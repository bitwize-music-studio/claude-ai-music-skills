# Ableton MCP Extension - Producer Pal Skills

This directory contains specialized skills for music production, mixing, and mastering within Ableton Live. These skills are adapted from the Claude AI Music Skills project and optimized for integration with Ableton's workflow.

## Structure

```
ableton-mcp-extension/
├── skills/           # Individual skill definitions (mix-engineer, mastering-engineer, etc.)
├── knowledge/        # Reference knowledge base
│   ├── presets/      # Genre-specific presets for mixing and mastering
│   └── genres/       # Detailed genre guides and conventions
└── tools/            # MCP tool implementations for Ableton integration
```

## Core Skills

### 1. Mix Engineer (`skills/mix-engineer.md`)
Polishes raw audio by processing per-stem WAVs with targeted cleanup, EQ, and compression.

**Key Features:**
- Per-stem processing (vocals, drums, bass, guitar, keys, etc.)
- Noise reduction and click removal
- Frequency coordination with mastering stage
- Genre-specific preset overrides
- Non-destructive processing

**Workflow:**
1. Analyze mix issues (noise, muddiness, harshness, clicks)
2. Apply genre-appropriate stem processing
3. Verify polished output meets quality standards
4. Hand off to mastering engineer

### 2. Mastering Engineer (`skills/mastering-engineer.md`)
Guides audio mastering for streaming platforms including loudness optimization and tonal balance.

**Key Features:**
- LUFS target optimization (-14 LUFS universal, genre-specific variants)
- Platform-aware mastering (Spotify, Apple Music, YouTube, etc.)
- True peak limiting (-1.0 dBTP standard)
- Dynamic range preservation
- Quality control validation

**Workflow:**
1. Analyze tracks for loudness, peaks, frequency balance
2. Apply mastering chain with appropriate settings
3. Verify results meet platform targets
4. Generate delivery-ready files

### 3. Project Analyzer (`skills/project-analyzer.md`)
Analyzes Ableton project structure and provides recommendations.

**Key Features:**
- Track organization review
- Routing and bus structure analysis
- Plugin chain optimization suggestions
- Session vs. Arrangement view guidance

## Knowledge Base

### Genre Presets (`knowledge/presets/`)
Contains YAML configuration files with genre-specific settings:

- `mix-presets.yaml` - Per-stem processing settings by genre
- `mastering-presets.yaml` - Mastering chain settings by genre
- `production-presets.yaml` - Production techniques by genre

### Genre Guides (`knowledge/genres/`)
Detailed documentation for 72+ music genres including:

- Instrumentation and production characteristics
- Lyric conventions (for vocal genres)
- Subgenre breakdowns
- Reference artists and tracks
- Suno/AI prompt keywords
- Tempo and structure guidelines

## Integration with Ableton

These skills are designed to work with Ableton Live through MCP tools that can:

1. **Read Project State**: Extract track info, plugin chains, routing
2. **Apply Processing**: Insert effects, adjust parameters, automate changes
3. **Export/Import**: Manage stems, bounced tracks, and final renders
4. **Validate Output**: Check levels, frequency balance, compliance

## Usage Pattern

```
User Request → Skill Selection → Knowledge Lookup → MCP Tool Execution → Ableton Action
```

Example: "Master this track for Spotify"
1. Select `mastering-engineer` skill
2. Load genre preset (e.g., hip-hop)
3. Call `ableton_export_stems()` or `ableton_get_master_bus()`
4. Apply mastering chain via `ableton_insert_effect()`
5. Validate with `ableton_analyze_audio()`
6. Render final master

## Customization

Override default presets by creating custom YAML files in your user overrides directory:

```yaml
# {overrides}/mix-presets.yaml
genres:
  dark-electronic:
    vocals:
      noise_reduction: 0.8
      high_tame_db: -3.0
    bass:
      highpass_cutoff: 20
      gain_db: 2.0
```

## Best Practices

1. **Stems First**: Always prefer per-stem processing when available
2. **Analyze Before Processing**: Understand problems before applying fixes
3. **Be Conservative**: Default settings are calibrated for typical output
4. **Non-Destructive**: Preserve originals; write processed files to new locations
5. **Genre-Aware**: Use genre presets as starting points, not absolutes
6. **Quality Gates**: Validate at each stage before proceeding
