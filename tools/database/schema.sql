-- bitwize-music Plugin — Database Schema
--
-- PostgreSQL schema for social media post management.
-- Run manually:   psql -h HOST -U USER -d DBNAME -f tools/database/schema.sql
-- Or use MCP tool: db_init (auto-creates tables if they don't exist)
--
-- Tables:
--   albums  — Album metadata (synced from plugin markdown state)
--   tracks  — Track metadata (synced from plugin markdown state)
--   tweets  — Social media posts linked to albums/tracks (multi-platform)

-- =========================================================================
-- ALBUMS
-- =========================================================================
CREATE TABLE IF NOT EXISTS albums (
    id               SERIAL PRIMARY KEY,
    slug             TEXT NOT NULL UNIQUE,
    title            TEXT NOT NULL,
    genre            TEXT NOT NULL,
    concept          TEXT,
    track_count      INTEGER NOT NULL DEFAULT 0,
    release_date     DATE,
    explicit         BOOLEAN DEFAULT FALSE,
    status           TEXT DEFAULT 'Unknown',
    soundcloud_url   TEXT,
    spotify_url      TEXT,
    apple_music_url  TEXT,
    amazon_music_url TEXT,
    bandcamp_url     TEXT,
    youtube_url      TEXT,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);

-- =========================================================================
-- TRACKS
-- =========================================================================
CREATE TABLE IF NOT EXISTS tracks (
    id           SERIAL PRIMARY KEY,
    album_id     INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    track_number INTEGER NOT NULL,
    slug         TEXT,
    title        TEXT NOT NULL,
    concept      TEXT,
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE (album_id, track_number)
);

CREATE UNIQUE INDEX IF NOT EXISTS tracks_album_id_slug_key ON tracks (album_id, slug);
CREATE INDEX IF NOT EXISTS idx_tracks_album_id ON tracks (album_id);

-- =========================================================================
-- TWEETS (multi-platform social media posts)
-- =========================================================================
CREATE TABLE IF NOT EXISTS tweets (
    id           SERIAL PRIMARY KEY,
    album_id     INTEGER REFERENCES albums(id) ON DELETE CASCADE,
    track_id     INTEGER REFERENCES tracks(id) ON DELETE CASCADE,
    tweet_text   TEXT NOT NULL,
    platform     TEXT DEFAULT 'twitter',
    content_type TEXT DEFAULT 'promo',
    media_path   TEXT,
    posted       BOOLEAN DEFAULT FALSE,
    enabled      BOOLEAN DEFAULT FALSE,
    times_posted INTEGER DEFAULT 0,
    created_at   TIMESTAMPTZ DEFAULT now(),
    posted_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tweets_album_id ON tweets (album_id);
CREATE INDEX IF NOT EXISTS idx_tweets_track_id ON tweets (track_id);
CREATE INDEX IF NOT EXISTS idx_tweets_platform ON tweets (platform);
CREATE INDEX IF NOT EXISTS idx_tweets_posted ON tweets (posted);
CREATE INDEX IF NOT EXISTS idx_tweets_enabled ON tweets (enabled);
