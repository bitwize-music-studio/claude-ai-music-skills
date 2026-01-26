# Platform Specifications for Promo Videos

Technical requirements and best practices for uploading promo videos to social media platforms.

## Quick Reference

| Platform | Aspect Ratio | Max Duration | Max File Size | Codec |
|----------|--------------|--------------|---------------|-------|
| Instagram Reels | 9:16 | 90s | 4 GB | H.264 |
| Twitter | 9:16, 16:9, 1:1 | 2:20 | 512 MB | H.264 |
| TikTok | 9:16 | 10min | 287 MB | H.264 |
| Facebook | 9:16, 16:9, 1:1, 4:5 | 240min | 4 GB | H.264 |
| YouTube Shorts | 9:16 | 60s | - | H.264 |

**Our default output (1080x1920, H.264, 15s, ~10-12 MB) works on ALL platforms.**

## Instagram

### Instagram Reels

**Recommended specs:**
- Resolution: 1080x1920 (9:16 vertical) ✓
- Duration: 15-90 seconds ✓
- Frame rate: 23-30 fps ✓
- Codec: H.264 ✓
- Audio: AAC ✓
- File size: < 4 GB ✓

**Optimal settings:**
- Duration: 15-30 seconds (our default 15s is perfect)
- Hashtags: Use relevant genre/mood hashtags
- Caption: Include track name, artist, streaming link
- Cover: Auto-generated from first frame (ensure artwork visible)

**Upload process:**
1. Open Instagram app (mobile)
2. Tap + → Reels
3. Select video from gallery
4. Edit: Add captions, stickers, hashtags
5. Share

**Best practices:**
- Post when audience is active (check Insights)
- Use trending audio formats (Reels tab)
- Add captions (many watch without sound)
- Engage with comments quickly

---

## Twitter

**Recommended specs:**
- Resolution: 1080x1920 (9:16 vertical) ✓
- Duration: Up to 2:20 (140 seconds) ✓
- Frame rate: 30 fps ✓
- Codec: H.264 ✓
- Audio: AAC ✓
- File size: < 512 MB ✓

**Also accepts:**
- 16:9 horizontal (1920x1080)
- 1:1 square (1080x1080)

**Optimal settings:**
- Individual promos: 15s each ✓
- Album sampler: Up to 2:20 (perfect for 10-track album) ✓
- File size: Keep under 50 MB for fast upload

**Upload process:**
1. Compose tweet (app or web)
2. Click media button
3. Select video
4. Add text, link, hashtags
5. Tweet

**Best practices:**
- First frame matters (auto-plays muted in feed)
- Add text overlay in caption (not baked into video)
- Use 2-3 relevant hashtags max
- Tag collaborators, venues, labels
- Pin best-performing video to profile

**Character limits:**
- 280 characters for caption
- 100 characters for alt text (use it!)

---

## TikTok

**Recommended specs:**
- Resolution: 1080x1920 (9:16 vertical) ✓
- Duration: 15-60 seconds optimal, up to 10 minutes ✓
- Frame rate: 30 fps ✓
- Codec: H.264 ✓
- Audio: AAC ✓
- File size: < 287 MB ✓

**Optimal settings:**
- Duration: 15-30 seconds (TikTok sweet spot)
- Vertical only (horizontal not recommended)
- High energy, attention-grabbing visuals

**Upload process:**
1. Open TikTok app
2. Tap + button
3. Upload → Select video
4. Edit: Add text, effects, hashtags
5. Post

