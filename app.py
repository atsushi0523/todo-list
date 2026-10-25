"""Todoリスト Webアプリのルーティング"""

import os

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError, CSRFProtect

from forms import TodoForm
from sheets import StorageError, create_storage, now_jst


def sort_todos(todos):
    """未完了を先に、そのなかで期日の近い順。完了済みは後ろにまとめる"""
    return sorted(todos, key=lambda todo: (todo["done"], todo["due_date"] or "9999-12-31", todo["created_at"]))


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

    @app.get("/")
    def index():
        # Sheets APIの回数制限があるので、1回の表示で読み込むのは1回だけ
        todos = sort_todos(storage.list_all())
        today = now_jst().strftime("%Y-%m-%d")
        for todo in todos:
            todo["overdue"] = not todo["done"] and bool(todo["due_date"]) and todo["due_date"] < today
        return render_template("index.html", todos=todos)

    @app.route("/new", methods=["GET", "POST"])
    def new():
        form = TodoForm()
        if form.validate_on_submit():
            storage.add(**form.todo_values())
            flash("登録しました", "success")
            return redirect(url_for("index"))
        return render_template("form.html", form=form, heading="新規登録")

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
            return redirect(url_for("index"))
        return render_template("form.html", form=form, heading="編集")

    @app.post("/delete/<todo_id>")
    def delete(todo_id):
        if not storage.delete(todo_id):
            abort(404)
        flash("削除しました", "success")
        return redirect(url_for("index"))

    @app.post("/toggle/<todo_id>")
    def toggle(todo_id):
        if not storage.toggle(todo_id):
            abort(404)
        flash("完了状態を切り替えました", "success")
        return redirect(url_for("index"))

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
