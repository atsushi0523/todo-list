"""やることの保存先をまとめたモジュール。

アプリ本体（app.py）はここにあるクラスのメソッドだけを使う。
保存先を差し替えたり、ステップ2でユーザー列を足したりするときは、このファイルだけを直せばよい。

- MemoryStorage: メモリ上に保存する（鍵なしで動かす開発・テスト用）
- SheetsStorage: Googleスプレッドシートに保存する（本番用）
"""

import functools
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

# サーバーの時刻設定に左右されないよう、日本時間を固定で使う
JST = timezone(timedelta(hours=9), "JST")

# スプレッドシートの列の並び（A列〜G列）
FIELDS = ["id", "title", "content", "due_date", "done", "created_at", "updated_at"]


class StorageError(Exception):
    """保存先との通信に失敗したときに投げる例外"""


def now_jst():
    return datetime.now(JST)


def _timestamp():
    return now_jst().strftime("%Y-%m-%d %H:%M:%S")


def _new_todo(title, content, due_date):
    now = _timestamp()
    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "content": content,
        "due_date": due_date,
        "done": False,
        "created_at": now,
        "updated_at": now,
    }


class MemoryStorage:
    """メモリ上に保存する。アプリを止めるとデータは消える。"""

    def __init__(self):
        self._todos = {}

    def list_all(self):
        return [dict(todo) for todo in self._todos.values()]

    def get(self, todo_id):
        todo = self._todos.get(todo_id)
        return dict(todo) if todo else None

    def add(self, title, content, due_date):
        todo = _new_todo(title, content, due_date)
        self._todos[todo["id"]] = todo
        return dict(todo)

    def update(self, todo_id, title, content, due_date):
        todo = self._todos.get(todo_id)
        if todo is None:
            return False
        todo.update(title=title, content=content, due_date=due_date, updated_at=_timestamp())
        return True

    def delete(self, todo_id):
        return self._todos.pop(todo_id, None) is not None

    def toggle(self, todo_id):
        todo = self._todos.get(todo_id)
        if todo is None:
            return False
        todo.update(done=not todo["done"], updated_at=_timestamp())
        return True


def _wrap_errors(method):
    """通信まわりの例外をすべて StorageError に変換する"""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except StorageError:
            raise
        except Exception as e:
            raise StorageError("スプレッドシートとの通信に失敗しました。しばらくしてからもう一度お試しください") from e

    return wrapper


def _row_to_todo(row):
    row = list(row) + [""] * (len(FIELDS) - len(row))
    todo = dict(zip(FIELDS, row))
    todo["done"] = str(todo["done"]).upper() == "TRUE"
    return todo


def _todo_to_row(todo):
    return [("TRUE" if todo["done"] else "FALSE") if field == "done" else todo[field] for field in FIELDS]


class SheetsStorage:
    """Googleスプレッドシートの1枚目のシートに保存する。1行が1件で、1行目は見出し行。

    open_worksheet はシートを開く関数。最初に使うときに1回だけ呼ぶので、
    スプレッドシートにつながらなくてもアプリの起動自体は止まらない。
    """

    def __init__(self, open_worksheet):
        self._open_worksheet = open_worksheet
        self._worksheet = None

    def _ws(self):
        if self._worksheet is None:
            ws = self._open_worksheet()
            if not ws.row_values(1):
                ws.update(range_name="A1:G1", values=[FIELDS], value_input_option="RAW")
            self._worksheet = ws
        return self._worksheet

    def _find_row(self, todo_id):
        """idからシートの行番号を探す。行番号は削除でずれるので、毎回探し直す"""
        cell = self._ws().find(todo_id, in_column=1)
        if cell is None or cell.row == 1:  # 1行目は見出しなので対象外
            return None
        return cell.row

    def _write_row(self, row, todo):
        # RAW で書き込み、日付などがシート側で別の形式に変換されないようにする
        self._ws().update(range_name=f"A{row}:G{row}", values=[_todo_to_row(todo)], value_input_option="RAW")

    @_wrap_errors
    def list_all(self):
        rows = self._ws().get_all_values()[1:]
        return [_row_to_todo(row) for row in rows if row and row[0]]

    @_wrap_errors
    def get(self, todo_id):
        row = self._find_row(todo_id)
        if row is None:
            return None
        return _row_to_todo(self._ws().row_values(row))

    @_wrap_errors
    def add(self, title, content, due_date):
        todo = _new_todo(title, content, due_date)
        self._ws().append_row(_todo_to_row(todo), value_input_option="RAW")
        return todo

    @_wrap_errors
    def update(self, todo_id, title, content, due_date):
        row = self._find_row(todo_id)
        if row is None:
            return False
        todo = _row_to_todo(self._ws().row_values(row))
        todo.update(title=title, content=content, due_date=due_date, updated_at=_timestamp())
        self._write_row(row, todo)
        return True

    @_wrap_errors
    def delete(self, todo_id):
        row = self._find_row(todo_id)
        if row is None:
            return False
        self._ws().delete_rows(row)
        return True

    @_wrap_errors
    def toggle(self, todo_id):
        row = self._find_row(todo_id)
        if row is None:
            return False
        todo = _row_to_todo(self._ws().row_values(row))
        todo.update(done=not todo["done"], updated_at=_timestamp())
        self._write_row(row, todo)
        return True


def _load_credentials(value):
    """GOOGLE_SERVICE_ACCOUNT_JSON は、JSONの中身そのものか、鍵ファイルのパスのどちらでもよい"""
    value = value.strip()
    if value.startswith("{"):
        return json.loads(value)
    with open(value, encoding="utf-8") as f:
        return json.load(f)


def create_storage():
    """環境変数 STORAGE に合わせて保存先を作る（未設定なら memory）"""
    kind = os.environ.get("STORAGE", "memory")
    if kind == "memory":
        return MemoryStorage()
    if kind == "sheets":
        spreadsheet_id = os.environ.get("SPREADSHEET_ID")
        credentials = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not spreadsheet_id or not credentials:
            raise RuntimeError("STORAGE=sheets のときは SPREADSHEET_ID と GOOGLE_SERVICE_ACCOUNT_JSON を設定してください")
        credentials_info = _load_credentials(credentials)

        def open_worksheet():
            import gspread

            client = gspread.service_account_from_dict(credentials_info)
            return client.open_by_key(spreadsheet_id).sheet1

        return SheetsStorage(open_worksheet)
    raise RuntimeError(f"STORAGE には memory か sheets を指定してください（今の値：{kind}）")
