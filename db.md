# foobar2000 SQLite Database Structure Analysis

foobar2000 v2.0 で使用されている `metadb.sqlite` には、音楽ライブラリのトラックURI（ファイルパス）をプライマリキーとするメタデータ情報や各種統計インデックスが格納されています。

- **filepath (ファイルパス)**: `metadb` テーブルの `name` カラムに URI 形式（例: `5+file://Z:\Music\...`）で格納されています。
- **md5 (MD5ハッシュ値)**: `metadb.info` BLOB 内にシリアライズされて格納されています。SQLの文字列・バイナリ操作関数を使用することで、外部プログラムを使わずに SQL だけで直接抽出可能です。

以下に、データベースに格納されている主要なタグおよび統計情報の抽出方法を纏めますわ。

---

## 1. メタデータタグ (metadb テーブル)

<md5>
  <table>metadb</table>
  <description>トラック音声データのMD5チェックサム値（32桁の16進数文字列）。重複検出などに利用されます。</description>
  <sql>
SELECT 
  name AS filepath, 
  SUBSTR(info, INSTR(info, X'6d643500') + 4, 32) AS md5 
FROM metadb 
WHERE INSTR(info, X'6d643500') > 0;
  </sql>
</md5>

<title>
  <table>metadb</table>
  <description>曲のタイトル。info BLOB内から可変長のNull終端文字列として動的に切り出します。</description>
  <sql>
SELECT 
  name AS filepath, 
  SUBSTR(info, INSTR(info, X'7469746c6500') + 6, INSTR(SUBSTR(info, INSTR(info, X'7469746c6500') + 6), X'00') - 1) AS title 
FROM metadb 
WHERE INSTR(info, X'7469746c6500') > 0;
  </sql>
</md5>

<artist>
  <table>metadb</table>
  <description>アーティスト名。</description>
  <sql>
SELECT 
  name AS filepath, 
  SUBSTR(info, INSTR(info, X'61727469737400') + 7, INSTR(SUBSTR(info, INSTR(info, X'61727469737400') + 7), X'00') - 1) AS artist 
FROM metadb 
WHERE INSTR(info, X'61727469737400') > 0;
  </sql>
</md5>

<album>
  <table>metadb</table>
  <description>アルバムタイトル。</description>
  <sql>
SELECT 
  name AS filepath, 
  SUBSTR(info, INSTR(info, X'616c62756d00') + 6, INSTR(SUBSTR(info, INSTR(info, X'616c62756d00') + 6), X'00') - 1) AS album 
FROM metadb 
WHERE INSTR(info, X'616c62756d00') > 0;
  </sql>
</md5>

<tracknumber>
  <table>metadb</table>
  <description>トラック番号。</description>
  <sql>
SELECT 
  name AS filepath, 
  SUBSTR(info, INSTR(info, X'747261636b6e756d62657200') + 12, INSTR(SUBSTR(info, INSTR(info, X'747261636b6e756d62657200') + 12), X'00') - 1) AS tracknumber 
FROM metadb 
WHERE INSTR(info, X'747261636b6e756d62657200') > 0;
  </sql>
</md5>

<genre>
  <table>metadb</table>
  <description>ジャンル情報。</description>
  <sql>
SELECT 
  name AS filepath, 
  SUBSTR(info, INSTR(info, X'47454e524500') + 6, INSTR(SUBSTR(info, INSTR(info, X'47454e524500') + 6), X'00') - 1) AS genre 
FROM metadb 
WHERE INSTR(info, X'47454e524500') > 0;
  </sql>
</md5>

<date>
  <table>metadb</table>
  <description>リリース年/日付。</description>
  <sql>
SELECT 
  name AS filepath, 
  SUBSTR(info, INSTR(info, X'4441544500') + 5, INSTR(SUBSTR(info, INSTR(info, X'4441544500') + 5), X'00') - 1) AS date 
FROM metadb 
WHERE INSTR(info, X'4441544500') > 0;
  </sql>
</md5>

---

