# Todoリスト

やることの登録・編集・一覧表示ができるWebアプリです。データはGoogleスプレッドシートに保存します。

- デモ：（Vercelのデモ URL をここに書く）
- ステップ1ではログインがなく、URLを知っている人全員で1つのリストを共有します

<!-- スクリーンショット：docs/screenshot.png を置いたら下の行を有効にする -->
<!-- ![一覧ページ](docs/screenshot.png) -->

## 主な機能

- やることの登録・編集（タイトル・内容・期日。期日には時刻も設定できる）
- 一覧表示（未完了のやることを期日・時刻の近い順に表示。時刻のないものはその日の最後）
- 完了・未完了の切り替え（完了したものは一覧から消え、「完了済み」ページに完了した順で表示。チェックを外すと一覧に戻る）
- 期限切れの強調表示（期日を過ぎた未完了のものを赤で表示。時刻つきのものは、その時刻を過ぎたら）
- カレンダー表示（月表示とリスト表示。予定を押すと編集ページを開く。スマートフォンでは最初にリスト表示）
- 削除（確認ダイアログあり）
- LINEで確認・完了（LINEで「一覧」「今日」と送ると、未完了のやることが「完了」ボタンつきで届く。ボタンを押すと完了になる）
- 入力チェック（タイトル必須・100文字以内、内容1000文字以内、期日必須・正しい日付、時刻は任意・正しい時刻）
- スマートフォン対応

## 使用技術

| 区分 | 技術 |
| --- | --- |
| 言語 | Python 3.12 |
| Webフレームワーク | Flask / Jinja2 |
| フォーム・CSRF対策 | Flask-WTF / WTForms |
| スプレッドシート連携 | gspread / google-auth（サービスアカウント） |
| LINE連携 | LINE Messaging API（Flex Message、ポストバック） |
| 見た目 | Bootstrap 5 / FullCalendar 6（カレンダー） |
| テスト | pytest |
| 本番 | Vercel（サーバーレス関数） |

## 構成

```
[ブラウザ] ──HTTP──────▶ [Flaskアプリ（Vercel）] ──Sheets API──▶ [Googleスプレッドシート]
                                 ▲   │
[LINE] ──Webhook（署名つき）─────┘   └──返信──▶ [LINE]
```

| ファイル | 役割 |
| --- | --- |
| `app.py` | ルーティング、エラー処理、LINEのWebhookの受け取り |
| `todos.py` | 並び替え・期限切れの判定など（WebとLINEで共通） |
| `line_api.py` | LINEとの通信（署名の確認、返信の送信） |
| `line_bot.py` | LINEの返事の組み立て（一覧・今日・完了ボタン） |
| `sheets.py` | 保存先の処理（`MemoryStorage` と `SheetsStorage`） |
| `forms.py` | フォームの定義と入力チェック |
| `templates/` | 一覧・カレンダー・フォーム・エラーのHTML |
| `static/` | CSS と、小さな JavaScript（完了チェックの送信、削除の確認、カレンダーの表示） |
| `wsgi.py` | 本番（Vercel）から読み込むエントリポイント |
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

1行目の見出し（`id, title, content, due_date, done, created_at, updated_at, due_time`）は、シートが空なら自動で書き込みます。列が足りない古い見出しの場合は、自動で今の列まで延ばします（データの行はそのまま使えます）。

> 鍵ファイルと `.env` は `.gitignore` で除外しているので、GitHubには上がりません。

## Vercelへのデプロイ

