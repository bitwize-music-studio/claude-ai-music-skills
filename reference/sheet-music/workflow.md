# Sheet Music Generation Workflow

Complete guide for converting mastered audio to publishing-quality piano reductions.

## Overview

**Pipeline**: WAV → AnthemScore CLI (automated) → MusicXML/PDF → MuseScore (polish) → Final PDF

**Time estimate**:
- Automated batch: ~30-60 seconds per track
- Manual polish in MuseScore: 5-30 minutes per track (if needed)

**Accuracy expectation**: 70-95% depending on arrangement density

---

## Quick Start (Automated)

```bash
# Batch transcribe all WAVs in a folder
./tools/sheet-music/transcribe.sh /path/to/mastered/

# Single track
./tools/sheet-music/transcribe.sh /path/to/track.wav

# PDF only (skip MusicXML)
./tools/sheet-music/transcribe.sh /path/to/mastered/ --pdf-only

# With MIDI files
./tools/sheet-music/transcribe.sh /path/to/mastered/ --midi
```

**Output**: Creates `sheet-music/source/` folder with PDFs, MusicXML, and MIDI files.

---

## Software Setup

### AnthemScore (Required)

**Website**: [lunaverus.com](https://www.lunaverus.com/)

**Editions**:
| Edition | Price | Features |
|---------|-------|----------|
| Lite | $31 | Basic transcription, no editing |
| **Professional** | $42 | Full editing, spectrogram view (recommended) |
| Studio | $107 | Lifetime updates |

**Installation**:
1. Purchase and download from website
2. Available for Windows, Mac, and Linux
3. No subscription - buy once, use forever
4. Free trial: 30 seconds per song, 100 total transcriptions

**Key features**:
- Neural network-based note detection
- Spectrogram visualization
- Adjustable sensitivity slider
- Beat and tempo detection
- Export to PDF, MusicXML, MIDI
- **Full CLI support for automation**

**macOS location**: `/Applications/AnthemScore.app/Contents/MacOS/AnthemScore`

### MuseScore (Required)

**Website**: [musescore.org](https://musescore.org/)

**Cost**: Free, open source

**Installation**:
1. Download from website
2. Available for Windows, Mac, Linux
3. No account required

**Key features**:
- Professional notation editing
- MusicXML import/export
- PDF export
- MIDI playback
- Extensive plugin ecosystem

---

## Detailed Workflow

### Phase 1: Preparation

**Select tracks to transcribe**:
- Melodic tracks work best (clear vocal/instrumental lines)
- Avoid dense electronic arrangements
- Consider which tracks benefit from sheet music (licensing, covers)

**Organize source files**:
```
album/
├── mastered/                    # Source WAVs
│   ├── 01-track.wav
│   └── 02-track.wav
└── sheet-music/                 # Output location
    ├── source/                  # AnthemScore output (auto-created)
    ├── singles/                 # Clean-titled consumer files
    │   └── .manifest.json
    └── songbook/                # Combined songbook PDF
```

### Phase 2: Transcription in AnthemScore

**Opening the file**:
1. Launch AnthemScore
2. File → Open
3. Select mastered WAV file
4. Wait for initial analysis (30-60 seconds)

**Understanding the interface**:
- **Spectrogram** (top): Frequency over time - bright = loud
- **Keyboard** (left): Piano roll visualization
- **Staff** (bottom): Generated notation

**Adjusting transcription**:

| Setting | Purpose | Typical Value |
|---------|---------|---------------|
| Note Sensitivity | More/fewer notes detected | Start at 50%, adjust |
| Min Note Length | Filter short notes | 0.1-0.2 seconds |
| Instrument | Target transcription type | Piano |

**Sensitivity tuning**:
- Too high: Ghost notes (false positives)
- Too low: Missing notes
- Find the sweet spot where melody is clear

**Manual corrections**:
- Click notes to select
- Delete key removes notes
- Click + drag to add notes
- Adjust duration by dragging edges

**Export**:
1. File → Export As → MusicXML (.musicxml)
2. Also export PDF for reference
3. Also export MIDI for playback verification

### Phase 3: Polish in MuseScore

**Import**:
1. File → Open
2. Select MusicXML file
3. Review import settings (usually defaults are fine)

**Essential checks**:

| Check | How to Fix |
|-------|------------|
| Key signature | Edit → Key Signature (or K shortcut) |
| Time signature | Edit → Time Signature (or T shortcut) |
| Tempo | Add → Text → Tempo Marking |
| Clef | Right-click staff → Staff/Part Properties |

**Notation cleanup**:
- Fix note durations (select note, use number keys 4-7)
- Add rests to complete measures
- Tie notes that should be connected
- Beam/unbeam eighth notes appropriately

**Performance markings**:
- Dynamics: Add → Dynamics (p, mf, f)
- Articulations: Select note, double-click palette item
- Pedal: Lines → Pedal

**Formatting**:
- Format → Style → adjust spacing
- Add page breaks: select barline → break icon
- Title/composer: File → Score Properties

### Phase 4: Final Export

**PDF settings**:
1. File → Export → PDF
2. Resolution: 300 DPI (print quality)
3. Page size: Letter (US) or A4 (international)

**Review checklist**:
- [ ] All pages readable
- [ ] Page turns at sensible positions
- [ ] Title and credits visible
- [ ] No notation collisions
- [ ] Playable by a pianist

**Save MuseScore project**:
- File → Save As → .mscz format
- This is your editable source for future changes

---

## Tips for Better Results

### Audio Quality

**Better source = better transcription**:
- Use mastered WAV (not MP3)
- Ensure track is not clipping
- Clear, well-mixed audio transcribes better

### Track Selection

**Transcribes well**:
- Solo vocals with simple accompaniment
- Acoustic folk/singer-songwriter
- Clear melody-driven pop
- Piano-based songs

**Challenging**:
- Dense rock with multiple guitars
- Electronic music with synth pads
- Songs with heavy distortion
- Rapid-fire rap vocals

### Piano Reduction Philosophy

**Goal**: Playable arrangement that captures the song's essence

**Approach**:
- Melody in right hand (usually)
- Bass line + harmony in left hand
- Simplify complex passages
- Don't try to transcribe everything

**What to keep**:
- Main melody
- Bass line
- Characteristic riffs/hooks
- Harmonic structure

**What to simplify/omit**:
- Drum patterns
- Doubled/layered parts
- Complex background vocals
- Sound effects

---

## Stem Separation (Advanced)

For complex tracks, separating stems first can dramatically improve accuracy.

### Using Demucs

**Install**:
```bash
pip install demucs
```

**Run separation**:
```bash
demucs /path/to/track.wav
```

**Output** (in `separated/htdemucs/track/`):
- `vocals.wav` - isolated vocals
- `drums.wav` - percussion
- `bass.wav` - bass line
- `other.wav` - everything else (guitars, synths, etc.)

### Transcription Strategy with Stems

1. **Transcribe bass.wav** → bass clef part
2. **Transcribe other.wav** → treble clef part (melody, chords)
3. **Combine in MuseScore** → full piano reduction

**When to use**:
- Dense rock/pop arrangements
- Songs where melody is buried in mix
- Professional licensing needs (accuracy matters)

**When not needed**:
- Simple acoustic tracks
- Clear vocal + piano songs
- Quick reference transcriptions

---

## Troubleshooting

### "Transcription is a mess"

**Diagnose**: Too many overlapping instruments

**Fix**:
1. Lower sensitivity slider significantly
2. Focus on dominant melody only
3. Consider stem separation
4. Or: Accept this track isn't suitable for auto-transcription

### "Notes are in wrong octave"

**Diagnose**: AI confused by harmonics or low-quality audio

**Fix**:
1. Select notes in MuseScore
2. Ctrl/Cmd + Up/Down arrow to shift octave
3. Verify against original audio

### "Rhythm is incorrect"

**Diagnose**: Syncopation, swing, or complex timing confused the AI

**Fix**:
1. Listen to original while following transcription
2. Manually re-notate problem measures
3. Use MIDI playback to verify

### "Key signature is wrong"

**Diagnose**: AI detection isn't perfect, especially for modes

**Fix**:
1. Listen to original, identify correct key
2. In MuseScore: Edit → Key Signature
3. May need to transpose all notes if fundamentally wrong

### "Page turns are awkward"

**Fix in MuseScore**:
1. Select barline before desired page break
2. Add → Breaks & Spacers → Page Break
3. Or use Layout → Add/Remove System Breaks

---

## File Organization

### Storage Locations

**Released albums**:
```
artists/[artist]/released/[genre]/[album]/sheet-music/
```

**In-progress albums**:
```
artists/[artist]/albums/[genre]/[album]/sheet-music/
```

### Naming Convention

**Source files** (in `source/`):
```
01-track-name.pdf        # AnthemScore output
01-track-name.xml        # MusicXML source
01-track-name.mid        # MIDI file
```

**Singles** (in `singles/` — consumer-ready):
```
Track Name.pdf           # Clean-titled PDF
Track Name.xml           # Clean-titled MusicXML
Track Name.mid           # Clean-titled MIDI
.manifest.json           # Track ordering
```

### What to Keep

| File | Keep? | Why |
|------|-------|-----|
| PDF | Yes | Publishing deliverable |
| .mscz | Yes | Source for future edits |
| .mid | Optional | Playback verification |
| .musicxml | Optional | Software interchange |
| Original WAV | Already have | In mastered/ folder |

---

## Publishing Considerations

### Copyright

- Sheet music is a derivative work
- You own copyright if you created the original song
- Include copyright notice on PDF: "© Year Artist Name"

### Licensing

**For sync licensing**:
- PDF sheet music can be included in licensing package
- Shows professionalism
- Useful for TV/film music supervisors

**For distribution**:
- Can sell sheet music separately (Sheet Music Plus, Musicnotes)
- Or include with album purchase
- Consider simplified vs. "as performed" versions

### Quality Expectations

**Professional standard**:
- Clean, readable notation
- Correct key/time signatures
- Appropriate dynamics and articulations
- Playable by intermediate pianist
- Proper credits and copyright

**Minimum viable**:
- Correct notes
- Readable layout
- Basic structure (verse, chorus labeled)
- Title and composer

---

## Quick Reference

### AnthemScore Shortcuts

| Action | How |
|--------|-----|
| Play/pause | Space |
| Zoom | Mouse wheel |
| Add note | Click on spectrogram |
| Delete note | Select + Delete |
| Adjust sensitivity | Slider (bottom) |

### MuseScore Shortcuts

| Action | Shortcut |
|--------|----------|
| Note input | N |
| Select all | Ctrl/Cmd + A |
| Transpose | Tools → Transpose |
| Add dynamic | Ctrl/Cmd + E (expression) |
| Octave up/down | Ctrl/Cmd + Up/Down |
| Play | Space |

### Workflow Summary

**Automated (preferred)**:
```
1. Transcribe: python3 tools/sheet-music/transcribe.py /path/to/mastered/
2. Review source PDFs/XMLs
3. Open XMLs in MuseScore for tracks needing polish
4. Prepare singles: python3 tools/sheet-music/prepare_singles.py /path/to/sheet-music/source/
5. Create songbook: python3 tools/sheet-music/create_songbook.py /path/to/sheet-music/singles/ (optional)
```

**Manual (GUI)**:
```
1. Open WAV in AnthemScore
2. Adjust sensitivity, fix obvious errors
3. Export MusicXML
4. Import to MuseScore
5. Fix key/time sig, add dynamics
6. Format for print
7. Export PDF
8. Save .mscz project
9. Store in sheet-music/ folder
```

---

## AnthemScore CLI Reference

### Location

```bash
# macOS
/Applications/AnthemScore.app/Contents/MacOS/AnthemScore

# Get help
/Applications/AnthemScore.app/Contents/MacOS/AnthemScore --help
```

### Basic Usage

```bash
ANTHEMSCORE="/Applications/AnthemScore.app/Contents/MacOS/AnthemScore"

# WAV → PDF + MusicXML (headless)
$ANTHEMSCORE track.wav -a -p track.pdf -x track.xml

# Also generate MIDI
$ANTHEMSCORE track.wav -a -p track.pdf -x track.xml -m track.mid

# Treble clef only
$ANTHEMSCORE track.wav -a -t -p track.pdf

# Bass clef only
$ANTHEMSCORE track.wav -a -b -p track.pdf
```

### All CLI Flags

| Flag | Purpose |
|------|---------|
| `-a, --headless` | No GUI (batch mode) |
| `-p <file>` | Output PDF |
| `-x <file>` | Output MusicXML |
| `-m <file>` | Output MIDI |
| `-d <file>` | Save AnthemScore project (.asdt) |
| `-c <file>` | Save spectrogram CSV |
| `-t` | Treble clef only |
| `-b` | Bass clef only |
| `-j <1-88>` | Lowest piano key |
| `-k <1-88>` | Highest piano key |
| `-r` | Remove notes outside range |
| `-o` | Move notes into range |
| `-w <4,8,16>` | Smallest note value |
| `-s <ms>` | Start time (milliseconds) |
| `-e <ms>` | End time (milliseconds) |
| `-z <n>` | Thread count |
| `-n` | Don't find notes (use with -c for spectrogram only) |
| `-l` | Print audio length and exit |

### Batch Script

Use the provided batch script for easier automation:

```bash
./tools/sheet-music/transcribe.sh /path/to/mastered/
./tools/sheet-music/transcribe.sh /path/to/mastered/ --pdf-only
./tools/sheet-music/transcribe.sh /path/to/mastered/ --midi
./tools/sheet-music/transcribe.sh /path/to/mastered/ --dry-run
```

---

## Post-Transcription Tools

### Prepare Singles (prepare_singles.py)

Prepare consumer-ready sheet music from numbered source files:

```bash
# Prepare singles with clean titles
python3 tools/sheet-music/prepare_singles.py /path/to/sheet-music/source/

# Options
python3 tools/sheet-music/prepare_singles.py /path/to/sheet-music/source/ --dry-run   # Preview only
python3 tools/sheet-music/prepare_singles.py /path/to/sheet-music/source/ --xml-only  # Skip PDF/MIDI
```

**What it does**:
1. Reads numbered source files (PDF, XML, MIDI) from source/
2. Applies smart title casing (e.g., "01-ocean-of-tears" → "Ocean of Tears")
3. Updates `<work-title>` in MusicXML files
4. Writes clean-titled files to singles/ directory
5. Creates `.manifest.json` for track ordering
6. Source files are never modified

**Optional**: MuseScore installed for PDF re-export (otherwise copies source PDFs).

---

### Create Songbook (create_songbook.py)

Combine track PDFs into a distribution-ready songbook:

```bash
# Basic usage
python3 tools/sheet-music/create_songbook.py /path/to/sheet-music/ \
  --title "Album Name" \
  --artist "Artist Name"

# Full options
python3 tools/sheet-music/create_songbook.py /path/to/sheet-music/ \
  --title "Album Name" \
  --artist "Artist Name" \
  --cover /path/to/album.png \
  --website "bitwizemusic.com" \
  --page-size letter \
  --year 2025
```

**Options**:
| Option | Purpose |
|--------|---------|
| `--title` | Songbook title (required) |
| `--artist` | Artist name (required) |
| `--cover` | Path to cover image (jpg/png) |
| `--website` | Website URL for title/copyright pages |
| `--page-size` | `letter` (8.5x11), `9x12`, or `6x9` |
| `--year` | Copyright year |
| `--section-headers` | Add header page before each track |

**Output includes**:
- Title page (with cover art if provided)
- Copyright page
- Table of contents with track names and page numbers
- All track PDFs combined in order

**Note**: Only includes files starting with digits (track numbers). Existing songbook PDFs are automatically excluded.

**Requirements**: `pip install pypdf reportlab`

---

## Complete Publishing Workflow

```bash
# 1. Transcribe all tracks (outputs to sheet-music/source/)
python3 tools/sheet-music/transcribe.py /path/to/mastered/

# 2. Review/polish in MuseScore (manual, as needed)
open -a "MuseScore 4" /path/to/sheet-music/source/*.xml

# 3. Prepare singles (clean titles → sheet-music/singles/)
python3 tools/sheet-music/prepare_singles.py /path/to/sheet-music/source/

# 4. Create songbook (→ sheet-music/songbook/)
python3 tools/sheet-music/create_songbook.py /path/to/sheet-music/singles/ \
  --title "Album Name" --artist "Artist"

# 5. Upload to website
# Singles ready in: /path/to/sheet-music/singles/
# Songbook ready in: /path/to/sheet-music/songbook/
```
