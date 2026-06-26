# Project Analyzer Skill for Ableton

**Description**: Analyzes Ableton project structure, track organization, routing, and plugin chains to provide optimization recommendations for mixing and mastering workflows.

**Use Case**: At the start of a session for organization review, or before export/mixdown for quality checks.

---

## Analysis Capabilities

### Track Organization
- Track naming conventions
- Color coding consistency
- Track grouping/folder structure
- Arrangement vs. Session view usage
- Clip naming and organization

### Routing & Bus Structure
- Input/output routing validation
- Return track utilization
- Subgroup/bus organization
- Sidechain routing detection
- Parallel processing chains

### Plugin Chain Analysis
- Plugin order optimization
- Gain staging verification
- CPU load distribution
- Unused plugin detection
- Preset documentation status

### Audio Quality Checks
- Clipping detection (track and master)
- Headroom assessment
- Phase correlation
- Frequency balance overview
- Dynamic range analysis

---

## Workflow

### Step 1: Project Scan
Call `ableton_get_project_info()` to retrieve:
- Total track count
- Audio vs. MIDI track breakdown
- Return tracks configuration
- Master bus chain
- Project sample rate and bit depth
- Tempo and time signature

### Step 2: Track-by-Track Analysis
For each track, analyze:
- **Name**: Is it descriptive? (e.g., "Lead Vocal" vs. "Audio 01")
- **Color**: Is it color-coded consistently?
- **Routing**: Where does input come from? Where does output go?
- **Plugins**: What's in the chain? Order optimal?
- **Levels**: Peak, RMS, headroom
- **Clips**: Properly named? Fades applied?

### Step 3: Routing Validation
Check for common issues:
- [ ] No tracks routed to non-existent buses
- [ ] Return tracks have appropriate send levels
- [ ] Master bus has headroom (-6 dBFS ideal for mixdown)
- [ ] No feedback loops in routing
- [ ] Sidechain sources are valid

### Step 4: Gain Staging Check
Verify signal flow:
- Individual tracks peaking around -18 to -12 dBFS
- Subgroups not clipping
- Master bus with adequate headroom
- No hidden gain boosts in plugin chains

### Step 5: Generate Report
Provide actionable recommendations organized by priority:

**Critical** (fix before proceeding):
- Clipping on any channel
- Routing errors
- Missing files/offline clips

**Important** (recommended fixes):
- Poor gain staging
- Disorganized track structure
- Missing fades on audio clips

**Optimization** (nice to have):
- Track naming improvements
- Color coding suggestions
- Plugin chain reordering

---

## Common Issues & Recommendations

### Issue: Undefined Track Names
**Detection**: Tracks named "Audio 01", "MIDI 03", etc.  
**Recommendation**: Rename to reflect content (e.g., "Lead Vocal", "Kick", "Bass Synth")

### Issue: No Color Coding
**Detection**: All tracks same color or default  
**Recommendation**: Implement color scheme (e.g., blue=vocals, red=drums, green=bass, yellow=synths)

### Issue: Master Bus Clipping
**Detection**: Master peak > 0 dBFS  
**Recommendation**: Reduce individual track levels or master fader; aim for -6 dBFS headroom

### Issue: Poor Gain Staging
**Detection**: Tracks peaking above -6 dBFS individually  
**Recommendation**: Use trim/gain plugins at start of chain to set proper levels

### Issue: Unorganized Routing
**Detection**: No subgroups, all tracks going direct to master  
**Recommendation**: Create subgroups (Drums, Bass, Instruments, Vocals) for cohesive processing

### Issue: Return Track Overuse
**Detection**: Excessive sends causing muddiness  
**Recommendation**: Consolidate similar effects; use parallel processing intentionally

### Issue: Plugin Chain Order
**Detection**: EQ after compression when corrective EQ needed first  
**Recommendation**: Reorder: corrective EQ → compression → tonal EQ → saturation → time-based effects

