---
name: foobar-sql-exporter
description: Execute SQL queries against the foobar2000 PostgreSQL database to generate M3U playlists, extract metadata, or inspect configurations.
---

# SQL Playlist Exporter for foobar2000

This skill allows the agent to execute custom PostgreSQL queries against the foobar2000 tracks, statistics, and configuration tables to generate dynamic playlists or extract report information.

## How to use

Run the compiled Go binary `$env:USERPROFILE\.gemini\config\plugins\skills\foobar-sql-exporter\bin\fb2k-sql.exe` with a query and output target.

### Parameters
* `-q` or `--query`: The SQL query to execute.
* `-f` or `--format`: The output format: `m3u` (for playlists), `json`, `csv`, `text` (default).
* `-o` or `--output`: Destination path. If omitted, prints to stdout.
* `--db`: Connection URI. Always prioritize using the user-provided connection URI in the current environment if available, or fall back to the environment variable `DATABASE_URL`.

## Database Schema Reference

The tables in the database are:
1. `raw.foobar2000_hosts`: Registered hostnames.
2. `raw.foobar2000_tracks`: Universal track tags (indexed by MD5). Key columns: `audio_md5`, `filepath`, `title`, `artist`, `album`, `tracknumber`, `genre`, `date`.
3. `raw.foobar2000_stats`: Play statistics for tracks per host. Key columns: `audio_md5`, `hostname`, `play_count`, `rating`, `added_at`, `first_played_at`, `last_played_at`.
4. `raw.foobar2000_playlists`: Playlist metadata. Key columns: `playlist_id`, `hostname`, `name`.
5. `raw.foobar2000_playlist_tracks`: Playlist track mappings. Key columns: `playlist_id`, `hostname`, `track_index`, `audio_md5`, `subsong`.
6. `raw.foobar2000_configs`: Configuration values. Key columns: `hostname`, `config_key`, `config_val`.

## Example Queries & Commands

### 1. Generate an M3U playlist of high-rating tracks (rating >= 4)
```powershell
$db="postgres://postgres:postgres@localhost:5432/postgres"
& "$env:USERPROFILE\.gemini\config\plugins\skills\foobar-sql-exporter\bin\fb2k-sql.exe --db $db -f m3u -o fav_tracks.m3u -q "
SELECT t.filepath, t.artist, t.title 
FROM raw.foobar2000_tracks t
JOIN raw.foobar2000_stats s USING(audio_md5)
WHERE s.rating >= 4
ORDER BY s.play_count DESC
"
```

### 2. Export 50 random unrated tracks added during the last 6 months
```powershell
$db="postgres://postgres:postgres@localhost:5432/postgres"
& "$env:USERPROFILE\.gemini\config\plugins\skills\foobar-sql-exporter\bin\fb2k-sql.exe --db $db -f m3u -o recent_unrated.m3u -q "
SELECT t.filepath, t.artist, t.title 
FROM raw.foobar2000_tracks t
JOIN raw.foobar2000_stats s USING(audio_md5)
WHERE (s.rating IS NULL OR s.rating = 0)
  AND s.added_at >= NOW() - INTERVAL '6 months'
ORDER BY RANDOM()
LIMIT 50
"
```

### 3. Extract the configured Title Formatting string from configurations
```powershell
$db="postgres://postgres:postgres@localhost:5432/postgres"
& "$env:USERPROFILE\.gemini\config\plugins\skills\foobar-sql-exporter\bin\fb2k-sql.exe --db $db -f text -q "
SELECT hostname, config_key, config_val 
FROM raw.foobar2000_configs 
WHERE config_key LIKE 'titleformat.%' 
LIMIT 10
"
```
