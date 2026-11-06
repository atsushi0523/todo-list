"""Todoリスト Webアプリのルーティング"""

import hmac
import json
import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError, CSRFProtect

import line_bot
from forms import TodoForm
from line_api import LineApiError, LineClient, verify_signature
from reminders import due_reminders
from sheets import StorageError, create_storage, now_jst
from todos import due_label, group_active, is_overdue, sort_done, today_label


# 操作のあとに戻れるページ（フォームやURLの next の値 → エンドポイント名）
BACK_ENDPOINTS = {"done": "done_list", "calendar": "calendar"}


def back_endpoint():
    """操作のあとに戻るページ。完了済みページやカレンダーから来たときはそこへ戻る。それ以外は一覧ページ"""
    return BACK_ENDPOINTS.get(request.values.get("next"), "index")


def valid_date_or_none(value):
    """YYYY-MM-DD の正しい日付ならそのまま返し、そうでなければ None を返す"""
    try:
        return datetime.strptime(value or "", "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


# カレンダーの色（iOS の青・赤・グレーにそろえる。static/style.css の凡例と同じ）
EVENT_COLORS = {"active": "#007aff", "overdue": "#ff3b30", "done": "#8e8e93"}


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


def create_app(storage=None, config=None, line_client=None):
    load_dotenv()

    app = Flask(__name__)
    # SECRET_KEY が未設定なら起動ごとにランダムな値を使う（本番では必ず環境変数で設定する）
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(32).hex()
    for name in ("LINE_CHANNEL_SECRET", "LINE_CHANNEL_ACCESS_TOKEN", "LINE_OWNER_USER_ID", "CRON_SECRET"):
        app.config[name] = os.environ.get(name, "")
    if config:
        app.config.update(config)
    csrf = CSRFProtect(app)
    # テンプレートで期日を「今日 14:30」「11/8(日)」のように表示する
    app.jinja_env.globals["due_text"] = lambda todo: due_label(todo, now_jst())

    if storage is None:
        storage = create_storage()
    if line_client is None:
        line_client = LineClient(app.config["LINE_CHANNEL_ACCESS_TOKEN"])

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
        sections = group_active(active, now)
        counts = {section["key"]: len(section["todos"]) for section in sections}
        return render_template(
            "index.html",
            todos=active,
            sections=sections,
            counts=counts,
            today=today_label(now),
            page="index",
            active_count=len(active),
            done_count=len(done),
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
        if request.method == "GET":
            # カレンダーで日付を押して来たときは、その日を期日に入れておく（?due_date=YYYY-MM-DD）
            form = TodoForm(data={"due_date": valid_date_or_none(request.args.get("due_date"))})
        else:
            form = TodoForm()
        if form.validate_on_submit():
            storage.add(**form.todo_values())
            flash("登録しました", "success")
            return redirect(url_for(back_endpoint()))
        return render_template("form.html", form=form, heading="新規登録", back_url=url_for(back_endpoint()))

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
            flash("完了にしました", "success")
        return redirect(url_for(back_endpoint()))

    @app.post("/line/webhook")
    @csrf.exempt  # LINEのサーバーから届くのでCSRFトークンはない。代わりに署名で本物かを確かめる
    def line_webhook():
        body = request.get_data()
        if not verify_signature(app.config["LINE_CHANNEL_SECRET"], body, request.headers.get("X-Line-Signature")):
            app.logger.warning("LINEの署名が一致しないWebhookを拒否しました")
            abort(400)

        owner = app.config["LINE_OWNER_USER_ID"]
        web_url = url_for("index", _external=True, _scheme="https")
        for event in json.loads(body).get("events", []):
            # 当面は自分専用。LINE_OWNER_USER_ID 以外の人からの操作には何もしない
            if not owner or event.get("source", {}).get("userId") != owner or not event.get("replyToken"):
                continue
            try:
                messages = line_bot.handle_event(event, storage, now_jst(), web_url)
            except StorageError as e:
                app.logger.error("保存先との通信に失敗しました", exc_info=e)
                messages = [line_bot.text_message(str(e))]
            if not messages:
                continue
            try:
                line_client.reply(event["replyToken"], messages)
            except LineApiError as e:
                app.logger.error(str(e))
        # 返信に失敗しても 200 を返す（LINEに何度も送り直させないため）
        return "OK"

    @app.post("/tasks/remind")
    @csrf.exempt  # 外部の定期実行サービスから呼ばれるのでCSRFトークンはない。代わりに CRON_SECRET で確かめる
    def tasks_remind():
        """期日前の通知（L-06）。cron-job.org などから5分おきに呼び出してもらう。
        呼び出すときは「Authorization: Bearer <CRON_SECRET>」ヘッダーをつける"""
        secret = app.config["CRON_SECRET"]
        given = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not secret or not hmac.compare_digest(given.encode(), secret.encode()):
            app.logger.warning("CRON_SECRET が一致しない /tasks/remind の呼び出しを拒否しました")
            return jsonify(error="unauthorized"), 401

        owner = app.config["LINE_OWNER_USER_ID"]
        if not owner:
            return jsonify(error="LINE_OWNER_USER_ID が設定されていません"), 503

        now = now_jst()
        reminders = due_reminders(storage.list_all(), now)
        if not reminders:
            return jsonify(sent=0)

        web_url = url_for("index", _external=True, _scheme="https")
        try:
            line_client.push(owner, [line_bot.reminder_message(reminders, now, web_url)])
        except LineApiError as e:
            # 送れなかったときは記録しない（次の呼び出しで送り直す）
            app.logger.error(str(e))
            return jsonify(error="LINEへの送信に失敗しました"), 502

        # 送れたものだけ「送った」と記録して、同じ通知を二度送らないようにする
        for reminder in reminders:
            storage.mark_notified(reminder.todo["id"], reminder.minutes)
        return jsonify(sent=len(reminders), todos=[{"title": r.todo["title"], "minutes": r.minutes} for r in reminders])

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
