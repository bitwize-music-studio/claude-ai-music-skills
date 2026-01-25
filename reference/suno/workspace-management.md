# Suno Workspace Management

Suno workspaces organize generated clips into project folders. The API does not support workspace management, so this must be done manually.

## What Are Workspaces?

Workspaces are folders in Suno's web UI for organizing your generated clips. They're separate from:

- **Library**: All your generated content
- **Playlists**: Curation and listening sets

Workspaces are for "editing in progress" - organizing active projects.

## Recommended Workflow

### Before Generating an Album

1. Create a workspace in Suno's web UI
2. Name it to match your album folder (e.g., `multiplayer-notepad`)
3. This creates a home for all clips from this project

### During Generation

When generating tracks:
1. Clips are generated to your default library
2. After generation completes, manually move clips to the album workspace
3. Use track titles to identify which clips belong where

### After Generation

1. Go to Library in Suno's web UI
2. Find the newly generated clip(s) by title
3. Click the menu (⋯) on each clip
4. Select "Move to Workspace"
5. Choose your album workspace

### Batch Moving

For multiple clips:
1. In Library, use Shift-click for ranges or Ctrl/Cmd-click for individuals
2. Click "More actions"
3. Move all selected to a single workspace

## Workspace Naming Convention

Match workspace names to album folder names:

| Album Folder | Workspace Name |
|--------------|----------------|
| `multiplayer-notepad` | `multiplayer-notepad` |
| `connection-lost` | `connection-lost` |
| `whatever-it-takes` | `whatever-it-takes` |

This makes it easy to find clips for each project.

## Archiving Completed Albums

When an album is finished:

1. Prefix the workspace with `ARCHIVE_` (e.g., `ARCHIVE_multiplayer-notepad`)
2. Or export final clips and move to external storage
3. Keep latest two exports plus milestone versions
4. Clear old iterations from the workspace

## Tips

- **Thumbs up/down**: Use immediately during review
  - Thumbs down moves clips to Trash (Library → Trash → Delete Permanently)
  - Thumbs up marks keepers
- **Stay organized**: Move clips to workspace right after generation
- **Track correspondence**: Track title in Suno should match track title in markdown file

## Why Manual?

