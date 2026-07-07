# Walkthrough - Go-based SQL Playlist Exporter for foobar2000

PostgreSQL データベースから任意の SQL クエリを実行し、M3U プレイリストなどを生成できる Go 製 CLI ツールと、それを統合したエージェント用カスタムスキルの実装が完了いたしましたわ。

## 実施した変更

### 1. Go CLI ツール
* **ファイル**: `C:\Users\letwir\.gemini\config\skills\foobar-sql-exporter\main.go`
* **機能**: 
  * `-q` / `--query`: 実行する任意の SQL。
  * `-f` / `--format`: `m3u` (ファイルパスとメタデータを M3U 形式で書き出し), `json`, `csv`, `text` (タブ区切り) に対応。
  * `-o` / `--output`: 結果の出力ファイルパス。
  * `--db`: 接続先 PostgreSQL URI（引数指定がない場合は環境変数 `DATABASE_URL` または親ディレクトリ群 of `config.toml` から自動取得）。
* **依存関係**: `github.com/jackc/pgx/v5`
* **ビルド先**: `C:\Users\letwir\.gemini\config\skills\foobar-sql-exporter\bin\fb2k-sql.exe`

### 2. カスタムスキル定義
* **ファイル**: `C:\Users\letwir\.gemini\config\skills\foobar-sql-exporter\SKILL.md`
* **機能**: エージェントに対し、`fb2k-sql.exe` の使い方とテーブル構造（`raw.foobar2000_tracks`, `raw.foobar2000_stats` など）の参照情報、プレイリスト生成用の有用な SQL テンプレートを提供しますわ。

## 検証結果

ユーザー（旦那様）から提示された一時的な接続先 URL を用いて、再生数が 5 回以上の楽曲から M3U プレイリストをエクスポートするテストを実行し、以下の形式で正しく出力されることを確認いたしましたわ。

```text
#EXTM3U
#EXTINF:-1,Magaloff：1956年5月~11月録音 - Chopin:マズルカ Op.56 No.1
file://M:\Music\album\CLASSIC\yung\Chopin：マズルカ Op.56 No.1.flac
...
```
動作検証は完全に成功しております。
