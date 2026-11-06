"""LINE Messaging API との通信。

使うのは「署名の確認」「返信の送信」「こちらからの送信（プッシュ）」だけなので、
line-bot-sdk は使わず標準ライブラリで書いている。
"""

import base64
import hashlib
import hmac
import json
import urllib.request

REPLY_URL = "https://api.line.me/v2/bot/message/reply"
PUSH_URL = "https://api.line.me/v2/bot/message/push"


class LineApiError(Exception):
    """LINEへの送信に失敗したときに投げる例外"""


def verify_signature(channel_secret, body, signature):
    """Webhookが本当にLINEから届いたかを確かめる。

    LINEは、リクエストの本文をチャネルシークレットで HMAC-SHA256 した値を
    X-Line-Signature ヘッダーに入れて送ってくる。同じ計算をして一致すれば本物。
    """
    if not channel_secret or not signature:
        return False
    digest = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    # 比べるのにかかる時間から値を推測されないよう、compare_digest で比べる
    return hmac.compare_digest(expected, signature)


class LineClient:
    """メッセージを送る。テストでは同じ reply・push メソッドを持つ偽物に差し替える"""

    def __init__(self, access_token):
        self._access_token = access_token

    def reply(self, reply_token, messages):
        """届いたメッセージへの返信。送信数には数えられない"""
        self._post(REPLY_URL, {"replyToken": reply_token, "messages": messages}, "返信")

    def push(self, to, messages):
        """こちらから送る（通知）。無料プランでは月200通までなので、まとめて1回で送る"""
        self._post(PUSH_URL, {"to": to, "messages": messages}, "送信")

    def _post(self, url, payload, action):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._access_token}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10):
                pass
        except Exception as e:
            detail = e.read().decode("utf-8", "replace") if hasattr(e, "read") else str(e)
            raise LineApiError(f"LINEへの{action}に失敗しました: {detail}") from e
