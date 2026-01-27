# Release Preferences

Custom QA requirements and platform priorities.

## QA Requirements

### Additional Checks
-
-

### Skip Checks (for specific album types)
-
-

## Platform Priorities

| Priority | Platform | Notes |
|----------|----------|-------|
| 1 | | |
| 2 | | |
| 3 | | |

## Metadata Standards

- Artist name format:
- Album title format:
- Tags to always include:

## Timing

- Days between completion and release:
- Days between SoundCloud and distributor:

---

## Example

```markdown
## QA Requirements
### Additional Checks
- Listen-through on 3 devices (headphones, monitors, phone)
- A/B comparison with reference track
- Verify all track transitions work as playlist

### Skip Checks
- Source verification (for non-documentary albums)
- Streaming lyrics review (instrumental albums)

## Platform Priorities
| Priority | Platform | Notes |
|----------|----------|-------|
| 1 | SoundCloud | Always upload first, same day |
| 2 | Bandcamp | Within 24 hours |
| 3 | Spotify/Apple | Via DistroKid, 1 week after |

## Metadata Standards
- Artist name format: lowercase (bitwize not Bitwize)
- Album title format: Title Case
- Tags to always include: ai-music, suno, electronic

## Timing
- Days between completion and release: 3 (buffer for final review)
- Days between SoundCloud and distributor: 7
```
