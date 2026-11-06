import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta

import pytest

from app import create_app
from line_api import LineApiError, verify_signature
from line_bot import done_postback_data
from sheets import JST, now_jst
from todos import due_label

SECRET = "0123456789abcdef0123456789abcdef"
OWNER = "U" + "a" * 32
STRANGER = "U" + "b" * 32


class FakeLineClient:
    """本物のLINEに送らず、返信の内容を記録する"""

    def __init__(self, fail=False):
        self.replies = []
        self.fail = fail

    def reply(self, reply_token, messages):
        if self.fail:
            raise LineApiError("送信に失敗")
        self.replies.append((reply_token, messages))


@pytest.fixture
def line_client():
    return FakeLineClient()


@pytest.fixture
def line_app(storage, line_client):
    # CSRF を有効にしたままでも Webhook は受け取れることを確かめるため、WTF_CSRF_ENABLED は切らない
    return create_app(
        storage=storage,
        line_client=line_client,
        config={"TESTING": True, "SECRET_KEY": "test", "LINE_CHANNEL_SECRET": SECRET, "LINE_OWNER_USER_ID": OWNER},
    )


def sign(body):
    return base64.b64encode(hmac.new(SECRET.encode(), body, hashlib.sha256).digest()).decode()


def post_events(app, *events, signature=None):
    body = json.dumps({"destination": "Uxxx", "events": list(events)}).encode()
    return app.test_client().post(
        "/line/webhook",
        data=body,
        headers={"X-Line-Signature": signature if signature is not None else sign(body)},
        content_type="application/json",
    )


def text_event(text, user=OWNER):
    return {"type": "message", "replyToken": "token-1", "source": {"type": "user", "userId": user},
            "message": {"type": "text", "id": "1", "text": text}}


def postback_event(data, user=OWNER):
    return {"type": "postback", "replyToken": "token-1", "source": {"type": "user", "userId": user},
            "postback": {"data": data}}


def days_from_today(days):
    return (now_jst() + timedelta(days=days)).strftime("%Y-%m-%d")


def only_reply(line_client):
    [(token, messages)] = line_client.replies
    assert token == "token-1"
    return messages


def flex_titles(message):
    """Flex Message に並んだやることのタイトルを、上から順に取り出す"""
    rows = [c for c in message["contents"]["body"]["contents"] if c["type"] == "box"]
    return [row["contents"][0]["contents"][0]["text"] for row in rows]


def flex_text(message):
    return json.dumps(message, ensure_ascii=False)


# --- 署名の確認 ---


def test_verify_signature():
    body = b'{"events":[]}'
    assert verify_signature(SECRET, body, sign(body)) is True
    assert verify_signature(SECRET, body + b" ", sign(body)) is False
    assert verify_signature(SECRET, body, "") is False
    assert verify_signature(SECRET, body, None) is False
    assert verify_signature("", body, sign(body)) is False


def test_webhook_rejects_bad_signature(line_app, line_client, storage):
    storage.add("やること", "", "2026-10-25")

    res = post_events(line_app, text_event("一覧"), signature="wrong")

    assert res.status_code == 400
    assert line_client.replies == []


def test_webhook_rejects_when_secret_not_set(storage, line_client):
    app = create_app(storage=storage, line_client=line_client,
                     config={"TESTING": True, "SECRET_KEY": "test", "LINE_CHANNEL_SECRET": "", "LINE_OWNER_USER_ID": OWNER})
    assert post_events(app, text_event("一覧")).status_code == 400


def test_webhook_accepts_verification_request(line_app, line_client):
    # LINE Developers の「検証」ボタンでは、events が空のリクエストが届く
    res = post_events(line_app)
    assert res.status_code == 200
    assert line_client.replies == []


def test_webhook_ignores_other_users(line_app, line_client):
    res = post_events(line_app, text_event("一覧", user=STRANGER), postback_event("action=done&id=x", user=STRANGER))
    assert res.status_code == 200
    assert line_client.replies == []


def test_webhook_ignores_everyone_when_owner_not_set(storage, line_client):
    app = create_app(storage=storage, line_client=line_client,
                     config={"TESTING": True, "SECRET_KEY": "test", "LINE_CHANNEL_SECRET": SECRET, "LINE_OWNER_USER_ID": ""})
    assert post_events(app, text_event("一覧")).status_code == 200
    assert line_client.replies == []


# --- 「一覧」 ---


def test_list_shows_active_todos_in_order(line_app, line_client, storage):
    storage.add("あと", "", "2026-12-01")
    first = storage.add("さき", "", "2026-11-01", "09:00")
    done = storage.add("終わったこと", "", "2026-10-01")
    storage.toggle(done["id"])

    post_events(line_app, text_event("一覧"))

    [message] = only_reply(line_client)
    assert message["type"] == "flex"
    assert message["altText"] == "未完了のやること（2件）"
    assert flex_titles(message) == ["さき", "あと"]
    assert done_postback_data(first["id"]) in flex_text(message)
    assert [item["action"]["text"] for item in message["quickReply"]["items"]] == ["一覧", "今日"]


