# Promo Video Workflow

Complete workflow for generating, reviewing, and publishing promo videos for music releases.

## Overview

Generate professional 15-second vertical promo videos (9:16) from mastered audio, optimized for social media platforms.

**Timeline:** After mastering, before release

**Output:** Individual track promos + album sampler video

## Prerequisites

### Required Files

- ✓ Mastered audio files (.wav, .mp3, .flac, .m4a)
- ✓ Album artwork (album.png or album.jpg)
- ✓ Both in correct location: `{audio_root}/{artist}/{album}/`

### Required Software

- ✓ ffmpeg with filters (showwaves, showfreqs, drawtext, gblur)
- ✓ Python 3.8+
- ✓ Python packages: pillow, pyyaml
- ✓ Optional: librosa, numpy (for smart segment selection)

## Workflow Steps

### Step 1: Prepare Album Directory

**Verify structure:**
```
{audio_root}/{artist}/{album}/
├── 01-track-name.wav
├── 02-another-track.wav
├── ...
└── album.png
```

**Check artwork:**
- Recommended size: 3000x3000px
- Format: PNG or JPG
- Square aspect ratio
- High quality (will be displayed prominently)

**Import if needed:**
```
/bitwize-music:import-art ~/Downloads/album-art.png my-album
```

### Step 2: Choose Visualization Style

See `/skills/promo-director/visualization-guide.md` for full details.

**Quick recommendations:**

| Genre | Style |
|-------|-------|
| Electronic/Hip-Hop | pulse |
| Pop/Rock | bars |
| Acoustic/Folk | line |
| Ambient/Chill | mirror |
| Synthwave/80s | neon |

**Test first:**

Generate one video to verify style looks good:
```bash
python3 tools/promotion/generate_promo_video.py \
  {audio_root}/{artist}/{album}/01-track.wav \
  {audio_root}/{artist}/{album}/album.png \
  "Track Title" \
  --style pulse \
  -o test.mp4
```

View on phone to check:
- Waveform reactivity
- Color scheme matches album aesthetic
- Title/artist readable
- Artwork not obscured

### Step 3: Generate Videos

**Option A: Use skill (recommended)**

```
/bitwize-music:promo-director my-album
```

Skill handles:
- Config reading
- Path resolution
- Dependency checks
- User prompts for options
- Progress reporting

**Option B: Run scripts directly**

Individual promos:
```bash
cd {plugin_root}
python3 tools/promotion/generate_promo_video.py \
  --batch {audio_root}/{artist}/{album}/ \
  --style pulse \
  -o {audio_root}/{artist}/{album}/promo_videos/
```

Album sampler:
```bash
cd {plugin_root}
python3 tools/promotion/generate_album_sampler.py \
  {audio_root}/{artist}/{album}/ \
  --artwork {audio_root}/{artist}/{album}/album.png \
  --clip-duration 12 \
  -o {audio_root}/{artist}/{album}/album_sampler.mp4
```

Both:
```bash
cd {plugin_root}
python3 tools/promotion/generate_all_promos.py \
  {audio_root}/{artist}/{album}/ \
  --style pulse
```

### Step 4: Review Generated Videos

**Check output:**

```
{audio_root}/{artist}/{album}/
├── promo_videos/
│   ├── 01-track_promo.mp4
│   ├── 02-track_promo.mp4
│   └── ...
└── album_sampler.mp4
```

**Quality checklist:**

- [ ] All tracks have promo videos
- [ ] Videos are 15 seconds long
- [ ] Format: 1080x1920 (9:16 vertical)
- [ ] Audio quality good (192 kbps AAC)
- [ ] Waveform reacts to audio
- [ ] Colors match album aesthetic
- [ ] Track title visible and readable
- [ ] Artist name visible
- [ ] Artwork visible and sharp
- [ ] File sizes reasonable (10-12 MB per video)

**View on phone:**

Transfer one video to phone and verify:
- Looks good in vertical orientation
- Readable text
- Good aspect ratio (not stretched)
- Waveform visible and impactful

