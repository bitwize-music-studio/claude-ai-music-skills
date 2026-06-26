# Ableton MCP Tools Specification

This document defines the MCP tools needed to integrate the Producer Pal skills with Ableton Live.

---

## Project Management Tools

### `ableton_get_project_info()`
Retrieves overall project structure and metadata.

**Returns:**
```json
{
  "project_name": "Track Name",
  "sample_rate": 44100,
  "bit_depth": 24,
  "tempo": 120.0,
  "time_signature": [4, 4],
  "total_tracks": 16,
  "audio_tracks": 10,
  "midi_tracks": 6,
  "return_tracks": 4,
  "duration_seconds": 245.5,
  "master_bus_devices": ["EQ Eight", "Compressor", "Limiter"]
}
```

### `ableton_list_tracks()`
Enumerates all tracks with basic properties.

**Returns:**
```json
[
  {
    "track_id": "track_001",
    "name": "Lead Vocal",
    "type": "audio",
    "color": "blue",
    "armed": false,
    "solo": false,
    "mute": false,
    "volume_db": -3.5,
    "pan": 0.0,
    "output_routing": "Master"
  }
]
```

### `ableton_get_track_info(track_id)`
Gets detailed information for a specific track.

**Parameters:**
- `track_id` (string): Unique track identifier

**Returns:**
```json
{
  "track_id": "track_001",
  "name": "Lead Vocal",
  "type": "audio",
  "clips": [
    {
      "clip_id": "clip_001",
      "name": "Verse 1",
      "start_time": 0.0,
      "duration": 32.0,
      "warp_markers": [...]
    }
  ],
  "devices": [...],
  "sends": [
    {"send_id": "A", "value": 0.3},
    {"send_id": "B", "value": 0.0}
  ]
}
```

---

## Audio Analysis Tools

### `ableton_analyze_audio(track_id)`
Measures levels, peaks, frequency content, and loudness.

**Parameters:**
- `track_id` (string): Track to analyze (or "master" for master bus)

**Returns:**
```json
{
  "track_id": "track_001",
  "peak_db": -3.2,
  "rms_db": -18.5,
  "lufs_integrated": -16.2,
  "lufs_short_term": -14.8,
  "true_peak_db": -2.8,
  "dynamic_range": 12.5,
  "frequency_spectrum": {
    "sub_bass": -12.5,
    "bass": -10.2,
    "low_mid": -14.3,
    "mid": -16.1,
    "high_mid": -18.5,
    "high": -22.3
  },
  "stereo_width": 0.65,
  "phase_correlation": 0.82
}
```

### `ableton_detect_clipping()`
Scans for clipped samples across all tracks.

**Returns:**
```json
{
  "clipping_detected": true,
  "clipped_tracks": [
    {
      "track_id": "track_003",
      "track_name": "Drums",
      "clip_count": 15,
      "max_peak_db": 0.8
    }
  ],
  "master_clipping": false
}
```

### `ableton_check_routing()`
Validates input/output routing across the project.

**Returns:**
```json
{
  "routing_valid": true,
  "issues": [],
  "routing_map": {
    "track_001": {"input": "External In", "output": "Master"},
    "track_002": {"input": "Audio From", "output": "Bus_Drums"}
  }
}
```

---

## Processing Tools

### `ableton_insert_effect(track_id, effect_name, position)`
Inserts a plugin/device on a track's device chain.

**Parameters:**
- `track_id` (string): Target track
- `effect_name` (string): Name of effect (e.g., "EQ Eight", "Compressor")
- `position` (integer): Position in chain (0 = first)

**Returns:**
```json
{
  "success": true,
  "device_id": "device_001",
  "message": "EQ Eight inserted on Lead Vocal at position 0"
}
```

### `ableton_set_parameter(device_id, parameter_name, value)`
Adjusts a plugin parameter programmatically.

**Parameters:**
- `device_id` (string): Device identifier
- `parameter_name` (string): Parameter name
- `value` (float/string): Parameter value

**Returns:**
```json
{
  "success": true,
  "device_id": "device_001",
  "parameter": "Frequency",
  "value": 3000.0,
  "message": "EQ Eight Frequency set to 3000.0 Hz"
}
```

### `ableton_get_plugin_chain(track_id)`
Lists all plugins in a track's device chain with parameters.

