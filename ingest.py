import os
import shutil
import sqlite3
import struct
import datetime
import sys
import socket
import tomllib
import psycopg
import tempfile

# Ensure UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def filetime_to_datetime(ft):
    if ft == 0:
        return None
    try:
        # FILETIME is 100-nanosecond intervals since Jan 1, 1601.
        sec = ft / 10000000.0 - 11644473600.0
        if sec < 0 or sec > 100000000000.0:
            return None
        return datetime.datetime.fromtimestamp(sec, datetime.timezone.utc)
    except:
        return None

def parse_iso_datetime(dt_str):
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            dt = datetime.datetime.strptime(dt_str.strip(), fmt)
            return dt.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
    return None

def clean_pg_text(val):
    if val is None:
        return None
    if isinstance(val, str):
        val = val.replace('\ufeff', '')
        return val.split('\x00')[0]
    return val

def extract_tag(blob, tag_name_bytes):
    if not blob:
        return None
    idx = blob.find(tag_name_bytes)
    if idx == -1:
        return None
    val_start = idx + len(tag_name_bytes)
    val_end = blob.find(b'\x00', val_start)
    if val_end == -1:
        try:
            val = blob[val_start:].decode('utf-8', errors='ignore')
            return clean_pg_text(val)
        except:
            return None
    try:
        val = blob[val_start:val_end].decode('utf-8', errors='ignore')
        return clean_pg_text(val)
    except:
        return None

def get_metadata_tag(blob, tag_name):
    for t in [tag_name.lower(), tag_name.upper(), tag_name.title()]:
        val = extract_tag(blob, t.encode('utf-8') + b'\x00')
        if val is not None:
            return val
    return None

def clean_filepath(uri):
    # e.g. "5+file://Z:\Music\..." -> "file://Z:\Music\..."
    # or "file://..." -> "file://..."
    if not uri:
        return ""
    plus_idx = uri.find('+')
    if plus_idx != -1 and uri[plus_idx+1:].startswith('file://'):
        return uri[plus_idx+1:]
    return uri

def load_config(config_path="config.toml"):
    with open(config_path, "rb") as f:
        return tomllib.load(f)

def copy_if_exists(src, dest):
    if os.path.exists(src):
        shutil.copy2(src, dest)
        return True
    return False

def copy_databases(config):
    metadb_src = config["source"]["metadb_path"]
    customdb_src = config["source"]["customdb_path"]
    target_dir = config["target"]["db_dir"]
    appdata_dir = os.path.dirname(metadb_src)

    # Check for WAL files
    metadb_wal = metadb_src + "-wal"
    customdb_wal = customdb_src + "-wal"
    is_wal = os.path.exists(metadb_wal) or os.path.exists(customdb_wal)
    is_temp = False

    if is_wal:
        # If WAL is detected, copy to a temp directory to ensure transaction safety
        temp_dir = tempfile.mkdtemp(prefix="fb2k_tmp_")
        target_dir = temp_dir
        is_temp = True
        print(f"WAL mode detected! Using temporary directory for copy: {temp_dir}")
    else:
        os.makedirs(target_dir, exist_ok=True)

    metadb_dest = os.path.join(target_dir, "metadb.sqlite")
    customdb_dest = os.path.join(target_dir, "customdb_sqlite.db")
    config_sqlite_dest = os.path.join(target_dir, "config.sqlite")

    # Copy primary files
    print(f"Copying {metadb_src} -> {metadb_dest} ...")
    shutil.copy2(metadb_src, metadb_dest)
    print(f"Copying {customdb_src} -> {customdb_dest} ...")
    shutil.copy2(customdb_src, customdb_dest)

    config_sqlite_src = os.path.join(appdata_dir, "config.sqlite")
    if os.path.exists(config_sqlite_src):
        print(f"Copying {config_sqlite_src} -> {config_sqlite_dest} ...")
        shutil.copy2(config_sqlite_src, config_sqlite_dest)
    else:
        config_sqlite_dest = None

    # Copy WAL and SHM files if they exist (crucial for SQLite to apply pending logs)
    for src_file in [metadb_src, customdb_src, config_sqlite_src]:
        if not os.path.exists(src_file):
            continue
        base_dest = os.path.join(target_dir, os.path.basename(src_file))
        copy_if_exists(src_file + "-wal", base_dest + "-wal")
        copy_if_exists(src_file + "-shm", base_dest + "-shm")

    return metadb_dest, customdb_dest, config_sqlite_dest, appdata_dir, is_temp, target_dir