### Step 5: Organize for Distribution

**Video files** stay in the audio directory:

```
{audio_root}/{artist}/{album}/
├── promo_videos/
│   ├── instagram/          # Selected videos for Instagram
│   ├── twitter/            # Selected videos for Twitter
│   └── archive/            # All generated videos
└── album_sampler.mp4       # Full album preview
```

**Social media copy** lives in the album content directory:

```
{content_root}/artists/{artist}/albums/{genre}/{album}/promo/
├── campaign.md             # Strategy, schedule, key messages
├── twitter.md              # Tweets/threads per track
├── instagram.md            # Captions + hashtags per track
├── tiktok.md               # Captions per track
├── facebook.md             # Posts per track
└── youtube.md              # Descriptions per track
```

Fill in the `promo/` templates with platform-specific copy before posting.

**Selection strategy:**

Not every track needs a promo video on every platform.

**For Instagram:**
- 2-3 standout tracks (singles, most popular)
- Use most eye-catching style (pulse, neon, bars)

**For Twitter:**
- Album sampler (full preview)
- 1-2 key tracks

**For TikTok:**
- Singles only
- Most energetic moments

### Step 6: Cloud Upload (Optional)

Upload promo videos to cloud storage for hosting and CDN distribution.

**Use skill:**
```
/bitwize-music:cloud-uploader my-album
```

**Or run script directly:**
```bash
cd {plugin_root}
python3 tools/cloud/upload_to_cloud.py my-album --dry-run  # Preview first
python3 tools/cloud/upload_to_cloud.py my-album            # Then upload
```

**Supports:**
- Cloudflare R2 (recommended, no egress fees)
- AWS S3

See `/reference/cloud/setup-guide.md` for setup instructions.

### Step 7: Platform Upload

See `platform-specs.md` for detailed requirements.

**Instagram Reels:**

