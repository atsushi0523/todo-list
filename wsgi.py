"""Vercel などの本番環境から読み込むエントリポイント"""

from app import create_app

app = create_app()
