import re
from types import SimpleNamespace

import pytest

from app import create_app
from sheets import MemoryStorage, SheetsStorage


class FakeWorksheet:
    """gspread の Worksheet の代わり。本物のスプレッドシートを使わずに SheetsStorage を試すためのもの"""

    def __init__(self):
        self.rows = []

    def row_values(self, row):
        return list(self.rows[row - 1]) if row <= len(self.rows) else []

    def get_all_values(self):
        return [list(row) for row in self.rows]

    def append_row(self, values, value_input_option=None):
        self.rows.append([str(v) for v in values])

    def find(self, query, in_column=None):
        for i, row in enumerate(self.rows, start=1):
            if row and row[0] == query:
                return SimpleNamespace(row=i, col=1)
        return None

    def update(self, range_name, values, value_input_option=None):
        row = int(re.match(r"A(\d+)", range_name)[1])
        while len(self.rows) < row:
            self.rows.append([])
        self.rows[row - 1] = [str(v) for v in values[0]]

    def delete_rows(self, row):
        del self.rows[row - 1]


@pytest.fixture
def worksheet():
    return FakeWorksheet()


@pytest.fixture(params=["memory", "sheets"])
def storage(request, worksheet):
    """アプリのテストは、メモリ保存とスプレッドシート保存（偽物のシート）の両方で動かす"""
    if request.param == "memory":
        return MemoryStorage()
    return SheetsStorage(lambda: worksheet)


@pytest.fixture
def app(storage):
    return create_app(
        storage=storage,
        config={"TESTING": True, "WTF_CSRF_ENABLED": False, "SECRET_KEY": "test"},
    )


@pytest.fixture
def client(app):
    return app.test_client()
