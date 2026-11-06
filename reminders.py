"""期日前の通知（要件定義書 L-06）で、いま送るべきものを選ぶ。

外部の定期実行サービス（cron-job.org など）が5分おきに /tasks/remind を呼び出し、
そのたびにここで「期日まで60分・30分を切って、まだ送っていないもの」を探す。
"""

import math
from dataclasses import dataclass
from datetime import datetime

from sheets import JST


@dataclass
class Reminder:
    todo: dict
    minutes: int  # 何分前の通知か（60 か 30）
    minutes_left: int  # 期日まであと何分か（切り上げ）


def due_at(todo):
    """期日と時刻を日時にする。時刻のないやることは期日前の通知の対象外なので None"""
    if not todo["due_date"] or not todo.get("due_time"):
        return None
    try:
        return datetime.strptime(f"{todo['due_date']} {todo['due_time']}", "%Y-%m-%d %H:%M").replace(tzinfo=JST)
    except ValueError:
        return None


def due_reminders(todos, now):
    """いま送るべき通知を、期日の近い順に返す。

    - 期日まで30分以内で、30分前の通知をまだ送っていない → 30分前の通知
    - 期日まで60分以内で、1時間前の通知をまだ送っていない → 1時間前の通知
      （30分を切ってから登録したものは、ここに来る前に30分前の通知になるので、1時間前の通知は送らない）
    - 完了済み・時刻なし・期日を過ぎたものには送らない
    """
    reminders = []
    for todo in todos:
        due = due_at(todo)
        if todo["done"] or due is None:
            continue
        seconds_left = (due - now).total_seconds()
        if seconds_left <= 0:
            continue
        minutes_left = math.ceil(seconds_left / 60)
        if minutes_left <= 30:
            if not todo.get("notified_30"):
                reminders.append(Reminder(todo, 30, minutes_left))
        elif minutes_left <= 60:
            if not todo.get("notified_60"):
                reminders.append(Reminder(todo, 60, minutes_left))
    return sorted(reminders, key=lambda r: r.minutes_left)
