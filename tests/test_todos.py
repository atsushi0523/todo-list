from datetime import datetime

from sheets import JST
from todos import group_active, section_of, today_label

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=JST)


def todo(title, due_date, due_time="", created_at="2026-11-01 00:00:00"):
    return {"title": title, "due_date": due_date, "due_time": due_time, "created_at": created_at}


def test_section_of():
    assert section_of(todo("昨日", "2026-11-05"), NOW) == "overdue"
    assert section_of(todo("今日の朝", "2026-11-06", "09:00"), NOW) == "overdue"  # 時刻を過ぎた
    assert section_of(todo("今日の夜", "2026-11-06", "18:00"), NOW) == "today"
    assert section_of(todo("今日", "2026-11-06"), NOW) == "today"
    assert section_of(todo("明日", "2026-11-07"), NOW) == "tomorrow"
    assert section_of(todo("来週", "2026-11-13"), NOW) == "later"
    assert section_of(todo("いつか", ""), NOW) == "someday"


def test_group_active_orders_sections_and_skips_empty():
    groups = group_active(
        [todo("いつか", ""), todo("来週", "2026-11-13"), todo("今日", "2026-11-06"), todo("昨日", "2026-11-05")], NOW
    )
    assert [g["key"] for g in groups] == ["overdue", "today", "later", "someday"]
    assert [g["label"] for g in groups] == ["期限切れ", "今日", "これから", "期日なし"]


def test_group_active_sorts_within_section():
    groups = group_active([todo("夜", "2026-11-06", "20:00"), todo("終日", "2026-11-06"), todo("昼", "2026-11-06", "13:00")], NOW)
    assert [t["title"] for t in groups[0]["todos"]] == ["昼", "夜", "終日"]


def test_today_label():
    assert today_label(NOW) == "11月6日 金曜日"
