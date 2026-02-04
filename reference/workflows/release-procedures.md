# Release Procedures

This document covers detailed procedures for album art generation and album release.

## Album Art Generation

Generate album art when tracks are complete and you're preparing for release.

### When to Generate Album Art

**Proactive trigger**: When user says "album is done" or you see all tracks marked `Final`, ask: **"Ready to generate the album art?"**

### Workflow

**Step 1: Verify Prompt Exists**
- Album README should have ChatGPT/DALL-E prompt in "Album Art" section
- If missing, use `/bitwize-music:album-art-director` to create prompt

**Step 2: Generate with User**

Since Claude Code cannot directly generate images:

1. **Tell user**: "The album art prompt is ready. I'll copy it for you to use with ChatGPT/DALL-E."
2. **Show the prompt** from the album README
3. **Instruct user**:
   - Open ChatGPT (with DALL-E access) or other image generation tool
   - Paste the prompt
   - Generate image (may need multiple attempts)
   - Download as high-resolution (3000x3000px recommended)

**Step 3: Save to Standard Locations**

Once user has generated and downloaded the image, use the `/bitwize-music:import-art` skill:

```
/bitwize-music:import-art ~/Downloads/album-art.jpg sample-album
```

The skill:
1. Reads config to get `audio_root`, `content_root`, and `artist.name`
2. Copies to audio folder: `{audio_root}/{artist}/{album}/album.png`
3. Copies to content folder: `{content_root}/artists/{artist}/albums/{genre}/{album}/album-art.jpg`

**Why use the skill**: It handles both destinations correctly and always includes the artist folder in the audio path.

**Step 4: Update Checklist**

Mark album art as complete in Album Completion Checklist.

### File Naming Standards

| Location | Filename | Format |
|----------|----------|--------|
| Audio folder | `album.png` | PNG for platforms |
| Album directory | `album-art.jpg` or `album-art.png` | Either |

### Troubleshooting

**User doesn't have ChatGPT access:**
- Try other tools: Midjourney, Stable Diffusion, etc.
- Adjust prompt for that tool's syntax

**Need prompt revisions:**
- Use `/bitwize-music:album-art-director` to refine visual concept
- Iterate on prompt based on generation results

---

## Releasing an Album

When an album is ready for release:

### 1. Verify Completion Checklist

Ensure all items in Album Completion Checklist are done:
- All tracks Final with Suno Links
- Album art generated and saved
- Audio mastered
- Streaming Lyrics filled in each track (if using distributor — see [distribution.md](../distribution.md) for format rules)

### 2. Update Album README

In the album's README.md:
1. Set `release_date: YYYY-MM-DD` in YAML frontmatter
2. Set `Status: Released`

### 3. Upload to Platforms

- Upload to SoundCloud and/or distributor
- Add platform URLs back to album README

## Post-Release Actions

See `/reference/workflows/checkpoint-scripts.md` for the detailed Day 1 checklist and release complete message template.
