# Metadata Requirements by Platform

Character limits, required fields, and specifications for each platform.

---

## Album Metadata

### Title Limits

| Platform | Max Characters | Notes |
|----------|----------------|-------|
| Spotify | 200 | Avoid special characters |
| Apple Music | 255 | Clean formatting required |
| YouTube Music | 100 | Shorter for display |
| SoundCloud | 100 | Tags help discovery |
| Bandcamp | 200 | Can be longer in practice |
| Distributors | 100-200 | Check specific distributor |

**Best practice**: Keep album titles under 50 characters for display on all platforms.

### Required Album Fields

| Field | Spotify | Apple | YouTube | SoundCloud | Bandcamp |
|-------|---------|-------|---------|------------|----------|
| Title | Yes | Yes | Yes | Yes | Yes |
| Artist | Yes | Yes | Yes | Yes | Yes |
| Genre | Yes | Yes | Yes | Yes | Yes |
| Release date | Yes | Yes | Yes | Optional | Optional |
| UPC | Via dist. | Via dist. | Via dist. | No | No |
| Copyright | Via dist. | Yes | Via dist. | Optional | Yes |
| Explicit flag | Yes | Yes | Yes | No | Optional |

---

## Track Metadata

### Title Limits

| Platform | Max Characters |
|----------|----------------|
| All platforms | 100-200 |
| Display limit | ~30-40 (truncated) |

**Best practice**: Keep track titles under 40 characters.

### Required Track Fields

| Field | Required | Notes |
|-------|----------|-------|
| Title | Yes | No featuring artist in title |
| Artist | Yes | Primary artist |
| Featured artist | If applicable | Separate field |
| Track number | Yes | Sequential, no gaps |
| ISRC | Via distributor | Unique per track |
| Explicit | Yes | Per track |
| Lyrics | Recommended | For Spotify/Apple |

---

## Description/Bio Limits

### Album Description

| Platform | Max Characters | Displayed |
|----------|----------------|-----------|
| Spotify | N/A | Artist bio only |
| Apple Music | 4000 | Editorial notes |
| YouTube | 5000 | Video description |
| SoundCloud | 4000 | Yes |
| Bandcamp | Unlimited | Yes |

### Artist Bio

| Platform | Max Characters |
|----------|----------------|
| Spotify | 1500 |
| Apple Music | 1000 |
| SoundCloud | 4000 |
| Bandcamp | Unlimited |

---

## Album Art Specifications

### Dimensions

| Platform | Minimum | Recommended | Maximum |
|----------|---------|-------------|---------|
| Spotify | 640x640 | 3000x3000 | 3000x3000 |
| Apple Music | 3000x3000 | 3000x3000 | 4000x4000 |
| YouTube Music | 1400x1400 | 3000x3000 | - |
| SoundCloud | 800x800 | 800x800 | 8000x8000 |
| Bandcamp | 1400x1400 | 3000x3000 | - |

**Best practice**: Always use 3000x3000px for universal compatibility.

### Format and Size

| Platform | Format | Max File Size |
|----------|--------|---------------|
| Spotify | JPG, PNG | 20MB |
| Apple Music | JPG only | 40MB |
| YouTube | JPG, PNG | 20MB |
| SoundCloud | JPG, PNG | 2MB |
| Bandcamp | JPG, PNG, GIF | 10MB |

### Album Art Rules

**Allowed**:
- Original artwork
- Licensed images
- AI-generated art (with disclosure if required)
- Text (album title, artist name)

**Not allowed**:
- Blurry/pixelated images
- Excessive text
- Contact information (URLs, social handles)
- Explicit imagery without flag
- Copyright-infringing content
- Platform logos

---

## Genre and Tag Requirements

### Primary Genre

| Platform | Selection Method |
|----------|------------------|
| Spotify | Dropdown (limited) |
| Apple Music | Dropdown (strict) |
| YouTube | Free text + category |
| SoundCloud | Dropdown + tags |
| Bandcamp | Dropdown + tags |

### Genre Categories (Distributors)

**Primary Genre**: Main classification (Electronic, Hip-Hop, Rock, etc.)

**Secondary Genre**: Subgenre (House, Trap, Alternative, etc.)

**Check distributor's genre list** - varies by platform.

### Tags

| Platform | Max Tags | Character Limit |
|----------|----------|-----------------|
| SoundCloud | 5 | 25 per tag |
| Bandcamp | Unlimited | - |
| YouTube | 500 chars total | - |

**Effective tags**: Genre, subgenre, mood, similar artists (style, not name), tempo.

---

## Lyrics Requirements

### Format by Platform

| Platform | Format | Sync Required |
|----------|--------|---------------|
| Spotify | Plain text | Timed optional |
| Apple Music | Plain text | Timed optional |
| Amazon Music | Plain text | No |
| YouTube | Subtitles (SRT/VTT) | Yes |

### Lyrics Guidelines

- No section labels ([Verse], [Chorus])
- No performer annotations
- Write out repeats
- Capitalize first letter of lines
- No ending punctuation
- Blank lines between sections only

See `/reference/distribution.md` for full streaming lyrics format.

---

## Pre-Save Campaign Requirements

| Platform | Lead Time | Via |
|----------|-----------|-----|
| Spotify | 4+ weeks | Distributor + SmartURL |
| Apple Music | 4+ weeks | Distributor |
| Deezer | 2+ weeks | Distributor |

**Required for pre-save**: Future release date, album art, basic metadata.

---

## Common Rejection Reasons

### Metadata Issues

- Title contains featuring artist (use separate field)
- Special characters in title
- ALL CAPS formatting
- Version info in wrong field ("Remix" in title vs version field)
- Mismatch between metadata and audio content

### Artwork Issues

- Wrong dimensions or resolution
- Blurry or pixelated
- Contains URLs or QR codes
- Explicit content without flag
- Copyright issues

### Audio Issues

- Silence at start/end (>3 seconds)
- Clipping or distortion
- Low-quality source file
- Mismatched track count

---

## Metadata Checklist

**Before submission**:

- [ ] Album title under 50 characters
- [ ] Track titles under 40 characters
- [ ] Album art 3000x3000px JPG
- [ ] All explicit flags correct
- [ ] Lyrics formatted (no section labels)
- [ ] Genre categories match content
- [ ] Release date set (if scheduling)
- [ ] Copyright info accurate
- [ ] Featured artists in correct field
- [ ] No special characters causing issues

---

## Platform-Specific Notes

**Spotify**: Artist profile verification recommended. Canvas videos increase engagement.

**Apple Music**: Strictest metadata requirements. Clean, professional formatting required.

**YouTube Music**: Needs video component. Static image Art Tracks work but limited features.

**SoundCloud**: Tags critical for discovery. Description supports markdown.

**Bandcamp**: Most flexible. Rich album pages with credits, liner notes, lyrics.
