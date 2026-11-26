# Shared workflows in Claude Code and Codex

Claude Code and Codex share one `skills/` tree and the same source-verification
rules. Claude Code uses the skills' model, effort, and tool settings. Codex uses
its own model settings and available tools.

## Skill names and inputs

In Claude Code, use `/bitwize-music:<skill>` in chat. In Codex, select the
installed skill in the skill picker or use its advertised name in chat, such as
`$bitwize-music:setup` or `$bitwize-music:resume my-album`.

Use the installed skill name in status reports, for example, “Use the
`verify-sources` skill for this album.” When showing an invocation, use the
active host's format above.

When shared instructions name a skill, load the corresponding installed
skill. If it is unavailable, tell the user before continuing.

Use the arguments in the user's request when the host leaves `$ARGUMENTS`
unset. For `AskUserQuestion` or missing required inputs, ask through the host's
question tool or in chat and wait for the answer.

## Resolve the installed plugin root

Claude Code supplies `${CLAUDE_PLUGIN_ROOT}`. In Codex, find the loaded
`skills/<name>/SKILL.md` and use the parent of that `skills/` directory as
the plugin root. Check that it contains `requirements.txt` and
`.claude-plugin/plugin.json`.

Resolve shared references such as `${CLAUDE_PLUGIN_ROOT}/templates/` under that
root. In Codex setup commands, substitute its absolute path for
`${CLAUDE_PLUGIN_ROOT}` (Bash) or `$env:CLAUDE_PLUGIN_ROOT` (PowerShell). Quote
the requirements and interpreter paths for the active shell.

Reuse these rules if the same installed copy is already in your session context.

## Configuration and startup

Both hosts use `~/.bitwize-music/config.yaml`, `~/.bitwize-music/venv`, and the
configured content, audio, documents, and overrides directories. Read current
configuration before resolving workspace paths. Preserve existing config and
artist casing, and use the canonical configure skill for changes.

In Codex, invoke the installed `session-start` skill at the beginning of a music
session. The Codex `session-start` and `resume` workflows read
[`reference/plugin-rules.md`](plugin-rules.md) from the installed plugin root.
For plugin workflow overrides, use only `CLAUDE.md` in the configured
`paths.overrides` directory. The default directory is `{content_root}/overrides`.

After installing dependencies, start a new session in the active host and
check the MCP connection. Rerun setup checks, report the connection and
dependency results, then configure the workspace.

## Resume reports

In Claude Code, list three next steps and put the priority action first. In
Codex, show the priority action.

See the official [Codex skill invocation guidance](https://learn.chatgpt.com/docs/build-skills#how-chatgpt-and-codex-use-skills).