### Issue: Missing Clip Fades
**Detection**: Audio clips without fade-in/out at boundaries  
**Recommendation**: Apply small fades (5-10ms) to prevent clicks/pops

### Issue: Inconsistent Sample Rates
**Detection**: Mixed sample rate audio files in project  
**Recommendation**: Consolidate to project sample rate; warp settings verified

---

## MCP Tools for Ableton Integration

| Tool | Purpose |
|------|---------|
| `ableton_get_project_info()` | Get overall project structure and metadata |
| `ableton_list_tracks()` | Enumerate all tracks with properties |
| `ableton_get_track_info(track_id)` | Detailed info for specific track |
| `ableton_get_plugin_chain(track_id)` | List plugins in track's device chain |
| `ableton_analyze_audio(track_id)` | Measure levels, peaks, frequency content |
| `ableton_check_routing()` | Validate input/output routing across project |
| `ableton_detect_clipping()` | Scan for clipped samples across all tracks |
| `ableton_get_tempo_map()` | Retrieve tempo changes and automation |

---

## Report Template

```markdown
## Project Analysis Report

**Project**: [Project Name]
**Analyzed**: [Date/Time]
**Total Tracks**: [N] (Audio: [N], MIDI: [N])
**Sample Rate**: [Hz]
**Bit Depth**: [bit]
**Tempo**: [BPM]

---

### Summary
- **Critical Issues**: [N]
- **Important Issues**: [N]
- **Optimization Suggestions**: [N]

---

### Critical Issues (Fix Before Proceeding)

1. **[Issue Title]**
   - **Location**: [Track name/number]
   - **Problem**: [Description]
   - **Solution**: [Actionable fix]

---

### Important Issues (Recommended Fixes)

1. **[Issue Title]**
   - **Location**: [Track name/number]
   - **Problem**: [Description]
   - **Solution**: [Actionable fix]

---

### Optimization Suggestions

1. **[Suggestion Title]**
   - **Benefit**: [What improves]
   - **Implementation**: [How to apply]

---

### Track Organization Score: [X/10]
- Naming: [X/10]
- Color Coding: [X/10]
- Grouping: [X/10]

### Mix Readiness Score: [X/10]
- Gain Staging: [X/10]
- Headroom: [X/10]
- Routing: [X/10]
- Processing: [X/10]

---

### Next Steps
1. [Priority action 1]
2. [Priority action 2]
3. [Priority action 3]
```

---

## Best Practices

### Track Organization
- Name tracks descriptively from the start
- Use consistent color coding (create a legend)
- Group related tracks into folders/subgroups
- Keep arrangement view clean and labeled

### Gain Staging
- Aim for -18 to -12 dBFS average per track
- Leave -6 dBFS headroom on master for mastering
- Use gain/trim plugins at start of chain if needed
- Check levels after each processing stage

### Routing
- Create logical subgroups (Drums, Bass, Music, Vocals)
- Use return tracks for shared effects (reverb, delay)
- Document complex routing with comments
- Avoid excessive parallel processing without purpose

### Plugin Chains
- Order matters: corrective → dynamic → tonal → character → time-based
- Remove unused plugins to save CPU
- Document custom presets with descriptions
- Use EQ before compression for corrective work

### Before Export/Mixdown
- Run full project analysis
- Fix all critical issues
- Address important issues
- Verify no clipping anywhere
- Check phase correlation on master
- Ensure adequate headroom (-6 dBFS)

---

## Remember

1. **Organization saves time** — a clean session is easier to mix
2. **Gain staging is foundational** — fix levels before fancy processing
3. **Headroom is your friend** — leave space for mastering
4. **Naming matters** — future you will thank present you
5. **Subgroups enable cohesion** — process related elements together
6. **Document as you go** — notes help collaboration and recall
7. **Validate before export** — catch issues early, not after render
8. **Your deliverable**: Actionable report with prioritized recommendations
