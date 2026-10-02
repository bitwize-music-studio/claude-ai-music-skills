# Shared workflows in Claude Code and Codex

The plugin has one canonical `skills/` tree. Claude Code's model, effort, and
tool frontmatter remains in place; Codex uses its own available tools and model
configuration. The workflow and its source-verification gates apply in both hosts.

## Skill names and inputs

Claude Code uses `/bitwize-music:<skill>`. In Codex, select the installed skill
from the skill picker or use its advertised name, such as
`$bitwize-music:setup` or `$bitwize-music:resume my-album`.

When shared instructions mention `/bitwize-music:<skill>`, treat that as a
reference to the canonical workflow. In Codex, load the corresponding installed
skill by its advertised name; do not run the Claude slash command in a shell.
If a skill is unavailable, report that before continuing with its workflow.

`$ARGUMENTS` means the arguments supplied with the user's skill request. If the
host does not inject that variable, use the user's request directly. Ask for
missing required inputs. Likewise, `AskUserQuestion` means asking the user via
the host's available question tool or ordinary conversation, then waiting for
the answer. Do not invent values to complete configuration.

## Resolve the installed plugin root

Use the path of the **loaded** `skills/<name>/SKILL.md`: the plugin root is two
directories above that skill's directory. Confirm it contains `skills/`,
`requirements.txt`, and `.claude-plugin/plugin.json`. This works in a checkout
and in an installed plugin cache, even when the music project is elsewhere.

Claude Code supplies `${CLAUDE_PLUGIN_ROOT}`. Codex shell commands need not have
that variable. Resolve the root from the loaded skill rather than the session's
working directory, another installation, or a guessed home-directory cache path.
References such as `${CLAUDE_PLUGIN_ROOT}/templates/` in shared prose mean that
resolved plugin root's `templates/` directory.

Before executing a setup shell block, bind `BITWIZE_PLUGIN_ROOT` to the resolved
absolute path in **that shell call**. Render the assignment with correct shell
quoting for the actual path; never execute an unresolved placeholder. All
requirements paths and interpreter paths must be quoted, including on Windows.

## Configuration and startup

Both hosts use `~/.bitwize-music/config.yaml`, `~/.bitwize-music/venv`, and the
configured content, audio, documents, and overrides directories. Read current
configuration before resolving workspace paths. Preserve existing config and
artist casing, and use the canonical configure skill for changes.

In Codex, explicitly invoke the installed `session-start` skill at the beginning
of a music session. A plugin's `CLAUDE.md` is not an automatic Codex startup
entry point. Read that file from the resolved plugin root as the shared workflow
guide, applying these runtime translations. Continue to load the configured
`overrides/CLAUDE.md` as the user's shared workflow customization.

After dependency installation, start a new session in the active host so MCP
can reconnect, rerun setup checks, then configure the workspace. Report observed
connection and dependency results; installation alone does not prove that the
host has connected to MCP.

See the official [Codex skill invocation guidance](https://learn.chatgpt.com/docs/build-skills#how-chatgpt-and-codex-use-skills).