**Parameters:**
- `track_id` (string): Track to query

**Returns:**
```json
[
  {
    "device_id": "device_001",
    "name": "EQ Eight",
    "position": 0,
    "parameters": {
      "Frequency A": 100.0,
      "Gain A": -3.0,
      "Q A": 1.0
    }
  }
]
```

---

## Export/Import Tools

### `ableton_export_stems(output_path, options)`
Exports individual tracks or stems to audio files.

**Parameters:**
- `output_path` (string): Destination folder
- `options` (object): Export settings

**Options:**
```json
{
  "format": "wav",
  "bit_depth": 24,
  "sample_rate": 44100,
  "include_effects": true,
  "normalize": false,
  "tracks": ["all"]  // or specific track IDs
}
```

**Returns:**
```json
{
  "success": true,
  "exported_files": [
    "/path/to/stems/Lead_Vocal.wav",
    "/path/to/stems/Drums.wav"
  ],
  "count": 10
}
```

### `ableton_export_master(output_path, options)`
Renders the final mastered output.

**Parameters:**
- `output_path` (string): Destination file path
- `options` (object): Export settings

**Returns:**
```json
{
  "success": true,
  "file_path": "/path/to/master/Final_Master.wav",
  "duration_seconds": 245.5,
  "peak_db": -1.0,
  "lufs": -14.2
}
```

### `ableton_import_audio(file_path, target_track)`
Imports audio files into the project.

**Parameters:**
- `file_path` (string): Path to audio file
- `target_track` (string): Track ID or "new" to create new track

**Returns:**
```json
{
  "success": true,
  "clip_id": "clip_001",
  "track_id": "track_001",
  "message": "Imported vocal.wav to Lead Vocal"
}
```

---

## Workflow Tools

### `ableton_apply_mix_preset(track_id, preset_name, genre)`
Applies a mixing preset to a track or stem group.

**Parameters:**
- `track_id` (string): Target track or "all" for multi-track
- `preset_name` (string): Preset name (e.g., "vocals_lead", "drums")
- `genre` (string): Genre for genre-specific settings

**Returns:**
```json
{
  "success": true,
  "applied_settings": {
    "eq": [...],
    "compression": {...},
    "gain_adjustment": 1.0
  },
  "message": "Applied hip-hop vocals preset to Lead Vocal"
}
```

### `ableton_apply_mastering_preset(preset_name, genre)`
Applies a mastering preset to the master bus.

**Parameters:**
- `preset_name` (string): Preset name
- `genre` (string): Genre for genre-specific settings

**Returns:**
```json
{
  "success": true,
  "target_lufs": -14.0,
  "true_peak": -1.0,
  "chain_configured": ["EQ Eight", "Compressor", "Saturator", "Limiter"],
  "message": "Applied hip-hop mastering preset"
}
```

### `ableton_validate_mastering(options)`
Validates mastered audio against quality standards.

**Parameters:**
- `options` (object): Validation criteria

**Returns:**
```json
{
  "passed": true,
  "checks": {
    "lufs_target": {"expected": -14.0, "actual": -14.2, "passed": true},
    "true_peak": {"expected": -1.0, "actual": -1.0, "passed": true},
    "clipping": {"passed": true},
    "mono_compatibility": {"passed": true}
  },
  "recommendations": []
}
```

---

## Implementation Notes

### Connection to Ableton
These tools would connect to Ableton Live via:
1. **AbletonOSC** - Open Sound Control protocol
2. **Live API** - Python scripting within Ableton
3. **MIDI Remote Scripts** - Custom bidirectional communication
4. **HTTP Server** - Custom Max for Live device with web server

### Recommended Architecture
```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  MCP Client     │────▶│  MCP Server      │────▶│  Ableton Live   │
│  (Producer Pal) │     │  (Python/Node)   │     │  (via OSC/API)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### Security Considerations
- Authenticate connections between MCP server and Ableton
- Validate all file paths before read/write operations
- Implement rate limiting for parameter changes
- Log all modifications for undo/rollback capability

### Error Handling
All tools should return consistent error format:
```json
{
  "success": false,
  "error_code": "TRACK_NOT_FOUND",
  "message": "Track 'track_999' does not exist in current project",
  "suggestion": "Use ableton_list_tracks() to see available tracks"
}
```
