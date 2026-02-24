# Sheet Music Distribution Guide

Guide for distributing sheet music via your website and other platforms.

## Overview

**What you're distributing**: Piano arrangements (sheet music) as individual singles and a combined songbook

**Primary method**: Free download from your website

**File formats**:
| Format | Extension | Purpose |
|--------|-----------|---------|
| **PDF** | `.pdf` | Viewing and printing — universal, works everywhere |
| **MusicXML** | `.xml` | Editing in MuseScore, Finale, Sibelius — for musicians who want to customize |
| **MIDI** | `.mid` | Playback and practice — import into any DAW or notation software |

**Alternative platforms** (optional):
- Sheet Music Plus — digital marketplace
- Musicnotes — digital sheet music store
- Your own website — direct downloads (recommended)

---

## Website Distribution

### Recommended Setup

Host sheet music as free downloads on your website alongside the album.

**Per-track downloads** (from `singles/` directory):
- PDF — for viewing/printing
- MusicXML — for editing
- MIDI — for playback

**Complete songbook** (from `songbook/` directory):
- Single PDF with title page, copyright, TOC, all tracks

### File Organization for Upload

The pipeline produces a clean directory structure:

```
sheet-music/
├── source/          # Working files (don't distribute)
├── singles/         # Upload these — one set per track
│   ├── Ocean of Tears.pdf
│   ├── Ocean of Tears.xml
│   ├── Ocean of Tears.mid
│   ├── Run Away.pdf
│   ├── Run Away.xml
│   ├── Run Away.mid
│   └── ...
└── songbook/
    └── Album Name - Complete Songbook.pdf
```

Upload everything from `singles/` and `songbook/` to your website. Don't upload `source/` — those are working files with track number prefixes.

### Website Page Structure

**Album sheet music page should include:**
- Brief description ("Free piano arrangements from [Album Name]")
- Per-track download links (PDF, XML, MIDI for each)
- Complete songbook download link
- Link to listen to the album
- Credit line: "Transcribed using AnthemScore, edited with MuseScore"

### Hosting Options

**Static site / existing website:**
- Upload files to your web host
- Link directly to PDFs
- Simplest approach

**GitHub Pages / Netlify:**
- Free hosting for static files
- Version control built in
- Good for musician-developers

**Bandcamp:**
- Can include sheet music as bonus content with album purchase
- Or offer as free download

---

## Preparing Your Songbook

### Use the create_songbook MCP tool

```
create_songbook(album_slug, title="Album Name - Complete Songbook", page_size="letter")
```

**Output includes:**
- Title page (with album art)
- Copyright page
- Table of contents (track names + page numbers)
- All tracks in order

### Front Matter Checklist

**Title page** (auto-generated):
- Book title
- Artist/composer name
- Subtitle (e.g., "Piano Arrangements")
- Album artwork (if provided)
- Website URL
- Year

**Copyright page** (auto-generated):
- Copyright notice
- Free distribution statement
- Transcription credits
- Website/contact info

**Table of Contents** (auto-generated):
- Track names with page numbers
- Leader dots for readability

### Page Size

| Size | Dimensions | Best For |
|------|------------|----------|
| **Letter** | 8.5" x 11" | Standard US sheet music |
| **9" x 12"** | 9" x 12" | Professional sheet music |
| 6" x 9" | 6" x 9" | Compact/travel size |

**Most common**: Letter (8.5" x 11") for home printing

---

## Legal & Copyright

### Copyright Ownership

**If you wrote the songs:**
- You own the copyright to music and lyrics
- Sheet music is a derivative work you also own
- You can distribute freely

**If you sampled or covered songs:**
- You do NOT own copyright
- Cannot distribute without permission
- Not applicable for original music

### Copyright Notice

**Included in songbook automatically:**
```
© 2026 Your Artist Name.

This songbook is a free companion to the album.
Share freely. Credit appreciated.

Piano arrangements transcribed using AnthemScore.
Notation edited with MuseScore.
```

### Creative Commons (Optional)

Consider adding a Creative Commons license for clear sharing terms:
- **CC BY** — anyone can use/share with credit
- **CC BY-NC** — non-commercial use with credit
- **CC BY-SA** — share-alike with credit

---

## Alternative Platforms

### Sheet Music Plus

**Website**: [sheetmusicplus.com](https://www.sheetmusicplus.com/)

- Digital marketplace for sheet music
- Sellers upload PDFs (individual tracks or books)
- Revenue split: ~70% to creator
- Best for: reaching sheet music enthusiasts

### Musicnotes

**Website**: [musicnotes.com](https://www.musicnotes.com/)

- Similar to Sheet Music Plus
- May require sample work for approval
- Digital marketplace with instant downloads

### Print-on-Demand (Optional)

If you want physical copies available:
- Amazon KDP — print books, no upfront cost
- Lulu — print-on-demand
- Blurb — premium quality

These are optional — the primary distribution method is free digital download.

---

## Licensing Considerations

### Sync Licensing

**Sheet music adds value** to licensing packages:
- Shows professionalism
- Useful for music supervisors (TV/film)
- Helps arrangers/cover artists

### Educational Use

**Educators may use your sheet music** for teaching:
- Make sure notation is accurate
- Include difficulty level in description
- Free distribution makes this more accessible

---

## Checklist: Publishing Sheet Music

**Before distributing:**
- [ ] Singles prepared (clean titles, all 3 formats)
- [ ] Songbook PDF finalized (optional)
- [ ] Copyright notice included
- [ ] Album art on title page
- [ ] Track titles clean (no number prefixes)
- [ ] Review PDFs for readability

**Website setup:**
- [ ] Upload singles (PDF, XML, MIDI per track)
- [ ] Upload songbook PDF
- [ ] Create download page with track listing
- [ ] Add link to album streaming page
- [ ] Test all download links

**Promotion:**
- [ ] Announce on social media
- [ ] Add link to album descriptions
- [ ] Mention in YouTube video descriptions
- [ ] Post sample page images

---

## Summary

**Sheet music distribution workflow:**

1. Generate sheet music with transcribe_audio (outputs to source/)
2. Prepare singles with prepare_singles (outputs to singles/)
3. Create songbook with create_songbook (outputs to songbook/)
4. Review all PDFs for quality
5. Upload to your website
6. Announce and promote

**Benefits:**
- Serves fans and musicians
- Adds value to licensing packages
- Professional presence
- Free distribution builds goodwill