def test_list_marks_overdue(line_app, line_client, storage):
    storage.add("過ぎたもの", "", days_from_today(-1))

    post_events(line_app, text_event("一覧"))

    [message] = only_reply(line_client)
    assert "期限切れ" in flex_text(message)


def test_list_empty(line_app, line_client):
    post_events(line_app, text_event(" 一覧 "))

    [message] = only_reply(line_client)
    assert message["text"] == "未完了のやることはありません🎉"


def test_list_limits_items(line_app, line_client, storage):
    for i in range(12):
        storage.add(f"やること{i:02}", "", "2026-11-01")

    post_events(line_app, text_event("一覧"))

    [message] = only_reply(line_client)
    assert len(flex_titles(message)) == 10
    assert message["altText"] == "未完了のやること（12件）"
    assert "ほか2件はWebで確認できます" in flex_text(message)


# --- 「今日」 ---


def test_today_shows_due_today_and_overdue(line_app, line_client, storage):
    storage.add("明日", "", days_from_today(1))
    storage.add("今日", "", days_from_today(0))
    storage.add("昨日", "", days_from_today(-1))
    done = storage.add("今日の完了済み", "", days_from_today(0))
    storage.toggle(done["id"])

    post_events(line_app, text_event("今日"))

    [message] = only_reply(line_client)
    assert flex_titles(message) == ["昨日", "今日"]


def test_today_empty(line_app, line_client, storage):
    storage.add("明日", "", days_from_today(1))

    post_events(line_app, text_event("今日"))

    [message] = only_reply(line_client)
    assert "ありません" in message["text"]


# --- そのほかの言葉・友だち追加 ---


def test_unknown_text_shows_help(line_app, line_client):
    post_events(line_app, text_event("こんにちは"))

    [message] = only_reply(line_client)
    assert message["text"].startswith("使い方")
    assert "https://localhost/" in message["text"]


def test_follow_shows_help(line_app, line_client):
    post_events(line_app, {"type": "follow", "replyToken": "token-1", "source": {"type": "user", "userId": OWNER}})

    [message] = only_reply(line_client)
    assert message["text"].startswith("使い方")


def test_non_text_message_is_ignored(line_app, line_client):
    event = text_event("")
    event["message"] = {"type": "sticker", "id": "1"}
    post_events(line_app, event)
    assert line_client.replies == []


# --- 「完了」ボタン ---


def test_done_button_completes_todo(line_app, line_client, storage):
    todo = storage.add("買い物", "", "2026-11-01")

    post_events(line_app, postback_event(done_postback_data(todo["id"])))

    assert storage.get(todo["id"])["done"] is True
    [message] = only_reply(line_client)
    assert message["text"] == "「買い物」を完了にしました✅"


def test_done_button_twice_keeps_done(line_app, line_client, storage):
    todo = storage.add("買い物", "", "2026-11-01")
    data = done_postback_data(todo["id"])

    post_events(line_app, postback_event(data))
    post_events(line_app, postback_event(data))

    assert storage.get(todo["id"])["done"] is True
    assert line_client.replies[1][1][0]["text"] == "「買い物」はもう完了しています"


def test_done_button_for_deleted_todo(line_app, line_client):
    post_events(line_app, postback_event(done_postback_data("unknown")))

    [message] = only_reply(line_client)
    assert "見つかりませんでした" in message["text"]


def test_unknown_postback_is_ignored(line_app, line_client):
    post_events(line_app, postback_event("action=something"))
    assert line_client.replies == []


# --- エラー時の動き ---


class BrokenStorage:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            from sheets import StorageError

            raise StorageError("スプレッドシートとの通信に失敗しました")

        return fail


def test_storage_error_is_replied(line_client):
    app = create_app(storage=BrokenStorage(), line_client=line_client,
                     config={"TESTING": True, "SECRET_KEY": "test", "LINE_CHANNEL_SECRET": SECRET, "LINE_OWNER_USER_ID": OWNER})

    res = post_events(app, text_event("一覧"))

    assert res.status_code == 200
    [message] = only_reply(line_client)
    assert "スプレッドシートとの通信に失敗しました" in message["text"]


def test_reply_failure_still_returns_ok(storage):
    app = create_app(storage=storage, line_client=FakeLineClient(fail=True),
                     config={"TESTING": True, "SECRET_KEY": "test", "LINE_CHANNEL_SECRET": SECRET, "LINE_OWNER_USER_ID": OWNER})
    assert post_events(app, text_event("一覧")).status_code == 200


# --- 期日の表記 ---


@pytest.mark.parametrize(
    "due_date, due_time, expected",
    [
        ("2026-11-04", "", "11/4(水)"),
        ("2026-11-08", "14:30", "11/8(日) 14:30"),
        ("2026-11-05", "", "昨日"),
        ("2026-11-06", "09:00", "今日 09:00"),
        ("2026-11-07", "", "明日"),
        ("2027-01-10", "", "2027/1/10(日)"),
        ("", "", "期日なし"),
    ],
)
def test_due_label(due_date, due_time, expected):
    now = datetime(2026, 11, 6, 12, 0, tzinfo=JST)
    assert due_label({"due_date": due_date, "due_time": due_time}, now) == expected
