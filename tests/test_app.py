from datetime import timedelta

import pytest

from app import create_app
from sheets import StorageError, now_jst


def days_from_today(days):
    return (now_jst() + timedelta(days=days)).strftime("%Y-%m-%d")


def valid_data(**overrides):
    data = {"title": "買い物に行く", "content": "牛乳と卵", "due_date": "2026-10-25"}
    data.update(overrides)
    return data


# --- 一覧表示 ---


def test_index_empty(client):
    res = client.get("/")
    html = res.get_data(as_text=True)
    assert res.status_code == 200
    assert "やることはまだありません" in html
    assert 'href="/new"' in html


def test_index_sorted_by_done_then_due_date(client, storage):
    storage.add("あとの期日", "", "2026-12-01")
    done = storage.add("完了済み", "", "2026-01-01")
    storage.add("近い期日", "", "2026-11-01")
    storage.toggle(done["id"])

    html = client.get("/").get_data(as_text=True)
    assert html.index("近い期日") < html.index("あとの期日") < html.index("完了済み")


def test_index_highlights_overdue(client, storage):
    storage.add("期限切れのもの", "", days_from_today(-1))
    storage.add("今日のもの", "", days_from_today(0))

    html = client.get("/").get_data(as_text=True)
    assert html.count("todo-overdue") == 1
    assert html.count("期限切れ</span>") == 1


def test_done_item_is_not_overdue(client, storage):
    todo = storage.add("終わったもの", "", days_from_today(-1))
    storage.toggle(todo["id"])

    html = client.get("/").get_data(as_text=True)
    assert "todo-done" in html
    assert "todo-overdue" not in html