1. GitHubにリポジトリを作ってプッシュする
2. [Vercel](https://vercel.com/) で「Add New」→「Project」を選び、GitHubのリポジトリを読み込む
3. 「Environment Variables」で環境変数を設定して「Deploy」を押す

| 変数名 | 値 |
| --- | --- |
| `SECRET_KEY` | 長いランダムな文字列（`python -c "import secrets; print(secrets.token_hex(32))"` で作れる） |
| `STORAGE` | `sheets` |
| `SPREADSHEET_ID` | スプレッドシートのID |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 鍵のJSONファイルの **中身** をそのまま貼り付ける |

以降は、GitHubの `main` ブランチにプッシュすると自動でデプロイされます。

> **注意**
> - Vercelは `pyproject.toml` の `dependencies` から本番用のライブラリを入れ、`[tool.vercel]` の `entrypoint`（`wsgi:app`）からアプリを読み込みます。ライブラリを追加・更新したときは、`requirements.txt` と `pyproject.toml` の両方をそろえてください
> - `SECRET_KEY` は必ず設定してください。未設定だと起動のたびに値が変わり、Vercelでは処理するサーバーが入れ替わるため、フォームの送信で「画面の有効期限が切れました」というエラーが出やすくなります
> - `STORAGE=memory` はVercelでは使えません（データがサーバーごとにばらばらになり、すぐに消えます）。本番は必ず `sheets` にしてください
> - 環境変数を変えたあとは、「Deployments」から再デプロイすると反映されます

## LINEとつなぐ

1. [LINE公式アカウント](https://entry.line.biz/start/jp/) を作り、[LINE Official Account Manager](https://manager.line.biz/) の「設定」→「Messaging API」で Messaging API を有効にする
2. 同じく「設定」→「応答設定」で、**応答メッセージをオフ**、**Webhookをオン** にする
3. [LINE Developers](https://developers.line.biz/console/) でチャネルを開き、次の値を `.env`（本番はVercelの環境変数）に設定する

| 変数名 | どこにあるか |
| --- | --- |
| `LINE_CHANNEL_SECRET` | 「チャネル基本設定」タブのチャネルシークレット |
| `LINE_CHANNEL_ACCESS_TOKEN` | 「Messaging API設定」タブのチャネルアクセストークン（長期） |
| `LINE_OWNER_USER_ID` | 「チャネル基本設定」タブのあなたのユーザーID。このユーザー以外からの操作には反応しない |

4. 「Messaging API設定」タブの Webhook URL に `https://<デプロイ先のドメイン>/line/webhook` を設定し、「Webhookの利用」をオンにする
5. botを友だち追加して、「一覧」や「今日」と送る

> LINEのWebhookはインターネットから届くので、ローカル（127.0.0.1）では受け取れません。動きはテストで確かめ、実際のやり取りはデプロイしてから試します。

## 工夫した点

- **行番号ではなくidで特定する**：削除で行番号がずれても、編集・削除の対象を取り違えないように、UUIDで行を探す
- **保存先の処理を1つのファイルにまとめた**：`app.py` は保存先がメモリかスプレッドシートかを知らない。保存先の差し替えや、ステップ2のユーザー列の追加は `sheets.py` を直すだけで済む
- **APIの回数制限を考えた**：一覧ページの読み込みは1回だけにしている
- **通信に失敗してもアプリは止まらない**：エラー画面でメッセージを出す
- **値はRAWで書き込む**：スプレッドシート側で日付の形式が勝手に変わらないようにする
- **日時は日本時間で記録する**：サーバーの時刻設定に左右されない
- **カレンダーのデータはページに埋め込む**：APIを増やさず、一覧と同じく読み込み1回で表示する。JSONは Jinja2 の `tojson` で埋め込み、タイトルに `</script>` が含まれていても安全にしている
- **LINEは返信だけで答える**：無料プランは送信できるメッセージ数に上限があるが、返信は数えられない。確認や完了の操作はすべて返信で返している
- **LINEの「完了」ボタンは2回押しても安全**：切り替えではなく「完了にする」操作にしているので、押し直しても未完了に戻らない
- **ライブラリを増やさない**：LINEで使うのは署名の確認と返信だけなので、line-bot-sdk は使わず標準ライブラリで書いた
- **セキュリティ**：CSRF対策（Flask-WTF）、テンプレートのエスケープ（XSS対策）。データを変える操作はすべてPOST。削除の確認メッセージはHTMLの属性から読み、インラインのJavaScriptにタイトルを埋め込まない。LINEのWebhookは署名を確かめ、本物のLINEから、本人が送ったものだけを受け付ける

## 今後の予定

- LINEへの通知（期日の1時間前・30分前、毎朝の進捗）
- LINEの中での登録・編集（LIFF）
- ログインとユーザーごとのリスト（LINEログインを検討中）

くわしくは [要件定義書](要件定義書.md) の9章を参照してください。
