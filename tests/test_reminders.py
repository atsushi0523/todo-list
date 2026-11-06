from datetime import datetime, timedelta

import pytest

from app import create_app
from line_api import LineApiError
from reminders import due_reminders
from sheets import JST, NOTIFY_FIELDS

CRON_SECRET = "cron-secret-for-test"
OWNER = "U" + "a" * 32
NOW = datetime(2026, 11, 6, 12, 0, tzinfo=JST)


class FakeLineClient:
    def __init__(self, fail=False):
        self.pushes = []
        self.fail = fail

    def push(self, to, messages):
        if self.fail:
            raise LineApiError("送信に失敗")
        self.pushes.append((to, messages))


@pytest.fixture
def line_client():
    return FakeLineClient()


@pytest.fixture
def remind_app(storage, line_client):
    return create_app(
        storage=storage,
        line_client=line_client,
        config={"TESTING": True, "SECRET_KEY": "test", "CRON_SECRET": CRON_SECRET, "LINE_OWNER_USER_ID": OWNER},
    )


def call(app, secret=CRON_SECRET):
    headers = {"Authorization": f"Bearer {secret}"} if secret is not None else {}
    return app.test_client().post("/tasks/remind", headers=headers)


def due_in(minutes):
    """今から minutes 分後の期日と時刻（分単位に切り上げ）"""
    due = datetime.now(JST).replace(second=0, microsecond=0) + timedelta(minutes=minutes + 1)
    return due.strftime("%Y-%m-%d"), due.strftime("%H:%M")


def todo(due_date, due_time, done=False, **flags):
    return {"id": due_time, "title": "t", "due_date": due_date, "due_time": due_time, "done": done,
            "notified_60": flags.get("n60", False), "notified_30": flags.get("n30", False)}


# --- 送るものの選び方 ---


@pytest.mark.parametrize(
    "item, expected",
    [
        (todo("2026-11-06", "13:00"), 60),  # ちょうど60分前
        (todo("2026-11-06", "12:45"), 60),  # 45分前
        (todo("2026-11-06", "12:30"), 30),  # ちょうど30分前
        (todo("2026-11-06", "12:10"), 30),  # 10分前
        (todo("2026-11-06", "13:01"), None),  # まだ早い
        (todo("2026-11-06", "12:00"), None),  # ちょうど期日（過ぎた）
        (todo("2026-11-06", "11:50"), None),  # 期日を過ぎた
        (todo("2026-11-06", ""), None),  # 時刻なしは対象外
        (todo("2026-11-06", "12:45", done=True), None),  # 完了済み
        (todo("2026-11-06", "12:45", n60=True), None),  # 1時間前は送った
        (todo("2026-11-06", "12:10", n60=True), 30),  # 1時間前は送った → 30分前を送る
        (todo("2026-11-06", "12:10", n30=True), None),  # 30分前も送った
    ],
)
def test_due_reminders(item, expected):
    reminders = due_reminders([item], NOW)
    assert [r.minutes for r in reminders] == ([expected] if expected else [])


def test_registered_within_30_minutes_gets_only_30_minute_notice(storage):
    item = storage.add("急ぎ", "", *due_in(20))
    [reminder] = due_reminders(storage.list_all(), datetime.now(JST))
    assert reminder.minutes == 30
    storage.mark_notified(item["id"], 30)
    assert due_reminders(storage.list_all(), datetime.now(JST)) == []  # 1時間前の通知はもう送らない


# --- /tasks/remind ---


def test_remind_requires_secret(remind_app, line_client, storage):
    storage.add("会議", "", *due_in(40))
    assert call(remind_app, secret=None).status_code == 401
    assert call(remind_app, secret="wrong").status_code == 401
    assert line_client.pushes == []


def test_remind_disabled_when_secret_not_set(storage, line_client):
    app = create_app(storage=storage, line_client=line_client,
                     config={"TESTING": True, "SECRET_KEY": "test", "CRON_SECRET": "", "LINE_OWNER_USER_ID": OWNER})
    assert call(app, secret="").status_code == 401