def test_values_are_escaped(client, storage):
    storage.add("<script>alert(1)</script>", "", "2026-10-25")

    html = client.get("/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# --- 登録 ---


def test_new_form(client):
    res = client.get("/new")
    assert res.status_code == 200
    assert "新規登録" in res.get_data(as_text=True)


def test_create(client, storage):
    res = client.post("/new", data=valid_data(), follow_redirects=True)

    assert res.request.path == "/"
    assert "登録しました" in res.get_data(as_text=True)
    [todo] = storage.list_all()
    assert todo["title"] == "買い物に行く"
    assert todo["content"] == "牛乳と卵"
    assert todo["due_date"] == "2026-10-25"
    assert todo["done"] is False
    assert todo["id"] and todo["created_at"] and todo["updated_at"]


def test_create_strips_and_normalizes(client, storage):
    client.post("/new", data=valid_data(title="  前後に空白  ", content="", due_date="2026-1-5"))

    [todo] = storage.list_all()
    assert todo["title"] == "前後に空白"
    assert todo["content"] == ""
    assert todo["due_date"] == "2026-01-05"


@pytest.mark.parametrize(
    "data, message",
    [
        (valid_data(title=""), "タイトルを入力してください"),
        (valid_data(title="   "), "タイトルを入力してください"),
        (valid_data(title="あ" * 101), "タイトルは100文字以内で入力してください"),
        (valid_data(content="あ" * 1001), "内容は1000文字以内で入力してください"),
        (valid_data(due_date=""), "期日を入力してください"),
        (valid_data(due_date="abc"), "期日は正しい日付を YYYY-MM-DD の形式で入力してください"),
        (valid_data(due_date="2026-13-01"), "期日は正しい日付を YYYY-MM-DD の形式で入力してください"),
        (valid_data(due_date="2026-02-30"), "期日は正しい日付を YYYY-MM-DD の形式で入力してください"),
    ],
)
def test_create_rejects_invalid_input(client, storage, data, message):
    res = client.post("/new", data=data)

    assert res.status_code == 200
    assert message in res.get_data(as_text=True)
    assert storage.list_all() == []


def test_create_accepts_max_length(client, storage):
    client.post("/new", data=valid_data(title="あ" * 100, content="い" * 1000))
    assert len(storage.list_all()) == 1


# --- 編集 ---


def test_edit_form_shows_current_values(client, storage):
    todo = storage.add("元のタイトル", "元の内容", "2026-10-25")

    html = client.get(f"/edit/{todo['id']}").get_data(as_text=True)
    assert 'value="元のタイトル"' in html
    assert "元の内容" in html
    assert 'value="2026-10-25"' in html


def test_edit(client, storage):
    todo = storage.add("元のタイトル", "元の内容", "2026-10-25")

    res = client.post(
        f"/edit/{todo['id']}",
        data=valid_data(title="新しいタイトル", content="新しい内容", due_date="2026-11-30"),
        follow_redirects=True,
    )

    assert res.request.path == "/"
    assert "更新しました" in res.get_data(as_text=True)
    updated = storage.get(todo["id"])
    assert updated["title"] == "新しいタイトル"
    assert updated["content"] == "新しい内容"
    assert updated["due_date"] == "2026-11-30"
    assert updated["created_at"] == todo["created_at"]


def test_edit_rejects_invalid_input(client, storage):
    todo = storage.add("元のタイトル", "", "2026-10-25")

    res = client.post(f"/edit/{todo['id']}", data=valid_data(title=""))

    assert res.status_code == 200
    assert "タイトルを入力してください" in res.get_data(as_text=True)
    assert storage.get(todo["id"])["title"] == "元のタイトル"


def test_edit_unknown_id(client):
    assert client.get("/edit/unknown").status_code == 404
    assert client.post("/edit/unknown", data=valid_data()).status_code == 404


# --- 削除 ---


def test_delete(client, storage):
    keep = storage.add("残すもの", "", "2026-10-25")
    remove = storage.add("消すもの", "", "2026-10-25")

    res = client.post(f"/delete/{remove['id']}", follow_redirects=True)

    assert res.request.path == "/"
    assert "削除しました" in res.get_data(as_text=True)
    assert [t["id"] for t in storage.list_all()] == [keep["id"]]


def test_delete_requires_post(client, storage):
    todo = storage.add("消さないもの", "", "2026-10-25")

    assert client.get(f"/delete/{todo['id']}").status_code == 405
    assert storage.get(todo["id"]) is not None


def test_delete_unknown_id(client):
    assert client.post("/delete/unknown").status_code == 404


# --- 完了切り替え ---


def test_toggle(client, storage):
    todo = storage.add("切り替えるもの", "", "2026-10-25")

    res = client.post(f"/toggle/{todo['id']}", follow_redirects=True)
    assert res.request.path == "/"
    assert storage.get(todo["id"])["done"] is True

    client.post(f"/toggle/{todo['id']}")
    assert storage.get(todo["id"])["done"] is False


def test_toggle_requires_post(client, storage):
    todo = storage.add("切り替えないもの", "", "2026-10-25")

    assert client.get(f"/toggle/{todo['id']}").status_code == 405
    assert storage.get(todo["id"])["done"] is False


def test_toggle_unknown_id(client):
    assert client.post("/toggle/unknown").status_code == 404


# --- エラー時の動き ---


class BrokenStorage:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise StorageError("スプレッドシートとの通信に失敗しました")

        return fail


def test_storage_error_shows_message():
    app = create_app(storage=BrokenStorage(), config={"TESTING": True, "WTF_CSRF_ENABLED": False})
    client = app.test_client()

    for res in [client.get("/"), client.post("/new", data=valid_data()), client.post("/toggle/x")]:
        assert res.status_code == 503
        assert "スプレッドシートとの通信に失敗しました" in res.get_data(as_text=True)


def test_csrf_token_required(storage):
    app = create_app(storage=storage, config={"TESTING": True, "SECRET_KEY": "test"})
    client = app.test_client()

    res = client.post("/new", data=valid_data(), follow_redirects=True)

    assert "画面の有効期限が切れました" in res.get_data(as_text=True)
    assert storage.list_all() == []