def parse_fplite(fplite_path):
    results = []
    if not os.path.exists(fplite_path):
        return results
    try:
        with open(fplite_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t')
            fp = clean_filepath(parts[0])
            sub = 0
            if len(parts) > 1 and parts[1].isdigit():
                sub = int(parts[1])
            results.append((fp, sub))
    except Exception as e:
        print(f"Warning: Failed to parse fplite {fplite_path}: {e}")
    return results

def main():
    config = load_config()
    metadb_file, customdb_file, config_file, appdata_dir, is_temp, temp_dir = copy_databases(config)
    
    # Get current hostname
    hostname = socket.gethostname()
    print(f"Current Hostname: {hostname}")

    # 1. Load data from metadb.sqlite
    print("Loading data from metadb.sqlite...")
    meta_conn = sqlite3.connect(metadb_file)
    meta_cursor = meta_conn.cursor()

    # Load primary metadb tags
    tracks = {} # filepath -> track_data
    md5_to_filepath = {} # md5 -> filepath (to lookup for playlists)
    meta_cursor.execute("SELECT name, info, size FROM metadb WHERE info IS NOT NULL")
    for name, info, size in meta_cursor.fetchall():
        filepath = clean_pg_text(clean_filepath(name))
        if not filepath:
            continue
        
        md5_val = get_metadata_tag(info, "md5")
        if not md5_val or len(md5_val) != 32:
            continue
            
        md5_upper = md5_val.upper()
        tracks[filepath] = {
            'audio_md5': md5_upper,
            'filepath': filepath,
            'title': get_metadata_tag(info, "title"),
            'artist': get_metadata_tag(info, "artist"),
            'album': get_metadata_tag(info, "album"),
            'tracknumber': get_metadata_tag(info, "tracknumber"),
            'genre': get_metadata_tag(info, "genre"),
            'date': get_metadata_tag(info, "date"),
            'play_count': 0,
            'rating': None,
            'added_at': None,
            'first_played_at': None,
            'last_played_at': None,
            'lyrics_path': None,
            'lyrics_url': None
        }
        md5_to_filepath[md5_upper] = filepath
        # Also map without subsong prefix for fallback playlist resolution
        raw_fp = clean_pg_text(name.split('+')[-1] if '+' in name else name)
        md5_to_filepath[raw_fp] = filepath

    print(f"Loaded {len(tracks)} tracks with MD5 from metadb.")

    # Load playback statistics index (C653739F-14B3-4EF2-819B-A3E2883230AE)
    print("Loading playback statistics from metadb...")
    try:
        meta_cursor.execute("""
            SELECT idx.filename, dat.value 
            FROM metadb_index_C653739F_14B3_4EF2_819B_A3E2883230AE idx
            JOIN metadb_index_C653739F_14B3_4EF2_819B_A3E2883230AE_data dat ON idx.key = dat.key
        """)
        for filename, value in meta_cursor.fetchall():
            filepath = clean_pg_text(clean_filepath(filename))
            if filepath in tracks and value and len(value) == 40:
                play_count, added, last_played, first_played, _ = struct.unpack('<QQQQQ', value)
                tracks[filepath]['play_count'] = play_count
                tracks[filepath]['added_at'] = filetime_to_datetime(added)
                tracks[filepath]['last_played_at'] = filetime_to_datetime(last_played)
                tracks[filepath]['first_played_at'] = filetime_to_datetime(first_played)
    except Exception as e:
        print(f"Warning: Failed to load playback statistics: {e}")

    # Load rating index (915BEE72-FD1D-4CF8-90D4-8E2C18FD05BF)
    print("Loading ratings from metadb...")
    try:
        meta_cursor.execute("""
            SELECT idx.filename, dat.value 
            FROM metadb_index_915BEE72_FD1D_4CF8_90D4_8E2C18FD05BF idx
            JOIN metadb_index_915BEE72_FD1D_4CF8_90D4_8E2C18FD05BF_data dat ON idx.key = dat.key
        """)
        for filename, value in meta_cursor.fetchall():
            filepath = clean_pg_text(clean_filepath(filename))
            if filepath in tracks and value and len(value) >= 4:
                rating, = struct.unpack('<I', value[:4])
                tracks[filepath]['rating'] = rating
    except Exception as e:
        print(f"Warning: Failed to load ratings: {e}")

    # Load lyrics path (188A64AA-6C1B-4AC9-990A-067CD016F72C)
    print("Loading lyrics paths from metadb...")
    try:
        meta_cursor.execute("""
            SELECT idx.filename, dat.value 
            FROM metadb_index_188A64AA_6C1B_4AC9_990A_067CD016F72C idx
            JOIN metadb_index_188A64AA_6C1B_4AC9_990A_067CD016F72C_data dat ON idx.key = dat.key
        """)
        for filename, value in meta_cursor.fetchall():
            filepath = clean_pg_text(clean_filepath(filename))
            if filepath in tracks and value and len(value) > 8:
                try:
                    val = value[8:].decode('utf-8', errors='ignore')
                    tracks[filepath]['lyrics_path'] = clean_pg_text(val)
                except:
                    pass
    except Exception as e:
        print(f"Warning: Failed to load lyrics paths: {e}")

    # Load lyrics URLs (88DA8D97-B450-4FF4-A881-F6F6AD3836C1)
    print("Loading lyrics URLs from metadb...")
    try:
        meta_cursor.execute("""
            SELECT idx.filename, dat.value 
            FROM metadb_index_88DA8D97_B450_4FF4_A881_F6F6AD3836C1 idx
            JOIN metadb_index_88DA8D97_B450_4FF4_A881_F6F6AD3836C1_data dat ON idx.key = dat.key
        """)
        for filename, value in meta_cursor.fetchall():
            filepath = clean_pg_text(clean_filepath(filename))
            if filepath in tracks and value and len(value) > 28:
                try:
                    val = value[28:].decode('utf-8', errors='ignore')
                    tracks[filepath]['lyrics_url'] = clean_pg_text(val)
                except:
                    pass
    except Exception as e:
        print(f"Warning: Failed to load lyrics URLs: {e}")

    meta_conn.close()

    # 2. Load custom stats from customdb_sqlite.db
    print("Loading custom stats from customdb_sqlite.db...")
    custom_conn = sqlite3.connect(customdb_file)
    custom_cursor = custom_conn.cursor()

    filepath_added = {}
    custom_cursor.execute("SELECT url, value FROM quicktag WHERE fieldname = 'ADDED_CD'")
    for url, value in custom_cursor.fetchall():
        filepath = clean_pg_text(clean_filepath(url))
        dt = parse_iso_datetime(value)
        if filepath and dt:
            filepath_added[filepath] = dt

    artist_album_title_stats = {}
    custom_cursor.execute("""
        SELECT url, fieldname, value 
        FROM quicktag 
        WHERE fieldname IN ('PLAY_COUNT_CD', 'FIRST_PLAYED_CD', 'LAST_PLAYED_CD')
    """)
    for key, fieldname, value in custom_cursor.fetchall():
        if not key or not value:
            continue
        cleaned_key = clean_pg_text(key)
        if cleaned_key not in artist_album_title_stats:
            artist_album_title_stats[cleaned_key] = {}
        artist_album_title_stats[cleaned_key][fieldname] = clean_pg_text(value)

    custom_conn.close()

    # 3. Merge custom stats into tracks
    print("Merging custom stats into tracks...")
    track_by_tag_key = {}
    for filepath, track in tracks.items():
        artist = track['artist'] or ""
        album = track['album'] or ""
        title = track['title'] or ""
        tag_key = f"{artist},{album},{title}"
        if tag_key not in track_by_tag_key:
            track_by_tag_key[tag_key] = []
        track_by_tag_key[tag_key].append(track)

    for filepath, added_dt in filepath_added.items():
        if filepath in tracks:
            current_added = tracks[filepath]['added_at']
            if current_added is None or added_dt < current_added:
                tracks[filepath]['added_at'] = added_dt

    for tag_key, stats in artist_album_title_stats.items():
        if tag_key in track_by_tag_key:
            matched_tracks = track_by_tag_key[tag_key]
            pc_val = stats.get('PLAY_COUNT_CD')
            pc = int(pc_val) if pc_val and pc_val.isdigit() else 0
            fp_dt = parse_iso_datetime(stats.get('FIRST_PLAYED_CD'))
            lp_dt = parse_iso_datetime(stats.get('LAST_PLAYED_CD'))
            
            for track in matched_tracks:
                track['play_count'] = max(track['play_count'], pc)
                if fp_dt:
                    if track['first_played_at'] is None or fp_dt < track['first_played_at']:
                        track['first_played_at'] = fp_dt
                if lp_dt:
                    if track['last_played_at'] is None or lp_dt > track['last_played_at']:
                        track['last_played_at'] = lp_dt

    # 4. Load playlists from playlists-v2.0/
    print("Loading playlists...")
    playlist_list = []      # list of (playlist_id, hostname, name)
    playlist_tracks = []    # list of (playlist_id, hostname, track_index, audio_md5, subsong)
    
    playlists_dir = os.path.join(appdata_dir, "playlists-v2.0")
    playlists_index = os.path.join(playlists_dir, "index.txt")
    
    if os.path.exists(playlists_index):
        try:
            with open(playlists_index, "r", encoding="utf-8-sig", errors="ignore") as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip()
                if not line or ':' not in line:
                    continue
                pl_id, pl_name = line.split(':', 1)
                pl_id = clean_pg_text(pl_id.strip())
                pl_name = clean_pg_text(pl_name.strip())
                
                playlist_list.append((pl_id, hostname, pl_name))
                
                # Parse fplite file
                fplite_file = os.path.join(playlists_dir, f"playlist-{pl_id}.fplite")
                fpl_tracks = parse_fplite(fplite_file)
                
                for idx, (fp, subsong) in enumerate(fpl_tracks):
                    # Lookup audio_md5 via filepath
                    audio_md5 = None
                    if fp in tracks:
                        audio_md5 = tracks[fp]['audio_md5']
                    elif fp in md5_to_filepath:
                        resolved_fp = md5_to_filepath[fp]
                        audio_md5 = tracks[resolved_fp]['audio_md5']
                        
                    if audio_md5:
                        playlist_tracks.append((pl_id, hostname, idx, audio_md5, subsong))
            print(f"Loaded {len(playlist_list)} playlists containing {len(playlist_tracks)} tracks.")
        except Exception as e:
            print(f"Warning: Failed to load playlists: {e}")

    # 5. Load plugins from user-components-x64/
    print("Loading installed plugins...")
    plugin_list = [] # list of (hostname, plugin_name)
    components_dir = os.path.join(appdata_dir, "user-components-x64")
    if os.path.exists(components_dir):
        try:
            for item in os.listdir(components_dir):
                item_path = os.path.join(components_dir, item)
                if os.path.isdir(item_path):
                    plugin_list.append((hostname, clean_pg_text(item)))
            print(f"Found {len(plugin_list)} installed plugins.")
        except Exception as e:
            print(f"Warning: Failed to scan plugins: {e}")

    # 6. Load configs from config.sqlite
    print("Loading configurations...")
    config_list = [] # list of (hostname, config_key, config_val)
    if config_file and os.path.exists(config_file):
        try:
            cfg_conn = sqlite3.connect(config_file)
            cfg_cursor = cfg_conn.cursor()
            cfg_cursor.execute("SELECT name, value FROM configStrings")
            for name, value in cfg_cursor.fetchall():
                config_list.append((hostname, clean_pg_text(name), clean_pg_text(value)))
            cfg_conn.close()
            print(f"Loaded {len(config_list)} configuration strings.")
        except Exception as e:
            print(f"Warning: Failed to load configs: {e}")

    # 7. Ingest into Postgres
    db_url = config["database"]["url"]
    print(f"Connecting to Postgres: {db_url.split('@')[-1]} ...")
    
    # Collect tracks and stats
    track_insert_data = []
    stats_insert_data = []
    
    for track in tracks.values():
        track_insert_data.append((
            track['audio_md5'],
            track['filepath'],
            track['title'],
            track['artist'],
            track['album'],
            track['tracknumber'],
            track['genre'],
            track['date']
        ))
        stats_insert_data.append((
            track['audio_md5'],
            hostname,
            track['play_count'],
            track['rating'],
            track['added_at'],
            track['first_played_at'],
            track['last_played_at'],
            track['lyrics_path'],
            track['lyrics_url']
        ))

    print(f"Ingesting into PostgreSQL ({hostname})...")
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                # 1. Upsert Hosts
                print("  Ingesting raw.foobar2000_hosts...")
                cur.execute("""
                    INSERT INTO raw.foobar2000_hosts (hostname, updated_at) 
                    VALUES (%s, CURRENT_TIMESTAMP)
                    ON CONFLICT (hostname) DO UPDATE SET updated_at = CURRENT_TIMESTAMP;
                """, (hostname,))

                # 2. Bulk Upsert Tracks (Shared drive/filepath - duplicate audio_md5 will update filepath/tags)
                print("  Ingesting raw.foobar2000_tracks...")
                tracks_query = """
                    INSERT INTO raw.foobar2000_tracks (
                        audio_md5, filepath, title, artist, album, tracknumber, genre, date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (audio_md5) DO UPDATE SET
                        filepath = EXCLUDED.filepath,
                        title = EXCLUDED.title,
                        artist = EXCLUDED.artist,
                        album = EXCLUDED.album,
                        tracknumber = EXCLUDED.tracknumber,
                        genre = EXCLUDED.genre,
                        date = EXCLUDED.date,
                        updated_at = CURRENT_TIMESTAMP;
                """
                batch_size = 2000
                for i in range(0, len(track_insert_data), batch_size):
                    batch = track_insert_data[i:i+batch_size]
                    cur.executemany(tracks_query, batch)
                
                # 3. Bulk Upsert Stats (Host-specific stats)
                print("  Ingesting raw.foobar2000_stats...")
                stats_query = """
                    INSERT INTO raw.foobar2000_stats (
                        audio_md5, hostname, play_count, rating, added_at, first_played_at, last_played_at,
                        lyrics_path, lyrics_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (audio_md5, hostname) DO UPDATE SET
                        play_count = EXCLUDED.play_count,
                        rating = EXCLUDED.rating,
                        added_at = EXCLUDED.added_at,
                        first_played_at = EXCLUDED.first_played_at,
                        last_played_at = EXCLUDED.last_played_at,
                        lyrics_path = EXCLUDED.lyrics_path,
                        lyrics_url = EXCLUDED.lyrics_url,
                        updated_at = CURRENT_TIMESTAMP;
                """
                for i in range(0, len(stats_insert_data), batch_size):
                    batch = stats_insert_data[i:i+batch_size]
                    cur.executemany(stats_query, batch)

                # 4. Bulk Upsert Playlists
                if playlist_list:
                    print("  Ingesting raw.foobar2000_playlists...")
                    pl_query = """
                        INSERT INTO raw.foobar2000_playlists (playlist_id, hostname, name)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (playlist_id, hostname) DO UPDATE SET
                            name = EXCLUDED.name,
                            updated_at = CURRENT_TIMESTAMP;
                    """
                    cur.executemany(pl_query, playlist_list)

                # 5. Bulk Upsert Playlist Tracks
                if playlist_tracks:
                    print("  Ingesting raw.foobar2000_playlist_tracks...")
                    # First, clear playlist tracks for this host to refresh membership order
                    pl_ids = list(set([p[0] for p in playlist_list]))
                    for pl_id in pl_ids:
                        cur.execute("DELETE FROM raw.foobar2000_playlist_tracks WHERE playlist_id = %s AND hostname = %s", (pl_id, hostname))
                    
                    pl_tracks_query = """
                        INSERT INTO raw.foobar2000_playlist_tracks (playlist_id, hostname, track_index, audio_md5, subsong)
                        VALUES (%s, %s, %s, %s, %s);
                    """
                    # Direct insert after deletion to maintain exact sequence
                    cur.executemany(pl_tracks_query, playlist_tracks)

                # 6. Bulk Upsert Plugins
                if plugin_list:
                    print("  Ingesting raw.foobar2000_plugins...")
                    cur.execute("DELETE FROM raw.foobar2000_plugins WHERE hostname = %s", (hostname,))
                    plugin_query = """
                        INSERT INTO raw.foobar2000_plugins (hostname, plugin_name)
                        VALUES (%s, %s);
                    """
                    cur.executemany(plugin_query, plugin_list)

                # 7. Bulk Upsert Configs
                if config_list:
                    print("  Ingesting raw.foobar2000_configs...")
                    cur.execute("DELETE FROM raw.foobar2000_configs WHERE hostname = %s", (hostname,))
                    cfg_query = """
                        INSERT INTO raw.foobar2000_configs (hostname, config_key, config_val)
                        VALUES (%s, %s, %s);
                    """
                    # Batch configuration insert
                    for i in range(0, len(config_list), batch_size):
                        batch = config_list[i:i+batch_size]
                        cur.executemany(cfg_query, batch)
                        
            conn.commit()
        print("Ingestion completed successfully!")
        if is_temp and os.path.exists(temp_dir):
            print(f"Cleaning up temporary directory: {temp_dir} ...")
            shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"Error during ingestion: {e}", file=sys.stderr)
        if is_temp and os.path.exists(temp_dir):
            print(f"Cleaning up temporary directory after error: {temp_dir} ...")
            shutil.rmtree(temp_dir)
        sys.exit(1)

if __name__ == '__main__':
    main()
