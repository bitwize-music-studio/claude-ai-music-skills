# Skill Glossary

Common terminology and frequently confused terms in the bitwize-music plugin.

---

## Core Concepts

### Skill
A slash command that invokes specialized functionality. Skills are invoked with `/bitwize-music:skill-name`. Each skill has its own SKILL.md documentation in `${CLAUDE_PLUGIN_ROOT}/skills/[skill-name]/`.

### Content Root
The directory where albums, artists, and research files live. Set in `paths.content_root`. Example: `~/music-projects/artists/bitwize/albums/...`

### Audio Root
The directory where mastered audio files are stored. Set in `paths.audio_root`. Uses flat structure: `{audio_root}/{artist}/{album}/`. No genre folder.

### Override
A user-created file that customizes skill behavior without modifying plugin files. Lives in `{content_root}/overrides/`. Survives plugin updates.

---

## Album Workflow Terms

### 7 Planning Phases
The structured planning process before writing lyrics:
1. Foundation (artist, genre, type)
2. Concept Deep Dive (story, characters)
3. Sonic Direction (inspirations, production)
4. Structure Planning (tracklist, flow)
5. Album Art (visual concept)
6. Practical Details (finalize titles)
7. Confirmation (get go-ahead)

### Track Status
The lifecycle of a single track:
- **Not Started** - Concept only
- **Sources Pending** - Has sources, awaiting verification
- **Sources Verified** - Ready for production
- **In Progress** - Currently generating
- **Generated** - Has acceptable output
- **Final** - Complete, locked

### Album Status
The lifecycle of an album:
- **Concept** - Planning phase
- **Research Complete** - Sources gathered
- **Sources Verified** - All sources verified
- **In Progress** - Tracks being created
- **Complete** - All tracks Final
- **Released** - Live on platforms

---

## Suno Terms

### Style Box
The text field in Suno for describing musical style. Contains genre, vocal style, instrumentation, mood. Example: "dark industrial electronic, aggressive male vocals, distorted synths"

### Lyrics Box
The text field in Suno for lyrics with section tags. Uses tags like `[Verse]`, `[Chorus]`, `[Bridge]`.

### Section Tags
Markers in lyrics that tell Suno how to structure the song. Examples: `[Intro]`, `[Verse 1]`, `[Pre-Chorus]`, `[Chorus]`, `[Bridge]`, `[Outro]`

### Suno Persona
A description of the vocalist to maintain consistency across an album. Stored in album README.

---

## Research Terms

### Source Verification
Human review confirming that captured sources are accurate before using them in lyrics. Required for true-story albums. Status: `Pending` to `Verified`.

### Primary Source
Direct evidence: court documents, official statements, subject's own words. Highest reliability.

### Secondary Source
Reporting about primary sources: journalism, analysis, Wikipedia summaries.

### Source Hierarchy
Priority order for trustworthiness:
1. Court documents
2. Government releases
3. Investigative journalism
4. News
5. Wikipedia (context only)

---

## Audio Terms

### Mastering
Final audio processing for streaming platforms. Target: -14 LUFS, -1.0 dBTP.

### LUFS
Loudness Units Full Scale. Measures perceived loudness. Streaming platforms normalize to -14 LUFS.

### dBTP
Decibels True Peak. Maximum sample value. -1.0 dBTP prevents clipping after encoding.

### Genre Preset
Pre-configured EQ and dynamics settings for specific genres. Used by mastering tools.

---

## Frequently Confused Terms

### Album Ideas vs Album Status
- **Album Ideas** (`IDEAS.md`): Brainstorming before album creation. Managed by `/album-ideas`.
- **Album Status** (album README): Tracking progress of created albums. Field in album frontmatter.

### Content Root vs Audio Root
- **Content Root**: Markdown files, lyrics, research. Has genre folders.
- **Audio Root**: WAV/MP3 files. Flat structure, no genre folders.

### Style Prompt vs Style Box
Same thing. "Style prompt" is what you write, "Style Box" is where it goes in Suno.

### Track vs Song
Interchangeable in this plugin. Both refer to a single piece of music on an album.

### Streaming Lyrics vs Suno Lyrics
- **Suno Lyrics**: Include section tags, phonetic spellings
- **Streaming Lyrics**: Clean version for DistroKid/Spotify (no tags, proper capitalization)

---

## Path Variables

Variables used in documentation that resolve from config:

| Variable | Config Field | Example |
|----------|--------------|---------|
| `{content_root}` | `paths.content_root` | `~/music-projects` |
| `{audio_root}` | `paths.audio_root` | `~/music-projects/audio` |
| `{documents_root}` | `paths.documents_root` | `~/music-projects/documents` |
| `${CLAUDE_PLUGIN_ROOT}` | (location of plugin) | `~/.claude/plugins/bitwize-music` |
| `{overrides}` | `paths.overrides` | `~/music-projects/overrides` |
| `[artist]` | `artist.name` | `bitwize` |

---

## See Also

- [SKILL.md](SKILL.md) - Help skill documentation
- [/CLAUDE.md](/CLAUDE.md) - Main workflow instructions
- [/README.md](/README.md) - Project overview
