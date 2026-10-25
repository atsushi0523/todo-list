"""フォームの定義と入力チェック"""

from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

# 文字数の上限（要件定義書 2.1 の仮の値）
TITLE_MAX = 100
CONTENT_MAX = 1000

DATE_FORMAT = "%Y-%m-%d"


def _strip(value):
    return value.strip() if value else ""


def _valid_date(form, field):
    try:
        datetime.strptime(field.data, DATE_FORMAT)
    except (TypeError, ValueError):
        raise ValidationError("期日は正しい日付を YYYY-MM-DD の形式で入力してください")


class TodoForm(FlaskForm):
    """登録ページと編集ページで使い回すフォーム"""

    title = StringField(
        "タイトル",
        filters=[_strip],
        validators=[
            DataRequired(message="タイトルを入力してください"),
            Length(max=TITLE_MAX, message=f"タイトルは{TITLE_MAX}文字以内で入力してください"),
        ],
    )
    content = TextAreaField(
        "内容",
        filters=[_strip],
        validators=[
            Optional(),
            Length(max=CONTENT_MAX, message=f"内容は{CONTENT_MAX}文字以内で入力してください"),
        ],
    )
    due_date = StringField(
        "期日",
        filters=[_strip],
        validators=[DataRequired(message="期日を入力してください"), _valid_date],
        render_kw={"type": "date"},
    )
    submit = SubmitField("保存する")

    def todo_values(self):
        """保存先に渡す値。期日は YYYY-MM-DD にそろえる（例：2026-1-5 → 2026-01-05）"""
        due_date = datetime.strptime(self.due_date.data, DATE_FORMAT).strftime(DATE_FORMAT)
        return {"title": self.title.data, "content": self.content.data, "due_date": due_date}