**Best practices:**
- Use trending sounds (but our audio is original)
- Add captions/subtitles (80% watch without sound)
- Use 3-5 hashtags (#NewMusic #IndieElectronic #etc)
- Post consistently (daily or every other day)
- Engage with comments immediately

**TikTok-specific tips:**
- First 3 seconds are critical (hook immediately)
- Vertical only (never upload horizontal)
- Bright, high-contrast visuals work best
- Gen-Z audience prefers authentic over polished

---

## Facebook

### Facebook Feed/Page Posts

**Recommended specs:**
- Resolution: 1080x1920 (9:16 vertical) ✓
- Duration: Up to 240 minutes ✓
- Frame rate: 30 fps ✓
- Codec: H.264 ✓
- Audio: AAC ✓
- File size: < 4 GB ✓

**Also accepts:**
- 16:9 horizontal (1920x1080)
- 1:1 square (1080x1080)
- 4:5 vertical (1080x1350)

**Optimal settings:**
- Individual promos: 15-30s
- Square (1:1) often performs better in News Feed
- File size: Keep under 100 MB

**Upload process:**
1. Open Facebook
2. Create post (on page or profile)
3. Add video
4. Write caption, add link
5. Publish or schedule

**Best practices:**
- Native video outperforms YouTube links
- Add captions (auto-generated or upload SRT)
- First frame matters (thumbnail)
- Cross-post to Instagram (owns Facebook)

---

## YouTube Shorts

**Recommended specs:**
- Resolution: 1080x1920 (9:16 vertical) ✓
- Duration: 60 seconds or less ✓
- Frame rate: 30 fps ✓
- Codec: H.264 ✓
- Audio: AAC ✓
- File size: No strict limit ✓

**Optimal settings:**
- Duration: 15-60 seconds (our 15s works, or extend to 30-60s)
- Vertical only
- High retention (keep viewers watching to end)

**Upload process:**
1. Open YouTube app or Studio
2. Create → Upload video
3. Title: Include #Shorts in title or description
4. Vertical video auto-detected as Short
5. Publish

**Best practices:**
- Title must include #Shorts
- Upload as regular video (Shorts auto-detected)
- Strong hook in first 3 seconds
- End with call-to-action (subscribe, stream, etc.)

---

## Platform Comparison

### Audience Demographics

**Instagram:**
- Age: 18-34 primary, 25-34 largest
- Music discovery: High
- Engagement: Visual, aesthetic-driven

**Twitter:**
- Age: 25-49 primary
- Music discovery: Medium
- Engagement: Text-first, conversational

**TikTok:**
- Age: 16-24 primary (Gen Z)
- Music discovery: Extremely high (primary music discovery platform)
- Engagement: Viral potential, algorithm-driven

**Facebook:**
- Age: 25-54 primary, older skew
- Music discovery: Low
- Engagement: Lower for music, but wide reach

**YouTube:**
- Age: 18-49 broad
- Music discovery: High (second to streaming services)
- Engagement: Long-form consumption, educational

### Where to Focus

**If you have limited time:**
1. Instagram Reels (best music discovery + engagement)
2. TikTok (viral potential, younger audience)
3. Twitter (industry presence, press, fans)

**If you have more time:**
4. YouTube Shorts (SEO, long-term value)
5. Facebook (older audience, cross-post from Instagram)

**If you're building industry presence:**
- Twitter (music industry is very active)
- Instagram (visual portfolio)

---

## Format Conversion

### Generate Square (1:1) for Facebook

Modify script to generate square videos:

```python
# In generate_promo_video.py
WIDTH = 1080
HEIGHT = 1080  # Square instead of 1920

# Adjust layout:
# - Artwork at top
# - Waveform in middle
# - Text at bottom
```

### Generate Horizontal (16:9) for YouTube

```python
# In generate_promo_video.py
WIDTH = 1920
HEIGHT = 1080  # Horizontal

# Adjust layout:
# - Artwork on left
# - Waveform on right
# - Text at bottom center
```

### Convert Existing Video

**Vertical to square:**
```bash
ffmpeg -i vertical.mp4 -vf "scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080" -c:a copy square.mp4
```

**Vertical to horizontal:**
```bash
ffmpeg -i vertical.mp4 -vf "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080" -c:a copy horizontal.mp4
```

---

## File Size Optimization

**Our default (10-12 MB per 15s video) is optimal for all platforms.**

**If you need smaller files:**

```bash
# Increase compression (lower quality)
ffmpeg -i input.mp4 -c:v libx264 -crf 28 -c:a aac -b:a 128k output.mp4

# Reduce resolution (not recommended)
ffmpeg -i input.mp4 -vf scale=720:1280 -c:v libx264 -crf 23 -c:a aac -b:a 128k output.mp4
```

**If you need higher quality:**

```bash
# Decrease compression (higher quality)
ffmpeg -i input.mp4 -c:v libx264 -crf 18 -c:a aac -b:a 256k output.mp4
```

**CRF values:**
- 18: Visually lossless (large files)
- 23: High quality (our default)
- 28: Medium quality (smaller files)
- 32: Lower quality (not recommended)

---

## Caption Best Practices

### Instagram
```
🎵 New track: "Song Title"
from the album "Album Name"

[Genre tag] [Mood tag]

Stream now: [link]

#NewMusic #IndieElectronic #AlbumName
```

### Twitter
```
New track "Song Title" from "Album Name" 🎵

[Brief description or hook]

Listen: [streaming link]

#NewMusic #Genre
```

### TikTok
```
New music alert! 🚨

"Song Title" out now

#NewMusic #Genre #Artist #Indie
```

---

## Hashtag Strategy

### Instagram (use 15-30):

**Generic music:**
#NewMusic #IndieMusic #ElectronicMusic #NowPlaying

**Genre-specific:**
#Techno #HipHop #Folk #Synthwave #AmbientMusic

**Mood/vibe:**
#DarkElectronic #ChillBeats #HighEnergy #MeditativeMusic

**Album-specific:**
#AlbumName #ArtistName #NewAlbum #MusicRelease

### Twitter (use 2-3):

Less is more on Twitter. Focus on most relevant:
#NewMusic #GenreTag #AlbumName

### TikTok (use 3-5):

Focus on discoverable tags:
#NewMusic #IndieArtist #Genre #MusicProducer #UnsignedArtist

---

## Accessibility

### Captions/Subtitles

**Why important:**
- 80% of social media watched without sound
- Accessibility for deaf/hard-of-hearing
- Better engagement (people read along)

**How to add:**

**Instagram:**
- Auto-captions (generated by Instagram)
- Or add text stickers manually

**Twitter:**
- Upload SRT file with video
- Or add text in tweet

**TikTok:**
- Auto-captions (tap Captions button)
- Or add text overlays

**Facebook:**
- Auto-generate captions
- Or upload SRT file

### Alt Text

Always add alt text describing video:

```
Example:
"Animated waveform visualization for song 'Track Title' by Artist Name.
Blue glowing waveform reacts to music over blurred album artwork background.
Track title and artist name displayed at bottom."
```

---

## Upload Checklist

Before uploading to any platform:

- [ ] Video is 1080x1920 (9:16 vertical)
- [ ] Duration appropriate for platform
- [ ] H.264 codec, AAC audio
- [ ] File size under platform limit
- [ ] First frame is clear (artwork visible)
- [ ] Audio plays correctly
- [ ] Title/artist text readable on phone
- [ ] Caption prepared
- [ ] Hashtags selected
- [ ] Streaming link ready
- [ ] Alt text written

---

## Platform-Specific Optimizations

### Instagram Algorithm

Favors:
- Watch time (full video viewed)
- Saves (bookmark feature)
- Shares (DM to friends)
- Comments

Optimization:
- Hook in first 3 seconds
- Keep under 30 seconds for full watches
- End with call-to-action ("Save this!")
- Engage with all comments

### TikTok Algorithm

Favors:
- Watch time (especially completion rate)
- Replays (loop video)
- Shares
- Sounds used (original music can go viral)

Optimization:
- Strong hook (first second)
- Loop-able video (end leads to beginning)
- Trending sounds (but yours is original)
- Post at peak times (8pm-11pm)

### Twitter Algorithm

Favors:
- Native video (not YouTube links)
- Engagement (retweets, replies, likes)
- Recency

Optimization:
- Post at peak times for your audience
- Native upload (don't link to YouTube)
- Thread videos (post series)
- Pin best performer to profile

---

## Related Documentation

- `/reference/promotion/promo-workflow.md` - Complete workflow
- `/skills/promo-director/SKILL.md` - Skill documentation
- `/skills/promo-director/visualization-guide.md` - Style guide
