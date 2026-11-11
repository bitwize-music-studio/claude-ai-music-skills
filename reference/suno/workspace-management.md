# Suno Workspace Management

Suno workspaces are folders on suno.com for clips that belong together. With Suno's MCP server connected, the plugin keeps one workspace per album for you; without it, the manual steps at the end still apply.

## What Are Workspaces?

Workspaces organize generated clips into projects. They are separate from:

- **Library**: All your generated content
- **Playlists**: Curation and listening sets

A song is in at most one workspace, so filing it somewhere moves it.

## With the Suno MCP Server

- **First generation creates the workspace.** `/bitwize-music:generate` reads the album's `suno_workspace` (frontmatter in the album README, through `get_album_workspace`). When there is none, the go-ahead summary carries a **Workspace** line; your yes creates a workspace named after the album (`workspaces-create`), records it (`set_album_workspace`), and files any takes the album already has (`workspaces-update-clips`, 50 ids per call).
- **Every take is filed as it is made.** The recorded id travels as `workspace_id` on `audio-create`, so new takes never land loose in My Songs.
- **Stems follow.** `/bitwize-music:import-audio --from-suno --stems` files the 24 stem songs of a split in the same workspace.
- **Resuming uses the recorded workspace.** Before generating, the skill checks it still exists (`workspaces-list`); if it was deleted on suno.com, it asks before creating a new one.
- **Older albums catch up at their next generation**: the summary says how many earlier takes will be filed.
- Turn it off with `generation.suno_workspaces: false` in `~/.bitwize-music/config.yaml`.

Creating a workspace and filing songs cost no credits (see [mcp-api-mapping.md](mcp-api-mapping.md)). The MCP server cannot delete or rename a workspace; do that on suno.com.

The workspace is recorded in the album README:

```yaml
suno_workspace:
  id: "be7f57b5-0cef-4769-ab0e-44b4861bd895"
  name: "Album Title"
```

To point an album at a workspace you already have, run `workspaces-list(query: "<name>")` and `set_album_workspace(album_slug, <id>, <name>)`, or edit the block by hand and rebuild the state cache.

## Without the Server (Manual)

### Before Generating an Album

1. Create a workspace in Suno's web UI
2. Name it after the album
3. This creates a home for all clips from this project

### After Generation

1. Go to Library in Suno's web UI
2. Find the newly generated clip(s) by title
3. Click the menu (⋯) on each clip
4. Select "Move to Workspace"
5. Choose your album workspace

For several clips at once: Shift-click for ranges or Ctrl/Cmd-click for individuals, then "More actions" → move to a workspace.

## Archiving Completed Albums

When an album is finished:

1. Rename the workspace on suno.com with an `ARCHIVE_` prefix (e.g., `ARCHIVE_multiplayer-notepad`)
2. Or export final clips and move to external storage
3. Keep latest two exports plus milestone versions
4. Clear old iterations from the workspace

## Tips

- **Thumbs up/down**: Use immediately during review
  - Thumbs down on suno.com moves clips to Trash (Library → Trash → Delete Permanently). A dislike sent through the MCP server does not: the song stays in the library *(measured)*
  - Thumbs up marks keepers
- **Track correspondence**: Track title in Suno should match track title in markdown file
