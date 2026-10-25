import pytest

from sheets import FIELDS, SheetsStorage, StorageError, create_storage, MemoryStorage


def test_writes_header_to_empty_sheet(worksheet):
    SheetsStorage(lambda: worksheet).list_all()
    assert worksheet.rows == [FIELDS]


def test_keeps_existing_header(worksheet):
    worksheet.rows = [FIELDS, ["abc", "既存", "", "2026-10-25", "FALSE", "", ""]]

    todos = SheetsStorage(lambda: worksheet).list_all()

    assert worksheet.rows[0] == FIELDS
    assert [t["title"] for t in todos] == ["既存"]


def test_row_layout(worksheet):
    storage = SheetsStorage(lambda: worksheet)
    todo = storage.add("買い物に行く", "牛乳と卵", "2026-10-25")

    row = worksheet.rows[1]
    assert row[:5] == [todo["id"], "買い物に行く", "牛乳と卵", "2026-10-25", "FALSE"]
    assert len(row) == len(FIELDS)


def test_finds_by_id_after_rows_shift(worksheet):
    storage = SheetsStorage(lambda: worksheet)
    first = storage.add("1件目", "", "2026-10-25")
    second = storage.add("2件目", "", "2026-10-25")

    storage.delete(first["id"])  # 2件目の行番号が1つずれる
    assert storage.toggle(second["id"])

    assert worksheet.rows[1][0] == second["id"]
    assert worksheet.rows[1][4] == "TRUE"


def test_header_row_is_not_a_todo(worksheet):
    storage = SheetsStorage(lambda: worksheet)
    storage.list_all()

    assert storage.get("id") is None
    assert storage.delete("id") is False
    assert worksheet.rows == [FIELDS]


def test_skips_blank_rows(worksheet):
    worksheet.rows = [FIELDS, [], ["abc", "あり", "", "2026-10-25", "TRUE"]]

    [todo] = SheetsStorage(lambda: worksheet).list_all()
    assert todo["done"] is True
    assert todo["updated_at"] == ""


def test_connection_error_becomes_storage_error():
    def open_worksheet():
        raise ConnectionError("network down")

    with pytest.raises(StorageError):
        SheetsStorage(open_worksheet).list_all()


def test_create_storage_defaults_to_memory(monkeypatch):
    monkeypatch.delenv("STORAGE", raising=False)
    assert isinstance(create_storage(), MemoryStorage)


def test_create_storage_sheets_requires_settings(monkeypatch):
    monkeypatch.setenv("STORAGE", "sheets")
    monkeypatch.delenv("SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)

    with pytest.raises(RuntimeError):
        create_storage()


def test_create_storage_rejects_unknown(monkeypatch):
    monkeypatch.setenv("STORAGE", "mysql")
    with pytest.raises(RuntimeError):
        create_storage()
