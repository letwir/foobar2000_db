-- Initialize raw schema and foobar2000 multi-host tables in PostgreSQL

CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.foobar2000_hosts (
    hostname VARCHAR(255) PRIMARY KEY,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.foobar2000_tracks (
    audio_md5 CHAR(32) PRIMARY KEY,
    filepath TEXT NOT NULL,
    title TEXT,
    artist TEXT,
    album TEXT,
    tracknumber VARCHAR(15),
    genre TEXT,
    date VARCHAR(20),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.foobar2000_stats (
    audio_md5 CHAR(32) REFERENCES raw.foobar2000_tracks(audio_md5),
    hostname VARCHAR(255) REFERENCES raw.foobar2000_hosts(hostname),
    play_count INTEGER DEFAULT 0,
    rating INTEGER,
    added_at TIMESTAMP,
    first_played_at TIMESTAMP,
    last_played_at TIMESTAMP,
    lyrics_path TEXT,
    lyrics_url TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (audio_md5, hostname)
);

CREATE TABLE IF NOT EXISTS raw.foobar2000_playlists (
    playlist_id UUID,
    hostname VARCHAR(255) REFERENCES raw.foobar2000_hosts(hostname),
    name TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (playlist_id, hostname)
);

CREATE TABLE IF NOT EXISTS raw.foobar2000_playlist_tracks (
    playlist_id UUID,
    hostname VARCHAR(255),
    track_index INTEGER,
    audio_md5 CHAR(32) REFERENCES raw.foobar2000_tracks(audio_md5),
    subsong INTEGER,
    PRIMARY KEY (playlist_id, hostname, track_index),
    FOREIGN KEY (playlist_id, hostname) REFERENCES raw.foobar2000_playlists(playlist_id, hostname)
);

CREATE TABLE IF NOT EXISTS raw.foobar2000_plugins (
    hostname VARCHAR(255) REFERENCES raw.foobar2000_hosts(hostname),
    plugin_name VARCHAR(255),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (hostname, plugin_name)
);

CREATE TABLE IF NOT EXISTS raw.foobar2000_configs (
    hostname VARCHAR(255) REFERENCES raw.foobar2000_hosts(hostname),
    config_key VARCHAR(255),
    config_val TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (hostname, config_key)
);

CREATE INDEX IF NOT EXISTS idx_fb2k_tracks_artist_album ON raw.foobar2000_tracks(artist, album);
CREATE INDEX IF NOT EXISTS idx_fb2k_tracks_filepath ON raw.foobar2000_tracks(filepath);
