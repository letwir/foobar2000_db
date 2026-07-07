-- Clean up all data in raw.foobar2000_* tables to start fresh

TRUNCATE TABLE 
    raw.foobar2000_playlist_tracks,
    raw.foobar2000_playlists,
    raw.foobar2000_stats,
    raw.foobar2000_plugins,
    raw.foobar2000_configs,
    raw.foobar2000_tracks,
    raw.foobar2000_hosts
CASCADE;