## 2. 統計および外部インデックス (metadb_index_* テーブル群)

各種インデックスは `metadb_index_<GUID>` テーブルと、値の実体を持つ `metadb_index_<GUID>_data` テーブルの JOIN で取得可能です。

<playback_statistics>
  <table>metadb_index_C653739F_14B3_4EF2_819B_A3E2883230AE_data</table>
  <description>
再生回数および各種再生タイムスタンプ（added, first_played, last_played）を保持するバイナリ（40バイト）。
- Byte 0-7: 再生回数 (64-bit int LE)
- Byte 8-15: 追加日時 (FILETIME 64-bit LE)
- Byte 16-23: 最終再生日時 (FILETIME 64-bit LE)
- Byte 24-31: 初回再生日時 (FILETIME 64-bit LE)
- Byte 32-39: その他統計用パラメータ (64-bit LE)
  </description>
  <sql>
SELECT 
  idx.filename AS filepath,
  HEX(dat.value) AS raw_binary_hex
FROM metadb_index_C653739F_14B3_4EF2_819B_A3E2883230AE idx
JOIN metadb_index_C653739F_14B3_4EF2_819B_A3E2883230AE_data dat ON idx.key = dat.key;
  </sql>
</playback_statistics>

<rating>
  <table>metadb_index_915BEE72_FD1D_4CF8_90D4_8E2C18FD05BF_data</table>
  <description>
評価（星の数）情報（20バイトバイナリ）。
- Byte 0-3: 評価値 1〜5 (32-bit int LE)
- Byte 4-11: 評価を設定した日時 (FILETIME 64-bit LE)
- Byte 12-19: ゼロ埋め
  </description>
  <sql>
SELECT 
  idx.filename AS filepath,
  HEX(dat.value) AS raw_binary_hex
FROM metadb_index_915BEE72_FD1D_4CF8_90D4_8E2C18FD05BF idx
JOIN metadb_index_915BEE72_FD1D_4CF8_90D4_8E2C18FD05BF_data dat ON idx.key = dat.key;
  </sql>
</rating>

<playback_history>
  <table>metadb_index_0C1BD000_43E7_4078_B885_48EE4249DEC3_data</table>
  <description>再生履歴。各再生時の FILETIME タイムスタンプが可変長のバイナリ配列として記録されています。</description>
  <sql>
SELECT 
  idx.filename AS filepath,
  HEX(dat.value) AS raw_binary_hex
FROM metadb_index_0C1BD000_43E7_4078_B885_48EE4249DEC3 idx
JOIN metadb_index_0C1BD000_43E7_4078_B885_48EE4249DEC3_data dat ON idx.key = dat.key;
  </sql>
</playback_history>

<lyrics_path>
  <table>metadb_index_188A64AA_6C1B_4AC9_990A_067CD016F72C_data</table>
  <description>ローカルにキャッシュされた歌詞ファイル (.txt / .lrc) への絶対パステキストです。</description>
  <sql>
SELECT 
  idx.filename AS filepath,
  SUBSTR(dat.value, 9) AS lyrics_file_path
FROM metadb_index_188A64AA_6C1B_4AC9_990A_067CD016F72C idx
JOIN metadb_index_188A64AA_6C1B_4AC9_990A_067CD016F72C_data dat ON idx.key = dat.key;
  </sql>
</lyrics_path>

<lyrics_url>
  <table>metadb_index_88DA8D97_B450_4FF4_A881_F6F6AD3836C1_data</table>
  <description>歌詞を取得したWebソースURL（NetEase、Musixmatch等）の情報テキストです。</description>
  <sql>
SELECT 
  idx.filename AS filepath,
  SUBSTR(dat.value, 29) AS lyrics_source_url
FROM metadb_index_88DA8D97_B450_4FF4_A881_F6F6AD3836C1 idx
JOIN metadb_index_88DA8D97_B450_4FF4_A881_F6F6AD3836C1_data dat ON idx.key = dat.key;
  </sql>
</lyrics_url>
