"""Todoリスト Webアプリのルーティング"""

import os

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError, CSRFProtect

from forms import TodoForm
from sheets import StorageError, create_storage, now_jst


def sort_active(todos):
    """未完了のやることを期日・時刻の近い順に並べる。時刻のないものはその日の最後にする"""
    return sorted(
        todos,
        key=lambda todo: (todo["due_date"] or "9999-12-31", todo.get("due_time") or "99:99", todo["created_at"]),
    )


def is_overdue(todo, now):
    """期限切れかどうか。時刻つきなら期日と時刻を過ぎたとき、時刻なしなら期日が今日より前のとき"""
    if not todo["due_date"]:
        return False
    if todo.get("due_time"):
        return f"{todo['due_date']} {todo['due_time']}" < now.strftime("%Y-%m-%d %H:%M")
    return todo["due_date"] < now.strftime("%Y-%m-%d")


def sort_done(todos):
    """完了済みのやることを、完了した（最後に更新した）日時の新しい順に並べる"""
    return sorted(todos, key=lambda todo: todo["updated_at"], reverse=True)


# 操作のあとに戻れるページ（フォームやURLの next の値 → エンドポイント名）
BACK_ENDPOINTS = {"done": "done_list", "calendar": "calendar"}


def back_endpoint():
    """操作のあとに戻るページ。完了済みページやカレンダーから来たときはそこへ戻る。それ以外は一覧ページ"""
    return BACK_ENDPOINTS.get(request.values.get("next"), "index")


# カレンダーの色（Bootstrap の primary / danger / secondary にそろえる）
EVENT_COLORS = {"active": "#0d6efd", "overdue": "#dc3545", "done": "#6c757d"}


def calendar_events(todos, now):
    """FullCalendar に渡す予定の一覧を作る。時刻なしは終日の予定、時刻つきはその時刻の予定にする"""
    events = []
    for todo in todos:
        if not todo["due_date"]:
            continue
        if todo["done"]:
            status = "done"
        elif is_overdue(todo, now):
            status = "overdue"
        else:
            status = "active"
        event = {
            "id": todo["id"],
            "title": todo["title"],
            "url": url_for("edit", todo_id=todo["id"], next="calendar"),
            "color": EVENT_COLORS[status],
            "classNames": [f"todo-event-{status}"],
        }
        if todo.get("due_time"):
            event.update(start=f"{todo['due_date']}T{todo['due_time']}:00", allDay=False)
        else:
            event.update(start=todo["due_date"], allDay=True)
        events.append(event)
    return events


def create_app(storage=None, config=None):
    load_dotenv()

    app = Flask(__name__)
    # SECRET_KEY が未設定なら起動ごとにランダムな値を使う（本番では必ず環境変数で設定する）
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(32).hex()
    if config:
        app.config.update(config)
    CSRFProtect(app)

    if storage is None:
        storage = create_storage()

    def load_todos():
        """未完了と完了済みに分けて返す。Sheets APIの回数制限があるので、1回の表示で読み込むのは1回だけ"""
        todos = storage.list_all()
        active = [todo for todo in todos if not todo["done"]]
        done = [todo for todo in todos if todo["done"]]
        return active, done

    @app.get("/")
    def index():
        active, done = load_todos()
        now = now_jst()
        for todo in active:
            todo["overdue"] = is_overdue(todo, now)
        return render_template(
            "index.html", todos=sort_active(active), page="index", active_count=len(active), done_count=len(done)
        )

    @app.get("/done")
    def done_list():
        active, done = load_todos()
        return render_template(
            "done.html", todos=sort_done(done), page="done", active_count=len(active), done_count=len(done)
        )

    @app.get("/calendar")
    def calendar():
        active, done = load_todos()
        return render_template(
            "calendar.html",
            events=calendar_events(active + done, now_jst()),
            page="calendar",
            active_count=len(active),
            done_count=len(done),
        )

    @app.route("/new", methods=["GET", "POST"])
    def new():
        form = TodoForm()
        if form.validate_on_submit():
            storage.add(**form.todo_values())
            flash("登録しました", "success")
            return redirect(url_for("index"))
        return render_template("form.html", form=form, heading="新規登録", back_url=url_for("index"))

    @app.route("/edit/<todo_id>", methods=["GET", "POST"])
    def edit(todo_id):
        if request.method == "GET":
            todo = storage.get(todo_id)
            if todo is None:
                abort(404)
            form = TodoForm(data=todo)
        else:
            form = TodoForm()
        if form.validate_on_submit():
            if not storage.update(todo_id, **form.todo_values()):
                abort(404)
            flash("更新しました", "success")
            return redirect(url_for(back_endpoint()))
        return render_template("form.html", form=form, heading="編集", back_url=url_for(back_endpoint()))

    @app.post("/delete/<todo_id>")
    def delete(todo_id):
        if not storage.delete(todo_id):
            abort(404)
        flash("削除しました", "success")
        return redirect(url_for(back_endpoint()))

    @app.post("/toggle/<todo_id>")
    def toggle(todo_id):
        if not storage.toggle(todo_id):
            abort(404)
        if back_endpoint() == "done_list":
            flash("未完了に戻しました", "success")
        else:
            flash("完了にしました。完了済みページで確認できます", "success")
        return redirect(url_for(back_endpoint()))

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(StorageError)
    def storage_error(e):
        app.logger.error("保存先との通信に失敗しました", exc_info=e)
        return render_template("error.html", message=str(e)), 503

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        flash("画面の有効期限が切れました。もう一度操作してください", "warning")
        return redirect(url_for("index"))

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
