# Todoリスト

やることの登録・編集・一覧表示ができるWebアプリです。データはGoogleスプレッドシートに保存します。

- デモ：（Renderにデプロイしたらここに URL を書く）
- ステップ1ではログインがなく、URLを知っている人全員で1つのリストを共有します

<!-- スクリーンショット：docs/screenshot.png を置いたら下の行を有効にする -->
<!-- ![一覧ページ](docs/screenshot.png) -->

## 主な機能

- やることの登録・編集（タイトル・内容・期日）
- 一覧表示（未完了のやることを期日の近い順に表示）
- 完了・未完了の切り替え（完了したものは一覧から消え、「完了済み」ページに完了した順で表示。チェックを外すと一覧に戻る）
- 期限切れの強調表示（期日を過ぎた未完了のものを赤で表示）
- 削除（確認ダイアログあり）
- 入力チェック（タイトル必須・100文字以内、内容1000文字以内、期日必須・正しい日付）
- スマートフォン対応

## 使用技術

| 区分 | 技術 |
| --- | --- |
| 言語 | Python 3.12 |
| Webフレームワーク | Flask / Jinja2 |
| フォーム・CSRF対策 | Flask-WTF / WTForms |
| スプレッドシート連携 | gspread / google-auth（サービスアカウント） |
| 見た目 | Bootstrap 5 |
| テスト | pytest |
| 本番 | gunicorn / Render |

## 構成

```
[ブラウザ] ──HTTP──▶ [Flaskアプリ（Render）] ──Sheets API──▶ [Googleスプレッドシート]
                              │
                              └─ サービスアカウントの鍵（環境変数）で認証
```

| ファイル | 役割 |
| --- | --- |
| `app.py` | ルーティング、エラー処理 |
| `sheets.py` | 保存先の処理（`MemoryStorage` と `SheetsStorage`） |
| `forms.py` | フォームの定義と入力チェック |
| `templates/` | 一覧・フォーム・エラーのHTML |
| `static/` | CSS と、小さな JavaScript（完了チェックの送信、削除の確認） |
| `tests/` | pytest |

## セットアップ（ローカル）

Windows（PowerShell）：

```powershell
cd <このフォルダ>
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python -m flask --app app run --debug
```

Mac / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app app run --debug
```

> Windowsで `.venv\Scripts\activate` を使うと「スクリプトの実行が無効」というエラーになることがあります。上のように `.venv\Scripts\python` を直接使えば、有効化なしで動きます。

http://127.0.0.1:5000 を開きます。`.env` が `STORAGE=memory` のままなら、Googleの鍵がなくても動きます（データはメモリ上にあり、止めると消えます）。

### テスト

```bash
pytest
```

本物のスプレッドシートは使いません。メモリ保存と、偽物のシートを使ったスプレッドシート保存の両方で同じテストを流します。

## Googleスプレッドシートとつなぐ

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作る
2. 「APIとサービス」→「ライブラリ」で **Google Sheets API** と **Google Drive API** を有効にする
3. 「IAMと管理」→「サービスアカウント」でサービスアカウントを作り、「鍵」→「鍵を追加」→「JSON」で鍵をダウンロードする
4. スプレッドシートを新しく作り、「共有」でサービスアカウントのメールアドレス（`xxx@xxx.iam.gserviceaccount.com`）を **編集者** として追加する
5. ダウンロードした鍵をプロジェクトのフォルダに `service-account.json` という名前で置き、`.env` を次のように書き換える

```
STORAGE=sheets
SPREADSHEET_ID=<スプレッドシートのURLの /d/ と /edit のあいだの文字列>
GOOGLE_SERVICE_ACCOUNT_JSON=service-account.json
```

1行目の見出し（`id, title, content, due_date, done, created_at, updated_at`）は、シートが空なら自動で書き込みます。

> 鍵ファイルと `.env` は `.gitignore` で除外しているので、GitHubには上がりません。

## Renderへのデプロイ

1. GitHubにリポジトリを作ってプッシュする
2. Renderで「New」→「Web Service」を選び、リポジトリをつなぐ
3. 次のように設定する

| 項目 | 値 |
| --- | --- |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn "app:create_app()"` |

4. 「Environment」で環境変数を設定する

| 変数名 | 値 |
| --- | --- |
| `SECRET_KEY` | 長いランダムな文字列（`python -c "import secrets; print(secrets.token_hex(32))"` で作れる） |
| `STORAGE` | `sheets` |
| `SPREADSHEET_ID` | スプレッドシートのID |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 鍵のJSONファイルの **中身** をそのまま貼り付ける |
| `PYTHON_VERSION` | `3.12.10` |

無料プランでは、しばらくアクセスがないとスリープし、最初の表示に時間がかかります。

## 工夫した点

- **行番号ではなくidで特定する**：削除で行番号がずれても、編集・削除の対象を取り違えないように、UUIDで行を探す
- **保存先の処理を1つのファイルにまとめた**：`app.py` は保存先がメモリかスプレッドシートかを知らない。保存先の差し替えや、ステップ2のユーザー列の追加は `sheets.py` を直すだけで済む
- **APIの回数制限を考えた**：一覧ページの読み込みは1回だけにしている
- **通信に失敗してもアプリは止まらない**：エラー画面でメッセージを出す
- **値はRAWで書き込む**：スプレッドシート側で日付の形式が勝手に変わらないようにする
- **日時は日本時間で記録する**：サーバーの時刻設定に左右されない
- **セキュリティ**：CSRF対策（Flask-WTF）、テンプレートのエスケープ（XSS対策）。データを変える操作はすべてPOST。削除の確認メッセージはHTMLの属性から読み、インラインのJavaScriptにタイトルを埋め込まない

## 今後の予定（ステップ2）

- Googleアカウントでのログイン（Authlib）
- ユーザーごとにリストを分ける
