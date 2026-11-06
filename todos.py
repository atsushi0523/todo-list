"""やることの並び替えや判定。Webの画面とLINEのbotの両方で使う"""

from datetime import date

WEEKDAYS = "月火水木金土日"


def sort_active(todos):
    """未完了のやることを期日・時刻の近い順に並べる。時刻のないものはその日の最後にする"""
    return sorted(
        todos,
        key=lambda todo: (todo["due_date"] or "9999-12-31", todo.get("due_time") or "99:99", todo["created_at"]),
    )


def sort_done(todos):
    """完了済みのやることを、完了した（最後に更新した）日時の新しい順に並べる"""
    return sorted(todos, key=lambda todo: todo["updated_at"], reverse=True)


def is_overdue(todo, now):
    """期限切れかどうか。時刻つきなら期日と時刻を過ぎたとき、時刻なしなら期日が今日より前のとき"""
    if not todo["due_date"]:
        return False
    if todo.get("due_time"):
        return f"{todo['due_date']} {todo['due_time']}" < now.strftime("%Y-%m-%d %H:%M")
    return todo["due_date"] < now.strftime("%Y-%m-%d")


def is_due_today(todo, now):
    return todo["due_date"] == now.strftime("%Y-%m-%d")


def due_label(todo, now):
    """LINEで見やすい短い期日の表記。今年なら年を省く（例：11/5(水) 14:30、2027/1/10(日)）"""
    if not todo["due_date"]:
        return "期日なし"
    year, month, day = (int(part) for part in todo["due_date"].split("-"))
    weekday = WEEKDAYS[date(year, month, day).weekday()]
    label = f"{month}/{day}({weekday})" if year == now.year else f"{year}/{month}/{day}({weekday})"
    if todo.get("due_time"):
        label += f" {todo['due_time']}"
    return label
