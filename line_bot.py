"""LINEのbotの返事を組み立てる。

LINEとの通信（line_api.py）とは分けてあり、ここではメッセージの中身（dict）を作るだけ。
そのため、本物のLINEにつながなくてもテストできる。
"""

from urllib.parse import parse_qs, urlencode

from todos import due_label, is_due_today, is_overdue, sort_active

# 1回の返信に並べるやることの上限（多すぎると読みにくく、メッセージの大きさの上限にも近づくため）
MAX_ITEMS = 10

COLOR_PRIMARY = "#0d6efd"
COLOR_DANGER = "#dc3545"
COLOR_MUTED = "#6c757d"

LIST_WORDS = {"一覧", "いちらん", "リスト"}
TODAY_WORDS = {"今日", "きょう"}


def text_message(text):
    return {"type": "text", "text": text}


def quick_reply():
    """返信の下に出るボタン。押すとそのままメッセージを送れる"""
    return {
        "items": [
            {"type": "action", "action": {"type": "message", "label": label, "text": label}}
            for label in ("一覧", "今日")
        ]
    }


def help_message(web_url):
    return text_message(
        "使い方\n"
        "・「一覧」と送る：未完了のやること\n"
        "・「今日」と送る：今日が期日のやることと、期限切れのやること\n"
        "・「完了」ボタンを押す：そのやることを完了にする\n\n"
        f"登録や編集はWebからできます。\n{web_url}"
    )


def done_postback_data(todo_id):
    return urlencode({"action": "done", "id": todo_id})


def _todo_row(todo, now):
    overdue = is_overdue(todo, now)
    label = due_label(todo, now) + ("　期限切れ" if overdue else "")
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "md",
        "alignItems": "center",
        "contents": [
            {
                "type": "box",
                "layout": "vertical",
                "flex": 3,
                "contents": [
                    {"type": "text", "text": todo["title"], "weight": "bold", "size": "sm", "wrap": True},
                    {"type": "text", "text": label, "size": "xs", "color": COLOR_DANGER if overdue else COLOR_MUTED},
                ],
            },
            {
                "type": "button",
                "flex": 1,
                "style": "primary",
                "height": "sm",
                "color": COLOR_PRIMARY,
                "action": {"type": "postback", "label": "完了", "data": done_postback_data(todo["id"])},
            },
        ],
    }


def todo_list_message(heading, todos, now, web_url):
    """やることを1件ずつ「完了」ボタンつきで並べたカード（Flex Message）を作る"""
    shown = todos[:MAX_ITEMS]
    rows = []
    for todo in shown:
        if rows:
            rows.append({"type": "separator"})
        rows.append(_todo_row(todo, now))
    if len(todos) > len(shown):
        rows.append(
            {"type": "text", "text": f"ほか{len(todos) - len(shown)}件はWebで確認できます", "size": "xs", "color": COLOR_MUTED}
        )

    return {
        "type": "flex",
        "altText": f"{heading}（{len(todos)}件）",
        "contents": {
            "type": "bubble",
            "size": "giga",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": heading, "weight": "bold", "size": "lg"},
                    {"type": "text", "text": f"{len(todos)}件", "size": "sm", "color": COLOR_MUTED},
                ],
            },
            "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": rows},
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "button", "style": "link", "height": "sm", "action": {"type": "uri", "label": "Webで開く", "uri": web_url}}
                ],
            },
        },
    }


def reply_to_text(text, storage, now, web_url):
    word = text.strip()
    if word in LIST_WORDS:
        active = sort_active([todo for todo in storage.list_all() if not todo["done"]])
        if not active:
            return [text_message("未完了のやることはありません🎉")]
        return [todo_list_message("未完了のやること", active, now, web_url)]
    if word in TODAY_WORDS:
        active = [todo for todo in storage.list_all() if not todo["done"]]
        today = sort_active([todo for todo in active if is_due_today(todo, now) or is_overdue(todo, now)])
        if not today:
            return [text_message("今日が期日のやることと、期限切れのやることはありません🎉")]
        return [todo_list_message("今日のやること", today, now, web_url)]
    return [help_message(web_url)]


def reply_to_postback(data, storage):
    params = parse_qs(data)
    if params.get("action") != ["done"] or not params.get("id"):
        return None
    todo = storage.get(params["id"][0])
    if todo is None:
        return [text_message("そのやることは見つかりませんでした。削除された可能性があります")]
    if todo["done"]:
        # 同じボタンを2回押しても、未完了に戻さない
        return [text_message(f"「{todo['title']}」はもう完了しています")]
    storage.toggle(todo["id"])
    return [text_message(f"「{todo['title']}」を完了にしました✅")]


def handle_event(event, storage, now, web_url):
    """LINEから届いた1件のイベントに対して、返信するメッセージのリストを返す。返信しないときは None"""
    kind = event.get("type")
    messages = None
    if kind == "message" and event.get("message", {}).get("type") == "text":
        messages = reply_to_text(event["message"]["text"], storage, now, web_url)
    elif kind == "postback":
        messages = reply_to_postback(event.get("postback", {}).get("data", ""), storage)
    elif kind == "follow":
        messages = [help_message(web_url)]
    if messages:
        messages[-1]["quickReply"] = quick_reply()
    return messages