def test_remind_get_is_not_allowed(remind_app):
    res = remind_app.test_client().get("/tasks/remind", headers={"Authorization": f"Bearer {CRON_SECRET}"})
    assert res.status_code == 405


def test_remind_sends_once_and_combines(remind_app, line_client, storage):
    storage.add("会議", "", *due_in(40))
    storage.add("電話", "", *due_in(10))
    storage.add("まだ先", "", *due_in(180))

    res = call(remind_app)

    assert res.status_code == 200
    assert res.get_json()["sent"] == 2
    [(to, [message])] = line_client.pushes  # 2件を1通にまとめる
    assert to == OWNER
    assert message["type"] == "flex"
    assert message["altText"].startswith("⏰「電話」の期限まで")  # 近いほうが先
    assert "ほか1件" in message["altText"]
    text = str(message)
    assert "会議" in text and "電話" in text and "まだ先" not in text

    # 2回目の呼び出しでは同じ通知を送らない
    assert call(remind_app).get_json()["sent"] == 0
    assert len(line_client.pushes) == 1


def test_remind_nothing_to_send(remind_app, line_client, storage):
    storage.add("まだ先", "", *due_in(180))
    assert call(remind_app).get_json() == {"sent": 0}
    assert line_client.pushes == []


def test_remind_failure_is_retried(storage):
    item = storage.add("会議", "", *due_in(40))
    app = create_app(storage=storage, line_client=FakeLineClient(fail=True),
                     config={"TESTING": True, "SECRET_KEY": "test", "CRON_SECRET": CRON_SECRET, "LINE_OWNER_USER_ID": OWNER})

    assert call(app).status_code == 502
    assert storage.get(item["id"])["notified_60"] is False  # 送れていないので、次の呼び出しで送り直す


def test_remind_without_owner(storage, line_client):
    storage.add("会議", "", *due_in(40))
    app = create_app(storage=storage, line_client=line_client,
                     config={"TESTING": True, "SECRET_KEY": "test", "CRON_SECRET": CRON_SECRET, "LINE_OWNER_USER_ID": ""})
    assert call(app).status_code == 503


# --- 保存先 ---


def test_mark_notified(storage):
    item = storage.add("会議", "", "2026-11-06", "13:00")
    before = storage.get(item["id"])["updated_at"]

    storage.mark_notified(item["id"], 60)
    saved = storage.get(item["id"])
    assert (saved["notified_60"], saved["notified_30"]) == (True, False)
    assert saved["updated_at"] == before  # 完了済みページの並びを変えない

    storage.mark_notified(item["id"], 30)
    saved = storage.get(item["id"])
    assert (saved["notified_60"], saved["notified_30"]) == (True, True)
    assert storage.mark_notified("unknown", 30) is False


def test_editing_due_resets_notified(storage):
    item = storage.add("会議", "", "2026-11-06", "13:00")
    storage.mark_notified(item["id"], 30)

    storage.update(item["id"], "会議（名前だけ変更）", "", "2026-11-06", "13:00")
    assert storage.get(item["id"])["notified_30"] is True  # 期日が同じなら送り直さない

    storage.update(item["id"], "会議", "", "2026-11-06", "15:00")
    saved = storage.get(item["id"])
    assert (saved["notified_60"], saved["notified_30"]) == (False, False)


def test_notify_fields_are_in_sheet_columns():
    from sheets import FIELDS, LAST_COLUMN

    assert FIELDS[7:] == ["due_time", "user_id", *NOTIFY_FIELDS.values()]
    assert LAST_COLUMN == "K"


def test_old_rows_without_new_columns(storage, worksheet):
    # H列までしかない古い行も読める（通知はまだ送っていない扱い）
    from sheets import SheetsStorage

    if not isinstance(storage, SheetsStorage):
        pytest.skip("スプレッドシートだけの話")
    storage.list_all()  # 見出しを書かせる
    worksheet.rows.append(["old-1", "古い", "", "2026-11-06", "FALSE", "x", "x", "13:00"])
    [old] = storage.list_all()
    assert (old["notified_60"], old["notified_30"], old["user_id"]) == (False, False, "")
