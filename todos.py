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


# 一覧ページの区切り。上から順に並べる（key は見出しの色やページ内リンクに使う）
SECTIONS = [
    ("overdue", "期限切れ"),
    ("today", "今日"),
    ("tomorrow", "明日"),
    ("later", "これから"),
    ("someday", "期日なし"),
]


def section_of(todo, now):
    """未完了のやることが、一覧のどの区切りに入るか"""
    if is_overdue(todo, now):
        return "overdue"
    if not todo["due_date"]:
        return "someday"
    year, month, day = (int(part) for part in todo["due_date"].split("-"))
    days = (date(year, month, day) - now.date()).days
    if days <= 0:
        return "today"  # 今日の、まだ時刻を過ぎていないもの
    if days == 1:
        return "tomorrow"
    return "later"


def group_active(todos, now):
    """未完了のやることを区切りごとに分ける。中身のない区切りは省く。
    返り値：[{"key": "today", "label": "今日", "todos": [...]}, ...]（各区切りの中は期日の近い順）"""
    groups = {key: [] for key, _ in SECTIONS}
    for todo in sort_active(todos):
        groups[section_of(todo, now)].append(todo)
    return [{"key": key, "label": label, "todos": groups[key]} for key, label in SECTIONS if groups[key]]


def today_label(now):
    """一覧ページの見出しの下に出す今日の日付（例：11月6日 金曜日）"""
    return f"{now.month}月{now.day}日 {WEEKDAYS[now.weekday()]}曜日"


# 今日の前後は、日付ではなく言葉で出す
RELATIVE_DAYS = {-1: "昨日", 0: "今日", 1: "明日"}


def due_label(todo, now):
    """短い期日の表記。昨日・今日・明日は言葉で、ほかは日付で出し、今年なら年を省く
    （例：今日 14:30、11/8(日)、2027/1/10(日)）"""
    if not todo["due_date"]:
        return "期日なし"
    year, month, day = (int(part) for part in todo["due_date"].split("-"))
    due = date(year, month, day)
    relative = RELATIVE_DAYS.get((due - now.date()).days)
    if relative:
        label = relative
    else:
        weekday = WEEKDAYS[due.weekday()]
        label = f"{month}/{day}({weekday})" if year == now.year else f"{year}/{month}/{day}({weekday})"
    if todo.get("due_time"):
        label += f" {todo['due_time']}"
    return label
