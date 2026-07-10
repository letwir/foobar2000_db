# Implementation Plan - Go-based SQL Playlist Exporter for foobar2000

PostgreSQL データベースに格納された foobar2000 の楽曲情報や再生統計、設定情報を対象に、任意の SQL を実行して M3U プレイリストや JSON などで結果を出力できる Go 製の CLI ツールを作成し、それをエージェントから利用できるカスタムスキル（`C:\Users\letwir\.gemini\config\skills\foobar-sql-exporter`）として登録いたしますわ。

ご指示に従い、この Go プロジェクト自体をカスタムスキルのディレクトリ内に作成し、完全に自己完結した構成といたします。

---

## User Review Required

> [!IMPORTANT]
> DBの接続文字列は、ソースコードや設定ファイルへの永続保存・Gitコミットを行わず、実行時の引数または一時的な環境変数として安全に引き渡す実装にいたしますわ。
> 
> 全てのプログラムコード、モジュール定義、ビルドされたバイナリを `C:\Users\letwir\.gemini\config\skills\foobar-sql-exporter` 内で完結するように配置いたします。

---

## Proposed Changes

### [Custom Agent Skill & Go Project]

#### [NEW] [SKILL.md](file:///C:/Users/letwir/.gemini/config/skills/foobar-sql-exporter/SKILL.md)
エージェントに SQL プレイリストエクスポートスキルを教え込むための設定ファイルですわ。
- プレイリスト生成のための代表的な SQL テンプレート（「再生回数が一定以上の隠れた名曲」「最近追加されたアニソン」など）を収録。
- 同ディレクトリ内の Go 製バイナリ `bin/fb2k-sql.exe` を使って、自然言語の指示から SQL を生成・実行させる手順を定義。

#### [NEW] [main.go](file:///C:/Users/letwir/.gemini/config/skills/foobar-sql-exporter/main.go)
SQLを実行し、結果を出力する Go 言語によるシンプルな CLI プログラムですわ。
- `jackc/pgx/v5` を用いて PostgreSQL に接続。
- `-q` / `--query`: 実行するSQLクエリ。
- `-o` / `--output`: 出力ファイルパス。
- `-f` / `--format`: 出力形式（`m3u`, `csv`, `json`, `text`）。`m3u` は `filepath` カラムの値を M3U フォーマット（ローカル/NASの絶対パス）で書き出します。
- `--db`: データベース接続URI（未指定時は環境変数 `DATABASE_URL` から取得するが、一時的な指定に対応）。

#### [NEW] [go.mod](file:///C:/Users/letwir/.gemini/config/skills/foobar-sql-exporter/go.mod)
Go のモジュール定義。

---

## Verification Plan

### Automated Tests
- カスタムスキルフォルダ内で Go コードがビルドできることの確認。
  ```powershell
  cd "C:\Users\letwir\.gemini\config\skills\foobar-sql-exporter"
  go.exe build -o bin/fb2k-sql.exe main.go
  ```

### Manual Verification
- 提示された Postgres 接続文字列を一時環境変数にセットし、動作確認用の SQL を実行して M3U プレイリストが正しく生成されるかテストします。
  ```powershell
  C:\Users\letwir\.gemini\config\skills\foobar-sql-exporter\bin\fb2k-sql.exe -q "SELECT filepath FROM raw.foobar2000_tracks JOIN raw.foobar2000_stats USING(audio_md5) WHERE play_count > 5 LIMIT 10" -f m3u -o test.m3u
  ```
- 生成された `test.m3u` の中身が正しい絶対パスになっているか確認します。
