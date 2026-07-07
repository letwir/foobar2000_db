<api id="foobar2000-v2-sqlite">
<title>foobar2000 v2.0 SQLite Database Integration</title>
Context:
foobar2000 v2.0 uses SQLite for its metadb index and playback statistics. The database `metadb.sqlite` contains the central track registry (`metadb`) and various plugin-provided/native indexes (`metadb_index_*`).

Findings:
- `metadb.name` stores the track URI (e.g. `5+file://...`).
- `metadb.info` contains serialized metadata tags as null-terminated UTF-8 key-value strings.
- Standard metadata tags such as `md5`, `title`, `artist` can be extracted solely via SQL by parsing the `info` BLOB with `INSTR` and `SUBSTR` functions.
- The `metadb_index_<GUID>` tables represent specific metadata indexes:
  - `C653739F-14B3-4EF2-819B-A3E2883230AE`: Playback Statistics (play count, first/last played, added timestamps).
  - `915BEE72-FD1D-4CF8-90D4-8E2C18FD05BF`: Ratings cache (32-bit int score and FILETIME timestamp).
  - `188A64AA-6C1B-4AC9-990A-067CD016F72C`: Local lyrics text path cache.
  - `88DA8D97-B450-4FF4-A881-F6F6AD3836C1`: Online lyrics lookup URL cache.
  - `0C1BD000-43E7-4078-B885-48EE4249DEC3`: Playback history timestamps list.
</api>