1. Open Instagram app
2. Tap + → Reels
3. Select video from gallery
4. Add caption (include track name, artist, streaming links)
5. Add hashtags (#NewMusic #IndieElectronic #etc)
6. Post

**Twitter:**

1. Open Twitter app or web
2. Compose tweet
3. Add video
4. Add text (track name, album info, link)
5. Post

**TikTok:**

1. Open TikTok app
2. Tap + button
3. Upload video
4. Add caption, hashtags
5. Post

**Facebook:**

1. Open Facebook
2. Create post
3. Upload video
4. Add caption
5. Post to page

### Step 8: Track Performance (Optional)

Monitor engagement:
- Views
- Likes/reactions
- Comments
- Shares
- Click-throughs to streaming links

Adjust strategy:
- Which tracks resonate most?
- Which platforms get most engagement?
- Which visualization styles perform best?
- Optimal posting times?

## Advanced Workflows

### Multi-Style Campaign

Generate multiple styles for A/B testing:

```bash
# Generate pulse style
python3 tools/promotion/generate_promo_video.py \
  track.wav album.png "Title" --style pulse -o pulse.mp4

# Generate neon style
python3 tools/promotion/generate_promo_video.py \
  track.wav album.png "Title" --style neon -o neon.mp4

# Test both on Instagram, see which performs better
```

### Platform-Specific Optimization

**Instagram (square 1:1):**

Modify WIDTH/HEIGHT in script:
```python
WIDTH = 1080
HEIGHT = 1080
```

**YouTube Shorts (9:16 but different specs):**

Use same 9:16 but optimize for longer duration:
```bash
python3 tools/promotion/generate_promo_video.py \
  track.wav album.png "Title" --duration 60 -o shorts.mp4
```

### Batch Processing Multiple Albums

```bash
for album in album1 album2 album3; do
  python3 tools/promotion/generate_all_promos.py \
    {audio_root}/{artist}/$album/ \
    --style pulse
done
```

### Scheduled Releases

Generate videos in advance, schedule with platform tools:
- Instagram: Creator Studio
- Twitter: TweetDeck or native scheduler
- Facebook: Business Suite

## Best Practices

### Timing

**When to generate:**
- After mastering complete
- Before release date (allow time for review/edits)
- Ideally 1-2 weeks before release

**When to post:**
- 1 week before release: Teaser (album sampler)
- Release day: Key singles (2-3 tracks)
- Week after release: Additional tracks
- Ongoing: Periodic reposts, playlist features

### Content Strategy

**Don't oversaturate:**
- Not every track needs a promo
- Focus on singles and standouts
- Space out posts (don't flood feed)

**Provide context:**
- Caption should include track name, album name, genre
- Link to streaming platforms
- Call to action ("Listen now", "Stream the album")

**Engage audience:**
- Ask questions in captions
- Respond to comments
- Create anticipation for release

### Technical Quality

**Always review on phone:**
- Desktop preview ≠ phone reality
- Text might be unreadable small
- Waveform might not be visible
- Colors might look different

**Test different styles:**
- What looks good on desktop may not work on phone
- Some styles pop more on small screens
- Bright styles (neon, pulse) often work better mobile

**File size considerations:**
- Keep under 100 MB for easy upload
- Compress if needed (but preserve quality)
- Use H.264 (not H.265/HEVC) for compatibility

## Troubleshooting

**"Videos look good on desktop but bad on phone"**
- Text too small: Increase TITLE_FONT_SIZE in script
- Waveform not visible: Try brighter style (neon, pulse)
- Colors washed out: Check phone brightness, try higher contrast

**"Waveform doesn't react to music"**
- Check: Is audio actually playing in video?
- ffmpeg error: showwaves filter might not be working
- Try different style: bars or line might work better

**"File sizes too large"**
- Check artwork resolution: Should be ≤3000px
- Reduce artwork: `convert album.png -resize 3000x3000\> album.png`
- Lower CRF in script (higher = more compression): `-crf 25`

**"Colors don't match album aesthetic"**
- PIL extraction failed: Use manual color override
- Artwork too dark: Color extraction filtered out colors
- Try different style: Some styles use white instead

**"Videos won't upload to platform"**
- Check format: Must be H.264 (not H.265)
- Check pixel format: Must be yuv420p
- Re-encode: `ffmpeg -i video.mp4 -c:v libx264 -pix_fmt yuv420p fixed.mp4`

## Campaign Planning Template

**Pre-Release (1 week before):**
- [ ] Generate all promo videos
- [ ] Select 2-3 key tracks for promotion
- [ ] Test one video on each platform
- [ ] Schedule album sampler post
- [ ] Prepare captions and hashtags

**Release Week:**
- [ ] Day 0: Post album sampler + streaming link
- [ ] Day 1: Post single #1 promo
- [ ] Day 3: Post single #2 promo
- [ ] Day 5: Post single #3 promo
- [ ] Day 7: Repost sampler + "out now" message

**Post-Release (ongoing):**
- [ ] Week 2: Post deep cut promo
- [ ] Week 3: Behind-the-scenes or making-of
- [ ] Week 4: Fan reactions or playlist features
- [ ] Monthly: Reposts of best performers

## Next Steps

After generating promo videos:

1. **Review all videos** - Quality check
2. **Select key tracks** - Which to promote where
3. **Fill in promo/ copy** - Populate per-platform templates in album's `promo/` directory
4. **[Optional] Upload to cloud** - `/bitwize-music:cloud-uploader`
5. **Schedule posts** - Plan timing using `promo/campaign.md`
6. **Continue to release workflow** - `/bitwize-music:release-director`

## Related Documentation

- `/skills/promo-director/SKILL.md` - Skill documentation
- `/skills/cloud-uploader/SKILL.md` - Cloud upload skill
- `/reference/cloud/setup-guide.md` - Cloud storage setup
- `/skills/promo-director/visualization-guide.md` - Style guide
- `/reference/promotion/platform-specs.md` - Platform requirements
- `/reference/promotion/ffmpeg-reference.md` - Technical details
