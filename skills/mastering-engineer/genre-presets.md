# Genre-Specific Mastering Presets

Detailed mastering settings by genre.

---

## Platform Targets Reference

### Spotify
- **Target**: -14 LUFS integrated
- **True peak**: -1.0 dBTP
- **What happens**: Tracks louder than -14 turned down, quieter turned up
- **Strategy**: Master to -14, maintain dynamics

### Apple Music
- **Target**: -16 LUFS integrated
- **True peak**: -1.0 dBTP
- **What happens**: "Sound Check" normalizes playback
- **Strategy**: Master to -14 (won't be turned up, preserves dynamics)

### YouTube
- **Target**: -13 to -15 LUFS
- **True peak**: -1.0 dBTP
- **What happens**: Normalization to -14 LUFS
- **Strategy**: -14 LUFS works perfectly

### SoundCloud
- **Target**: No normalization
- **Strategy**: -14 LUFS for consistency with streaming platforms

### Bandcamp
- **Target**: No normalization (listener controls volume)
- **Strategy**: -14 LUFS, but can go louder (-12) if genre appropriate

---

## Genre Presets

### Hip-Hop / Rap
**LUFS target**: -12 to -14 LUFS
**Dynamics**: Moderate compression, punchy transients
**EQ focus**: Sub-bass presence (40-60 Hz), vocal clarity (2-4 kHz)
**MCP command**: `master_audio(album_slug, genre="hip-hop")`

**Characteristics**:
- Strong low end
- Clear vocals
- Punchy kick/snare

### Rock / Alternative
**LUFS target**: -12 to -14 LUFS
**Dynamics**: Wide dynamic range, preserve peaks
**EQ focus**: Guitar presence (800 Hz - 3 kHz), avoid harsh highs
**MCP command**: `master_audio(album_slug, genre="rock")`

**Characteristics**:
- Guitar energy
- Drum impact
- Vocal cut-through

### Nu-Metal
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the groove and bounce that define the genre; nu-metal's quiet-loud dynamics between restrained verses and explosive choruses need headroom -- over-compression flattens the emotional contrast
**EQ focus**: Low-end weight from downtuned guitars and bass (60-200 Hz), vocal clarity across all styles (rapped, screamed, sung) at 2-5 kHz, gentle high-mid cut to tame scooped-mid guitar harshness (3-5 kHz), bass guitar presence (80-200 Hz)
**MCP command**: `master_audio(album_slug, genre="nu-metal")`

**Characteristics**:
- Bass guitar is more prominent than in most metal subgenres -- often funk-influenced slap style or heavily distorted; keep it defined and punchy, not buried
- Downtuned seven-string guitars produce heavy low-mid content (100-300 Hz); careful separation from bass guitar prevents mud
- Vocal styles vary wildly within a single song (rapping, singing, screaming) -- mastering must accommodate all three without favoring one; vocal clarity at 2-5 kHz critical
- DJ scratching and electronic samples sit in the upper-mid range (2-6 kHz); preserve their presence without harshness
- Groove and rhythmic clarity are the priority -- kick and snare punch must cut through the low-end density; triggered-sounding kicks acceptable
- Scooped-mid guitar tone is intentional to the genre -- do not try to "fix" the mid-scoop; it leaves room for vocals and bass

### Stoner Rock
**LUFS target**: -14 LUFS (stoner doom: -16 LUFS; desert rock/fuzz rock: -14 LUFS)
**Dynamics**: Moderate compression; preserve the natural weight and sustain of fuzz-drenched riffs; avoid squashing the groove -- stoner rock lives in the space between riff hits, and over-compression kills the head-nodding feel
**EQ focus**: Low-end body and warmth (60-200 Hz), guitar fuzz presence (800 Hz-3 kHz with gentle high-mid cut to tame fizzy harshness without killing the distortion character), bass guitar definition (80-200 Hz)
**MCP command**: `master_audio(album_slug, genre="stoner-rock")`

**Characteristics**:
- Fuzz guitar tone is the genre's identity -- preserve the thick, saturated distortion with its harmonic overtones; do not over-cut the upper harmonics that give fuzz its character
- Bass and guitar often occupy similar frequency ranges due to shared downtuning; careful low-mid separation (150-400 Hz) prevents mud without thinning the combined wall of sound
- High-mid harshness at 3-5 kHz from fuzz pedals: moderate cuts (-2 to -2.5 dB); aggressive cutting removes the bite that defines the tone
- Stoner doom tracks (-16 LUFS): wider dynamics, preserve the crushing weight of slow riffs; minimal compression to maintain the natural sag and swell
- Desert rock and fuzz rock (-14 LUFS): tighter compression acceptable, punchier drums, more energy and drive
- Psychedelic stoner tracks with extended jams: preserve reverb tails and delay effects; these are compositional elements
- Warm, analog-sounding master preferred -- avoid overly bright or clinical limiting; the genre's retro production aesthetic should carry through to mastering

### Post-Punk
**LUFS target**: -14 LUFS (atmospheric/gothic: -15 LUFS)
**Dynamics**: Moderate compression; preserve the interplay between bass and guitar textures; avoid squashing reverb tails and delay effects that define the genre's spatial character
**EQ focus**: Bass presence and clarity (80-300 Hz), guitar texture preservation (800 Hz-3 kHz with gentle high-mid cut to tame angular guitar harshness), vocal clarity without brightness
**MCP command**: `master_audio(album_slug, genre="post-punk")`

**Characteristics**:
- Bass is the melodic center — must remain clear, present, and defined; do not let it become muddy or buried
- Angular guitar sits in the upper-mid range; cut harshness at 3-4 kHz but preserve the chorus/flanger/delay textures that define the genre
- Reverb and delay are compositional elements, not decoration — over-compression collapses the spatial depth that post-punk depends on
- Atmospheric/gothic tracks can target -15 LUFS for wider dynamics and more reverb headroom
- Dance-punk subgenre: tighter compression, punchier kick and bass, can push to -14 LUFS
- Vocals should sit within the mix, not on top of it — post-punk often buries vocals slightly behind instrumentation

### Noise Rock
**LUFS target**: -14 LUFS (sludge-noise: -12 to -14 LUFS)
**Dynamics**: Minimal compression — noise rock's dynamics come from the instruments themselves; over-compression flattens the contrast between feedback swells and rhythmic attacks that define the genre
**EQ focus**: Low-end weight (60-200 Hz for bass distortion body), high-mid presence preserved but harsh resonances tamed (3-5 kHz), avoid cutting too much — harshness is intentional
**MCP command**: `master_audio(album_slug, genre="noise-rock")`

**Characteristics**:
- Distortion and feedback are compositional elements — do not treat them as problems to solve
- Bass distortion needs body and weight; cutting low-mids too aggressively thins the genre's fundamental sound
- High-mid harshness at 3-5 kHz: gentle cuts only, -2 to -3 dB; aggressive cutting removes the abrasive edge that defines noise rock
- Lo-fi and room sound are features — do not over-process or "clean up" the recording
- Sludge-noise (Melvins, Unsane style): heavier limiting acceptable, push to -12 LUFS for crushing weight
- Power-duo acts (Lightning Bolt style): bass guitar fills the entire low-mid spectrum; ensure it doesn't mud up but retains its massive presence
- Art-noise and no-wave-derived tracks: wider dynamics, may sit at -15 LUFS to preserve quiet/loud contrasts

### Math Rock
**LUFS target**: -14 LUFS (atmospheric/Japanese math rock: -15 LUFS)
**Dynamics**: Moderate compression; preserve the rhythmic interplay between instruments -- math rock's stop-start dynamics and metric shifts must remain articulate; avoid squashing transients that define the genre's percussive guitar style
**EQ focus**: Guitar clarity and separation (1-4 kHz), drum transient definition (3-5 kHz), bass note articulation (80-200 Hz); gentle high-mid cut to tame Suno-generated brightness without losing the clean guitar attack
**MCP command**: `master_audio(album_slug, genre="math-rock")`

**Characteristics**:
- Guitar tapping and harmonics sit in the 1-5 kHz range -- preserve articulation and note separation; over-compression blurs tapped passages into mush
- Drumming is technical and dynamic -- transient clarity is essential; kick and snare must punch through without overwhelming the guitar interplay
- Dry production aesthetic: minimal reverb is intentional -- do not add spaciousness that wasn't there
- Japanese math rock (toe, Lite style): slightly wider dynamics acceptable, target -15 LUFS for warmer, more atmospheric sound
- Noise-math (Hella, Tera Melos style): treat more like noise rock mastering -- preserve distortion and aggression, push to -14 LUFS
- Progressive math rock (Polyphia, CHON): cleaner production, more polished; treat like modern rock mastering with emphasis on guitar clarity
- Bass guitar often carries melodic lines -- keep it defined and present, not buried or boomy

### Death Metal
**LUFS target**: -14 LUFS
**Dynamics**: Heavy compression; sustain the wall-of-sound density without crushing blast beats; preserve kick drum articulation through double-bass passages
**EQ focus**: Low-end tightness (60-200 Hz), vocal presence through the distortion wall (1-4 kHz), high-mid cut to tame guitar fizz (3-5 kHz), gentle high shelf cut for cymbal wash control
**MCP command**: `master_audio(album_slug, genre="death-metal")`

**Characteristics**:
- Growled/guttural vocals sit inside the mix, not on top -- preserve intelligibility without pushing them artificially forward
- Blast beats generate dense high-frequency content from cymbals; gentle high shelf cut (-1 dB at 8 kHz) prevents listening fatigue
- Double bass drum patterns need kick definition at 60-80 Hz without mud; tight low-end essential
- Tremolo-picked guitars create a wall of harmonic content in the 1-5 kHz range; cut harshness but preserve the aggression
- Technical/progressive death metal benefits from slightly wider dynamics to showcase rhythmic complexity
- Old-school death metal (Morbid Angel, Death style): warmer, less polished mastering; modern (Archspire style): tighter, more clinical

### Grindcore
**LUFS target**: -14 LUFS
**Dynamics**: Heavy compression; sustain the relentless blast-beat density; preserve the raw, chaotic energy without over-polishing; grindcore's lo-fi production aesthetic is often intentional
**EQ focus**: Low-end density (60-200 Hz), vocal presence through distortion wall (1-4 kHz), high-mid cut to tame guitar and cymbal harshness (3-5 kHz), high shelf cut for cymbal wash control from constant blast beats
**MCP command**: `master_audio(album_slug, genre="grindcore")`

**Characteristics**:
- Blast beats generate massive high-frequency cymbal content; high shelf cut (-1 dB at 8 kHz) essential to prevent listening fatigue across an entire album of blasting
- Dual vocals (growls + shrieks) occupy different frequency ranges; both need presence without one dominating the other
- Guitar and bass often blend into a single wall of distortion; do not try to separate them surgically -- the blurred density is intentional
- Raw, lo-fi production is a genre feature in classic grindcore; do not over-process or "clean up" recordings that are intentionally crude
- Songs are extremely short (30 seconds to 2 minutes); consistent level between tracks is important since gaps are brief
- Deathgrind (Terrorizer, Cattle Decapitation): tighter, more death metal-influenced mastering; treat closer to death metal preset
- Powerviolence-influenced (Nails, Full of Hell): preserve extreme tempo shifts between blasting and sludge sections; dynamic contrast matters
- Cybergrind with electronic elements: drum machines may need different treatment than acoustic drums; preserve the mechanical quality

### Electronic / EDM
**LUFS target**: -10 to -12 LUFS (can go louder)
**Dynamics**: Heavy compression, consistent energy
**EQ focus**: Sub-bass (30-50 Hz), sparkle on top (10+ kHz)
**MCP command**: `master_audio(album_slug, genre="edm")`

**Characteristics**:
- Massive bass
- Sustained energy
- Bright, polished highs

### Eurodance
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the punch and drive of the four-on-the-floor kick while maintaining vocal clarity across both rapped and sung passages; avoid over-compression that flattens the euphoric dynamics of chorus builds
**EQ focus**: Kick and bass punch (50-100 Hz), synth lead presence and brightness (2-8 kHz), vocal clarity for both female singing and male rapping (2-5 kHz), gentle high-mid cut to tame harsh synth stabs (3.5-5 kHz)
**MCP command**: `master_audio(album_slug, genre="eurodance")`

**Characteristics**:
- The four-on-the-floor kick must be punchy and driving at 50-100 Hz; it is the rhythmic backbone and must stay prominent against the synth bass
- Synth leads and pads occupy a wide frequency range (200 Hz-8 kHz); keep them bright and present without harshness, especially on supersaw and arpeggiated leads
- Dual vocal styles (female sung choruses + male rap verses) require clarity across different frequency ranges; female vocals need presence at 3-5 kHz, male rap vocals need definition at 2-4 kHz
- Orchestral stabs and brass hits are transient-heavy; preserve their impact without allowing them to dominate the mix
- Sidechain pumping effect is intentional and genre-defining -- do not try to eliminate it; ensure the kick triggers the sidechain cleanly
- Bright, polished overall tone is expected; Eurodance should sound clean and radio-ready, not lo-fi or raw

### Tech House
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the rolling groove and percussive dynamics that define the genre; over-compression flattens the subtle interplay between kick, bass, and layered percussion that makes tech house work on the dancefloor
**EQ focus**: Kick punch and definition (50-80 Hz), rolling bassline presence (80-200 Hz), percussion clarity (2-5 kHz), gentle high-mid cut to tame crisp hi-hat brightness without losing groove detail (3-5 kHz)
**MCP command**: `master_audio(album_slug, genre="tech-house")`

**Characteristics**:
- The 909-style kick drum must be tight, punchy, and well-defined at 50-80 Hz; it drives the entire track and must cut through sub-bass content cleanly
- Rolling basslines (often mid-range, 80-200 Hz) are the harmonic backbone; keep them warm and defined without muddying the kick drum
- Layered percussion (congas, shakers, rim shots, claps) creates the polyrhythmic groove; preserve transient clarity in the 2-5 kHz range
- Sidechain compression pumping between kick and bass is intentional and defines the genre's rhythmic feel; preserve the breathing effect
- Vocal chops and spoken samples are rhythmic elements, not melodic features; they should sit inside the mix, not on top of it
- Sub-bass content should be controlled and tight, not boomy; tech house favors mid-bass punch over deep sub-bass weight
- Minimal tech house variants: slightly wider dynamics, more space in the mix; bass-heavy festival variants: tighter compression, stronger low end acceptable
- Extended DJ intros and outros should maintain consistent level with the body of the track

### Electropop
**LUFS target**: -14 LUFS (club-oriented tracks: -12 LUFS)
**Dynamics**: Moderate-to-heavy compression; preserve the punch and clarity of electronic drums while maintaining vocal presence; the genre demands a polished, radio-ready loudness without squashing the synth dynamics
**EQ focus**: Vocal clarity and presence (2-5 kHz), synth pad warmth (200-600 Hz), sub-bass definition (40-80 Hz), gentle high-mid cut (-1 dB at 3.5 kHz) to tame bright synth stacks without killing the sparkle
**MCP command**: `master_audio(album_slug, genre="electropop")`

**Characteristics**:
- Vocals are always the centerpiece -- clear, present, and forward in the mix; processed vocals (auto-tune, layering) should remain intelligible
- Synth layers occupy a wide frequency range; careful EQ separation prevents masking between pads, arpeggios, and bass synth
- Electronic kick and snare need punch and definition; sidechain compression on synths against the kick is often baked into the mix -- preserve that pumping effect
- Sub-bass (40-80 Hz) should be tight and controlled, not boomy; electropop bass sits higher than EDM bass
- Bright, polished high end (8-12 kHz) for shimmer and air, but watch for harshness from stacked synth harmonics
- Dark electropop (Depeche Mode style): slightly wider dynamics, warmer treatment, can target -15 LUFS
- Club-oriented tracks can push to -12 LUFS with heavier limiting for dancefloor energy
- Indie electropop: slightly less compression than mainstream; preserve lo-fi textures if intentional

### Deep House
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the warm, open groove and subtle dynamic shifts; deep house lives in its spaciousness -- over-compression kills the late-night intimacy and hypnotic feel
**EQ focus**: Sub-bass warmth (40-80 Hz), Rhodes/keys presence (200-500 Hz), vocal sample clarity (2-4 kHz), gentle high-mid cut at 3.5 kHz to tame hi-hat harshness, airy top-end for reverb tails (10+ kHz)
**MCP command**: `master_audio(album_slug, genre="deep-house")`

**Characteristics**:
- Sub-bass should be warm and round, not aggressive or punchy -- deep house bass is felt more than heard, sitting lower than tech house or mainroom house
- Kick drum has a softer attack than peak-time house; preserve the pillowy, warm character rather than pushing for maximum transient impact
- Rhodes, Wurlitzer, and jazz guitar samples sit in the 200-500 Hz range; keep them warm and defined without muddiness
- Reverb and delay are integral to the spatial atmosphere -- mastering should preserve the depth and width of the mix; avoid limiting that flattens the stereo image
- Soulful vocal samples and spoken word elements need warmth and intimacy at 2-4 kHz; avoid harshness that breaks the dreamy quality
- Shuffled hi-hats and subtle percussion (shakers, rim clicks) at 8-12 kHz drive the groove; preserve their crisp detail without brightness fatigue over long listening sessions
- Afro deep house variants may have more percussive energy; organic house variants should be treated even more gently with wider dynamics

### Nu Disco
**LUFS target**: -14 LUFS (cosmic/slow-motion strains: -15 LUFS)
**Dynamics**: Moderate compression; preserve the warm groove and dynamic builds; nu disco's filtered sweeps and gradual arrangement layering need headroom -- over-compression flattens the build-and-release that drives the dance floor
**EQ focus**: Bass warmth and groove (60-200 Hz), synth and vocal clarity (2-5 kHz), gentle high-mid cut at 3.5 kHz to tame harshness from layered synths, sparkle on hi-hats and percussion (8-12 kHz)
**MCP command**: `master_audio(album_slug, genre="nu-disco")`

**Characteristics**:
- Sidechain compression pumping is an intentional stylistic element -- do not try to smooth it out; the "breathing" effect on synth pads and bass is central to the genre's feel
- Bass should be warm, round, and melodic (funk/disco tradition) rather than sub-heavy; it sits higher than EDM bass (60-200 Hz)
- Filter sweeps on synths and samples are compositional tools -- preserve their full frequency range and dynamic arc
- Soulful vocals need warmth and presence without harshness; vocoder and processed vocals at 2-4 kHz should remain clear and defined
- Cosmic/space disco strains (-15 LUFS): wider dynamics, more reverb headroom, gentler compression for the hypnotic, spaced-out quality
- Disco house and club-oriented tracks: tighter compression acceptable, punchier kick at 60-80 Hz, brighter top end for peak-time energy
- String and brass samples (real or synthesized) add orchestral warmth at 200-600 Hz; keep them lush without muddiness
- Extended mixes (5-8 minutes) need consistent energy across their duration; avoid limiting that causes fatigue over long DJ sets

### Progressive House
**LUFS target**: -14 LUFS (deep progressive: -15 LUFS)
**Dynamics**: Light-to-moderate compression; preserve the gradual builds and extended dynamic arcs that define the genre; progressive house lives in the tension between quiet breakdowns and euphoric peaks -- over-compression destroys this emotional architecture
**EQ focus**: Pad warmth and body (200-600 Hz), synth lead clarity (1-4 kHz), sub-bass definition (40-80 Hz), gentle high-mid cut to tame bright synth harmonics without losing shimmer (3-5 kHz)
**MCP command**: `master_audio(album_slug, genre="progressive-house")`

**Characteristics**:
- Extended builds (32-64 bars) rely on gradual dynamic increase -- over-limiting flattens the arc and removes the emotional payoff at the climax
- Layered pads and atmospheric textures occupy the mid-range (200 Hz-2 kHz); preserve their warmth and spatial depth without muddiness
- Four-on-the-floor kick must remain consistent and punchy (60-80 Hz) but not dominate; it anchors the groove while melodies carry the emotion
- Reverb tails, delay trails, and filtered sweeps are compositional elements -- over-compression collapses the spatial depth that defines the genre
- Deep progressive (Guy J, Hernan Cattaneo style): target -15 LUFS, wider dynamics, more spacious and hypnotic; minimal compression to preserve subtle textural shifts
- Big room progressive (festival variant): can push to -14 LUFS with tighter compression; punchier kick, brighter leads, less subtlety acceptable
- Sidechain compression pumping on pads is intentional and genre-defining; preserve the rhythmic breathing effect
- Melodic progressive (Eric Prydz, deadmau5 style): synth leads in the 1-4 kHz range need clarity and emotional presence without harshness

### Jungle
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the chopped breakbeat dynamics and rapid-fire snare rolls; avoid squashing the rhythmic complexity that defines the genre
**EQ focus**: Sub-bass weight (30-60 Hz), breakbeat clarity (2-5 kHz), gentle high-mid cut to tame cymbal harshness from time-stretched breaks
**MCP command**: `master_audio(album_slug, genre="jungle")`

**Characteristics**:
- Chopped Amen breaks and other breakbeats are the genre's backbone -- preserve their dynamics and attack transients
- Sub-bass must be deep and powerful (30-60 Hz) but separate from the breakbeat energy above
- Ragga/MC vocals sit on top of dense rhythmic layers; vocal clarity at 2-4 kHz without harshness
- Time-stretched and pitch-shifted breaks can introduce artifacts in the 4-8 kHz range; gentle cuts as needed
- Reese bass (detuned sawtooth) occupies a wide low-mid range; keep it defined without muddying the breaks
- Darkside jungle: heavier, darker treatment acceptable; liquid/intelligent jungle: cleaner, more spacious mastering

### UK Garage
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the shuffled 2-step groove and bass bounce; avoid flattening the syncopated swing that defines the rhythm
**EQ focus**: Bass warmth and punch (60-150 Hz), vocal clarity (2-5 kHz), crisp hi-hat and percussion detail (8-12 kHz)
**MCP command**: `master_audio(album_slug, genre="uk-garage")`

**Characteristics**:
- 2-step rhythm is syncopated and swing-based -- over-compression destroys the bounce and groove feel
- Bass should be warm and round, not sub-heavy like dubstep; garage bass sits higher (60-150 Hz)
- R&B-influenced vocals need warmth and presence without harshness; pitch-shifted vocals common
- Crisp percussion (shakers, hi-hats, rim clicks) at 8-12 kHz drives the groove; preserve transient detail
- Organ stabs and chopped vocal samples are signature elements; keep them punchy and defined
- Speed garage variants can push slightly louder; 2-step house leans cleaner and more spacious

### Folk / Acoustic
**LUFS target**: -14 to -16 LUFS
**Dynamics**: Preserve natural dynamics
**EQ focus**: Warmth (200-500 Hz), natural highs
**MCP command**: `master_audio(album_slug, genre="folk")`

**Characteristics**:
- Natural, intimate
- Wide dynamic range
- Minimal processing

### Country
**LUFS target**: -13 to -14 LUFS
**Dynamics**: Moderate, radio-ready
**EQ focus**: Vocal clarity, steel guitar presence
**MCP command**: `master_audio(album_slug, genre="country")`

**Characteristics**:
- Clear vocals
- Instrument separation
- Warm, polished

### Jazz / Classical
**LUFS target**: -16 to -18 LUFS
**Dynamics**: Preserve full dynamic range
**EQ focus**: Natural tonal balance, minimal EQ
**MCP command**: `master_audio(album_slug, genre="jazz")`

**Characteristics**:
- Wide dynamics
- Natural room sound
- Uncompressed peaks

### Soundtrack / Film Theme Songs
**LUFS target**: -14 LUFS (power ballads: -13 LUFS; intimate film ballads: -15 LUFS)
**Dynamics**: Moderate compression — vocal always intelligible and forward; preserve dynamic arc from quiet verse to full-belt chorus; avoid over-compressing orchestral builds
**EQ focus**: Vocal presence (2-5 kHz), orchestral warmth (200-600 Hz), gentle high-mid cut to control brass brightness without losing sparkle
**MCP command**: `master_audio(album_slug, genre="soundtrack")`

**Characteristics**:
- Voice absolutely upfront — this is a song, not underscore; lyrics must be heard
- Power ballads (-13 LUFS) compete with mainstream pop — aggressive but controlled limiting
- Bond-style themes: wide dynamic range, brass transients need headroom, tremolo guitar clarity at 2-4 kHz
- Disco soundtracks: punchy kick at 60-80 Hz, four-on-the-floor energy; treat like Funk at -14 LUFS
- Intimate Golden Age ballads (-15 LUFS): preserve natural room acoustic, minimal processing
- Needle drops use their original mastering — no remastering needed for compilation context

### Musicals / Musical Theater
**LUFS target**: -16 LUFS (contemporary rock musicals: -14 LUFS)
**Dynamics**: Wide dynamic range preserved — intimate ballads must stay quiet, showstoppers can soar; avoid over-compression that flattens the emotional arc
**EQ focus**: Vocal intelligibility (1-4 kHz), pit orchestra warmth (200-600 Hz), gentle high-mid cut to tame bright Suno-generated brass
**MCP command**: `master_audio(album_slug, genre="musicals")`

**Characteristics**:
- Voice always upfront and intelligible — lyrics carry the drama
- Wide dynamic swing between ballad passages and full-company numbers
- Pit orchestra body in 200-600 Hz range needs warmth without muddiness
- Brass and strings must coexist without harshness above 4 kHz
- Contemporary/rock musicals (Hamilton style) can push to -14 LUFS with more compression
- Cast album aesthetic: theatrical room ambience preserved, not over-dried

### Schlager
**LUFS target**: -12 to -14 LUFS
**Dynamics**: Moderate-to-heavy compression, radio-ready loudness
**EQ focus**: Vocal presence (2-5 kHz), bass drum punch (60-100 Hz), bright top end (8-12 kHz for shimmer)
**MCP command**: `master_audio(album_slug, genre="schlager")`

**Characteristics**:
- Vocals dominant and upfront
- Kick drum punchy and defined
- Bright, polished, singalong-ready
- Synthesizer and brass clarity
- Party tracks can push to -11 LUFS

### Middle Eastern Pop
**LUFS target**: -14 LUFS (mahraganat: -12 LUFS)
**Dynamics**: Moderate compression, preserve vocal ornamentations and melismatic runs
**EQ focus**: Vocal presence (1-4 kHz), oud/qanun body (200-600 Hz), darbuka attack (3-5 kHz), gentle high-mid cut to tame synth harshness
**MCP command**: `master_audio(album_slug, genre="middle-eastern-pop")`

**Characteristics**:
- Melismatic vocals need headroom — avoid over-compressing ornamental runs
- Quarter-tone melodies require careful limiting to avoid pitch artifacts
- Darbuka and riq transients should remain crisp and defined
- Raï tracks: slightly more aggressive compression, accordion warmth preserved
- Mahraganat: louder target (-12 LUFS), heavier compression, bass-forward mix

### Chanson
**LUFS target**: -14 to -16 LUFS
**Dynamics**: Light compression, preserve natural dynamics and rubato phrasing
**EQ focus**: Vocal transparency (1-4 kHz), accordion warmth (200-800 Hz), gentle high cut above 12 kHz for vintage warmth
**MCP command**: `master_audio(album_slug, genre="chanson")`

**Characteristics**:
- Voice is absolute center — pristine clarity without harshness
- Accordion/guitar body preserved, not thinned out
- Room ambience and intimacy maintained
- Dynamic range wider than pop — quiet passages stay quiet
- Nouvelle chanson with electronic elements can target -14 LUFS; traditional acoustic chanson sits at -15 to -16

### Children's Music
**LUFS target**: -14 LUFS (lullabies: -16 LUFS)
**Dynamics**: Light compression, consistent volume critical for playback in cars and classrooms
**EQ focus**: Vocal clarity (2-4 kHz), warmth (200-500 Hz), gentle high-mid cut to avoid harshness on small speakers
**MCP command**: `master_audio(album_slug, genre="childrens-music")`

**Characteristics**:
- Vocals must be clear, warm, and front-center at all times
- Avoid harsh sibilance — small ears are sensitive to high frequencies
- Lullabies target -16 LUFS with minimal compression for gentle dynamics
- Singalong/action songs can sit at -14 LUFS with moderate compression
- Low dynamic range preferred — avoid sudden volume jumps (safety for children's playback)
- Ukulele and xylophone brightness tamed without losing sparkle

### Bollywood
**LUFS target**: -14 LUFS (classical filmi/ghazal: -15 LUFS; bhangra/item numbers: -13 LUFS)
**Dynamics**: Moderate compression; preserve vocal ornamentation (meend glides and taan runs need headroom); allow natural dynamic arc from intimate verse to full-orchestra chorus
**EQ focus**: Vocal clarity (2-5 kHz), tabla and dholak attack (3-5 kHz), string warmth (200-600 Hz), gentle high-mid cut to tame Suno-generated brightness in orchestral layers
**MCP command**: `master_audio(album_slug, genre="bollywood")`

**Characteristics**:
- Playback vocal is always the center — strings, tabla, and harmonium exist to support it, never overwhelm
- Ornamental vocal runs (meend, taan) require headroom — over-compression smears them into muddy sustain
- Tabla transients should remain crisp and defined; dholak body (150-250 Hz) needs warmth without muddiness
- Classical filmi tracks (-15 LUFS): preserve the wide dynamic range between intimate vocal passages and full orchestral moments
- Bhangra and item numbers (-13 LUFS): more compression acceptable, dhol punch at 60-100 Hz, bright top end for dancefloor energy
- Sitar and bansuri harmonics sit in 1.5-4 kHz range — avoid over-cutting here or they disappear in the mix
- Contemporary Bollywood pop with electronic production: treat sub-bass and EDM elements like mainstream pop; maintain vocal warmth on top

### Contemporary Christian (CCM)
**LUFS target**: -14 LUFS (worship ballads: -15 LUFS; anthemic rock: -13 LUFS)
**Dynamics**: Moderate compression; preserve dynamic builds from quiet verses to anthemic choruses; CCM relies on emotional swells and should not sound flat
**EQ focus**: Vocal clarity and warmth (2-5 kHz), piano/acoustic guitar body (200-500 Hz), gentle high-mid cut to tame Suno-generated brightness in layered arrangements
**MCP command**: `master_audio(album_slug, genre="contemporary-christian")`

**Characteristics**:
- Vocals are always the centerpiece — clear, warm, and emotionally present; never buried behind production
- CCM pop tracks sit at -14 LUFS with polished, radio-ready compression similar to mainstream pop
- Christian rock subgenre: treat like alternative/rock mastering (-14 LUFS, stronger high-mid cuts at -2.0 dB)
- Christian hip-hop (CHH): treat like mainstream hip-hop mastering (-14 LUFS, punchy low end, vocal clarity)
- Worship ballads with piano and pads: target -15 LUFS, preserve wide dynamics and room ambience
- Anthemic praise tracks with full band: can push to -13 LUFS with more compression for energy
- Group vocal harmonies and choir elements need headroom — over-compression smears layered voices into mush
- See also: Worship preset below for church-specific worship music mastering

### Worship
**LUFS target**: -14 LUFS (intimate/devotional: -15 LUFS; uptempo praise: -13 LUFS)
**Dynamics**: Moderate compression; preserve the dynamic arc from quiet verse to full-band chorus build; worship music relies on crescendo and release, so avoid squashing those transitions
**EQ focus**: Vocal warmth and clarity (2-5 kHz), pad/synth body (200-500 Hz), gentle high-mid cut to tame ambient guitar delays and cymbal brightness without losing air
**MCP command**: `master_audio(album_slug, genre="worship")`

**Characteristics**:
- Vocal must sit forward and warm — congregational singability depends on the lead being clear and inviting, not harsh
- Ambient guitar delays (dotted-eighth patterns) live in 2-5 kHz; cut harshness there but preserve the shimmer and space
- Synth pads and keys provide the low-mid foundation (200-500 Hz) — keep them warm and full but not muddy
- Dynamic builds from stripped verse to full chorus are the emotional core; over-compression flattens the worship arc
- Intimate/devotional tracks (-15 LUFS): preserve wide dynamics, natural room reverb, acoustic detail
- Uptempo praise tracks (-13 LUFS): more compression acceptable, emphasize kick and bass punch, brighter top end for energy
- Live worship recordings may include audience/congregation — don't over-compress those ambient elements
- Extended bridges and vamp sections should sustain energy without fatiguing; watch for harsh buildup in layered guitars and keys

### Dub
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the spaciousness and echo trails that define the genre; dub is built on subtraction, so headroom and decay space are essential
**EQ focus**: Deep bass presence (40-80 Hz), warm mid-range (200-600 Hz), high-frequency rolloff for analog warmth, echo/delay preservation
**MCP command**: `master_audio(album_slug, genre="dub")`

**Characteristics**:
- Bass is the foundation -- deep, heavy, and felt in the chest; must be powerful without distortion or muddiness
- Echo, delay, and reverb are compositional tools, not effects -- over-compression collapses the spatial depth that defines dub
- Mixing desk as instrument: drops, fades, and filter sweeps are intentional; preserve dynamic contrasts
- Drums should have room and character; snare with spring reverb, kick with weight and space
- High-frequency content is often rolled off for analog warmth; do not brighten or add presence
- Roots dub (King Tubby, Lee Perry): warmer, lo-fi aesthetic; modern dub (Adrian Sherwood): can be more polished but still spacious

### Cumbia
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the rhythmic interplay between accordion/gaita and percussion; keep the shuffling cumbia rhythm bouncy and alive
**EQ focus**: Accordion/gaita presence (800 Hz-3 kHz), bass warmth (80-200 Hz), guacharaca/percussion clarity (4-8 kHz)
**MCP command**: `master_audio(album_slug, genre="cumbia")`

**Characteristics**:
- The shuffling cumbia rhythm is the genre's identity -- over-compression kills the dance groove
- Accordion or gaita melodies need clear presence in the mid-range without harshness
- Bass (electric or tuba depending on regional style) provides the harmonic foundation; keep it warm and defined
- Percussion (guacharaca, tambora, congas) drives the rhythm; preserve transient clarity
- Colombian cumbia: more acoustic, warmer treatment; digital cumbia/cumbia villera: louder, more compressed acceptable
- Cumbia sonidera and Peruvian chicha: psychedelic elements (guitar effects, synths) need space in the mix

### Samba
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the polyrhythmic interplay between surdo, tamborim, and cavaquinho; avoid flattening the layered percussion dynamics
**EQ focus**: Surdo depth (60-150 Hz), cavaquinho sparkle (2-6 kHz), vocal warmth (200-500 Hz), tamborim attack (3-5 kHz)
**MCP command**: `master_audio(album_slug, genre="samba")`

**Characteristics**:
- Polyrhythmic percussion is the genre's core -- multiple percussion layers must remain distinct and articulate
- Surdo (bass drum) provides the rhythmic foundation; deep and resonant at 60-150 Hz without boom
- Cavaquinho (small guitar) sits in the upper register; preserve its bright, percussive attack
- Vocal delivery ranges from intimate pagode to powerful samba-enredo; adjust compression accordingly
- Samba-enredo (Carnival): can push louder, more energy, massive percussion sections need headroom
- Bossa nova-influenced samba: gentler treatment, wider dynamics, more intimate production

### Highlife
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the interplay between guitar melodies and rhythmic patterns; keep the groove relaxed and flowing
**EQ focus**: Guitar clarity and warmth (800 Hz-3 kHz), bass definition (80-200 Hz), horn presence (1-4 kHz), percussion articulation (4-8 kHz)
**MCP command**: `master_audio(album_slug, genre="highlife")`

**Characteristics**:
- Interlocking guitar patterns are the genre's signature -- preserve note separation and clarity in the mid-range
- Bass guitar carries melodic lines alongside rhythm; keep it warm, present, and clearly defined
- Horn sections (trumpet, saxophone) add melodic color; clarity without harshness above 3 kHz
- Percussion (congas, shakers, bells) provides polyrhythmic texture; preserve transient detail
- Classic highlife (E.T. Mensah style): warmer, vintage-influenced mastering; modern highlife: cleaner, more polished
- Afrobeat-influenced highlife: treat the extended groove sections with care, preserving the hypnotic quality

### J-Pop
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; J-Pop production is dense and polished; match the loudness expectations of the market while preserving vocal clarity
**EQ focus**: Vocal presence and brightness (2-6 kHz), synth clarity (1-4 kHz), bass punch (60-100 Hz), sparkle on top (10-14 kHz)
**MCP command**: `master_audio(album_slug, genre="j-pop")`

**Characteristics**:
- Vocals are the centerpiece -- bright, clear, and forward; J-Pop vocal production emphasizes clarity and sweetness
- Dense arrangements with layered synths, guitars, and strings; each element needs space in a busy mix
- Idol pop: brighter, more compressed, radio-ready; visual kei: treat more like rock/metal mastering
- Vocaloid tracks: synthetic vocals need careful high-frequency management to avoid digital harshness
- Anime opening/ending themes: dramatic builds and high energy; preserve dynamic impact of key moments
- J-Pop masters tend to be louder than Western pop averages; -14 LUFS for streaming is appropriate but the mix density is high

### City Pop
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the smooth, polished production aesthetic; city pop's warmth comes from dynamic headroom and analog-style mastering
**EQ focus**: Bass warmth and groove (60-200 Hz), vocal smoothness (2-4 kHz), synth/keyboard shimmer (4-8 kHz), gentle high-frequency air
**MCP command**: `master_audio(album_slug, genre="city-pop")`

**Characteristics**:
- Warm, analog-sounding master preferred -- city pop's 1980s production aesthetic should carry through; avoid clinical digital brightness
- Bass guitar and synth bass are melodic and groovy (funk/boogie influence); keep them warm, round, and present
- Vocals should be smooth and intimate, sitting naturally in the mix; avoid harsh sibilance
- Electric piano, synth pads, and strings provide lush harmonic beds; preserve their warmth without muddiness
- Guitar work (jazz-influenced chord voicings, funky rhythm parts) needs clarity in the mid-range
- The internet revival aesthetic appreciates the genre's vintage warmth -- do not over-modernize the sound

### Power Metal
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; preserve the speed and energy of double bass drumming while keeping soaring vocals clear and forward
**EQ focus**: Vocal brightness and clarity (2-5 kHz), guitar speed and articulation (1-4 kHz), bass drum definition (60-100 Hz), orchestral/keyboard layers (200-600 Hz)
**MCP command**: `master_audio(album_slug, genre="power-metal")`

**Characteristics**:
- Soaring clean vocals are the genre's centerpiece -- they must cut through dense, fast instrumentation with clarity and power
- Double bass drum patterns need tight definition at 60-100 Hz; avoid muddiness from the rapid-fire kick
- Fast guitar riffs and solos need articulation in the 1-4 kHz range; over-compression blurs speed picking into mush
- Keyboard and orchestral layers support the epic atmosphere; keep them present but behind vocals and guitars
- Power metal masters tend to be bright -- be careful not to over-cut high-mids or the genre loses its soaring quality
- Epic/symphonic power metal (Rhapsody style): wider dynamics for orchestral passages; speed metal-influenced power metal: tighter compression

### Symphonic Metal
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; balance the orchestral dynamics with metal heaviness; preserve the wide dynamic range from quiet orchestral intros to full metal choruses
**EQ focus**: Vocal clarity across operatic and harsh styles (2-5 kHz), orchestral warmth (200-600 Hz), guitar heaviness (80-200 Hz), gentle high-mid cut to manage combined orchestral and guitar brightness
**MCP command**: `master_audio(album_slug, genre="symphonic-metal")`

**Characteristics**:
- Operatic vocals need headroom for dynamic range and vibrato -- over-compression flattens the operatic delivery
- Orchestral and metal elements compete for the same frequency space; careful separation prevents mud without thinning either
- String and brass sections add richness in the 200-600 Hz range; keep them full without masking guitar and bass
- Choral passages and group vocals need space; over-limiting smears layered voices
- Beauty-and-the-beast vocal contrast (clean female + harsh male) requires both styles to remain intelligible
- Nightwish-style cinematic approach benefits from slightly wider dynamics than typical metal

### Folk Metal
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the interplay between folk instruments and metal elements; the contrast between acoustic passages and heavy sections is key
**EQ focus**: Folk instrument clarity (tin whistle, fiddle, hurdy-gurdy at 1-6 kHz), guitar heaviness (80-300 Hz), vocal presence (2-5 kHz), gentle high-mid cut for combined brightness
**MCP command**: `master_audio(album_slug, genre="folk-metal")`

**Characteristics**:
- Folk instruments (fiddle, flute, hurdy-gurdy, bagpipes) sit in the mid-to-upper-mid range; preserve their character without harshness
- Acoustic-to-heavy transitions are compositional; maintain dynamic contrast between folk passages and metal sections
- Harsh and clean vocals often alternate; both need intelligibility without one dominating
- Bass drum and bass guitar provide the metal foundation; keep tight and defined under the folk instrumentation
- Viking/pagan metal (Amon Amarth, Bathory): heavier, darker treatment; Celtic folk metal (Eluveitie): brighter, more acoustic-forward
- Drinking song passages with group vocals: keep them rowdy and full, not over-polished

### Deathcore
**LUFS target**: -14 LUFS
**Dynamics**: Heavy compression; sustain the crushing density of breakdowns and blast beats; preserve kick drum attack through low-tuned chaos
**EQ focus**: Low-end tightness (40-200 Hz for drop-tuned guitars and bass), vocal presence (1-4 kHz), high-mid cut to tame fizzy guitar harshness (3-5 kHz), high shelf cut for cymbal wash control
**MCP command**: `master_audio(album_slug, genre="deathcore")`

**Characteristics**:
- Breakdowns are the genre's signature -- the low-end impact must be felt without becoming muddy; tight sub-bass definition critical
- Drop-tuned guitars (often drop A or lower) produce massive low-mid content; careful separation from bass prevents mud
- Guttural vocals (gutturals, pig squeals, tunnel throat) sit inside the mix; preserve intelligibility without pushing them artificially forward
- Blast beats generate dense cymbal wash; high shelf cut (-1 dB at 8 kHz) prevents listening fatigue
- Modern deathcore (Lorna Shore style): cleaner, more produced; old-school deathcore (Whitechapel): rawer, heavier limiting acceptable
- Orchestral/symphonic deathcore elements need space alongside the heaviness; balance carefully

### Djent
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; preserve the polyrhythmic precision and percussive guitar attack; the tight, articulate palm muting that defines the genre must remain clear
**EQ focus**: Guitar palm-mute clarity (800 Hz-3 kHz), bass tightness (60-200 Hz), drum precision (3-6 kHz for snare and ghost notes), vocal clarity across clean and harsh styles
**MCP command**: `master_audio(album_slug, genre="djent")`

**Characteristics**:
- The palm-muted polyrhythmic guitar tone is the genre's identity -- preserve its percussive, staccato character; over-compression smears the rhythmic precision
- Extended-range guitars (7-8 string) produce dense low-end content; tight low-mid control essential without thinning the tone
- Drum programming or triggered drums need precise transient preservation; ghost notes and complex fills define the groove
- Clean vocal passages and ambient interludes contrast with heavy sections; maintain dynamic range for these transitions
- Meshuggah-style rhythmic djent: heavier, more relentless; Periphery/TesseracT-style progressive djent: wider dynamics, more melodic space
- Bass guitar often mirrors guitar patterns; keep it defined and locked in with the kick drum

### Breakbeat
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the chopped break dynamics and transient impact; the sampled drum breaks must retain their punch and character
**EQ focus**: Break clarity (2-5 kHz), bass weight (40-80 Hz), vocal/sample presence (1-4 kHz), percussion detail (6-10 kHz)
**MCP command**: `master_audio(album_slug, genre="breakbeat")`

**Characteristics**:
- Sampled breakbeats are the foundation -- preserve their original dynamics, transients, and character; over-compression kills the groove
- Big beat (Chemical Brothers, Fatboy Slim style): louder, more compressed, can push to -12 LUFS
- Nu skool breaks: tighter, more modern production; closer to drum and bass energy
- Bass should be powerful and defined; sub-bass separate from the break energy above
- Vocal samples and hooks need clarity without competing with the breaks
- The genre's energy comes from the interplay between chopped breaks and bass; keep both articulate

### Downtempo
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the spacious, atmospheric quality; downtempo lives in the subtlety and texture of its production
**EQ focus**: Bass warmth (40-100 Hz), pad and texture detail (200-600 Hz), vocal/sample presence (2-4 kHz), gentle high-frequency air
**MCP command**: `master_audio(album_slug, genre="downtempo")`

**Characteristics**:
- Spacious production is essential -- over-compression collapses the atmospheric depth that defines the genre
- Bass should be warm, round, and enveloping; not punchy or aggressive
- Organic textures (field recordings, nature sounds, acoustic instruments) need preservation; do not over-process
- Psybient/psychill: more reverb-tolerant, wider dynamics; lounge/chill-out: slightly tighter, more polished
- Vocal elements (when present) sit within the texture, not on top of it
- The genre rewards patient, minimal mastering -- less processing is more

### IDM
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the complex rhythmic patterns and micro-details that define the genre; over-compression flattens the intricate sound design
**EQ focus**: Detail preservation across full spectrum, micro-transient clarity (3-8 kHz), bass precision (40-100 Hz), high-frequency sparkle for digital textures
**MCP command**: `master_audio(album_slug, genre="idm")`

**Characteristics**:
- Complex rhythmic patterns and glitchy textures must remain articulate; over-compression blurs the rhythmic detail
- Sound design is the focus -- every frequency range may contain intentional, carefully crafted elements; avoid broad EQ moves
- Aphex Twin-style melodic IDM: warmer treatment, melodic elements need presence; Autechre-style abstract IDM: more clinical, preserve harsh textures
- Bass can range from sub-heavy to absent; follow the production intent, do not impose expectations
- Quiet passages and dynamic contrast are often compositional; preserve them
- Digital artifacts and glitches are intentional -- do not treat them as problems

### Electro
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the mechanical, precise quality of drum machine patterns; the 808-driven sound needs tight, controlled dynamics
**EQ focus**: 808 kick definition (40-80 Hz), synth clarity (200 Hz-4 kHz), vocoder presence (1-4 kHz), hi-hat crispness (8-12 kHz)
**MCP command**: `master_audio(album_slug, genre="electro")`

**Characteristics**:
- 808 drum machines define the rhythmic backbone -- kick and snare must be tight and punchy
- Vocoder and talk box vocals need clear mid-range presence without harshness
- Synth lines (Kraftwerk-lineage) should be clean and precise; preserve the mechanical aesthetic
- Classic electro (Egyptian Lover, Afrika Bambaataa): warmer, more analog; modern electro: cleaner, more polished
- Bass synths need definition without overwhelming the kick drum; careful low-end separation
- The genre's retro-futurist aesthetic benefits from a polished but not overly clinical master

### Hardstyle
**LUFS target**: -12 LUFS
**Dynamics**: Heavy compression; the distorted kick drum and euphoric leads need aggressive limiting; hardstyle is intentionally loud
**EQ focus**: Kick drum distortion and body (40-200 Hz), lead synth clarity (1-4 kHz), vocal/chant presence (2-5 kHz), high-frequency energy (8-12 kHz)
**MCP command**: `master_audio(album_slug, genre="hardstyle")`

**Characteristics**:
- The distorted kick drum is the genre's signature -- it must be powerful, defined, and felt physically; do not tame the distortion
- Euphoric leads and melodies need to soar above the kick; clear mid-range separation essential
- Reverse bass kicks and screeches are intentional sonic elements; preserve their character
- Euphoric hardstyle: brighter, more melodic leads, vocal chants; rawstyle: darker, heavier, more distorted
- The genre expects loudness -- -12 LUFS is the target; pushing to -10 is acceptable for peak-time tracks
- Build-ups and breakdowns create the live-set energy; preserve the dynamic arc from quiet to full-blast

### Boom Bap
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the punchy, sample-based drum character; the boom (kick) and bap (snare) must hit hard and clean
**EQ focus**: Kick punch (60-100 Hz), snare crack (200 Hz-1 kHz), vocal clarity and presence (2-5 kHz), sample warmth (200-500 Hz)
**MCP command**: `master_audio(album_slug, genre="boom-bap")`

**Characteristics**:
- Sampled drums define the genre -- preserve the dusty, vinyl-sourced character of chopped breaks; do not over-clean
- Kick and snare must be punchy and forward; they drive the head-nod groove
- Lyrical content is the focus -- vocal clarity is paramount; the MC must cut through clearly
- Sample-based production (jazz, soul, funk chops) needs warmth; preserve the vinyl/analog aesthetic
- Golden age revival (Joey Bada$$, Griselda): slightly rawer, lo-fi-tolerant; classic boom bap (Pete Rock, DJ Premier): polished but warm
- Bass lines are melodic and warm, not sub-heavy; keep them defined alongside the kick

### Cloud Rap
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the dreamy, atmospheric quality; the ethereal production needs space and air
**EQ focus**: Vocal presence with auto-tune warmth (2-5 kHz), pad/synth atmosphere (200-600 Hz), sub-bass weight (30-60 Hz), high-frequency shimmer
**MCP command**: `master_audio(album_slug, genre="cloud-rap")`

**Characteristics**:
- Atmospheric, reverb-heavy production is the genre's identity -- over-compression collapses the dreamy space
- Auto-tuned vocals need warmth and clarity; preserve the melodic, pitch-corrected character without harshness
- Sub-bass is often heavy but slow-moving; keep it warm and enveloping, not aggressive
- Synth pads and ambient textures create the cloudy atmosphere; preserve their depth and layering
- Yung Lean/Bladee-style: more lo-fi, dreamier; A$AP Rocky/Travis Scott: more polished, heavier bass
- The genre rewards a spacious, airy master -- avoid anything that makes it feel tight or compressed

### Conscious Hip-Hop
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve vocal dynamics and emotional delivery; the message is the priority -- every word must be heard
**EQ focus**: Vocal clarity and warmth (2-5 kHz), beat warmth (200-500 Hz), bass definition (60-100 Hz), sample texture preservation
**MCP command**: `master_audio(album_slug, genre="conscious-hip-hop")`

**Characteristics**:
- Lyrical content carries the message -- vocal clarity and intelligibility are non-negotiable
- Beats tend to be more musical and organic than mainstream hip-hop; preserve the soulful, jazz, or live-instrument quality
- Dynamic vocal delivery (quiet introspection to passionate emphasis) needs headroom; do not flatten the emotional range
- Kendrick Lamar/J. Cole style: modern, polished production; Common/Mos Def style: warmer, more sample-based
- Live instrumentation elements (piano, bass, strings) need natural presence; do not over-process
- Spoken word passages within tracks need the same clarity standard as rapped sections

### Flamenco
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the wide dynamic range from intimate guitar passages to explosive cante jondo vocal outbursts; flamenco's emotional power comes from dynamic contrast
**EQ focus**: Guitar body and attack (200 Hz-3 kHz), vocal presence and rawness (1-5 kHz), palmas (hand claps) and cajon clarity (3-6 kHz), zapateado (footwork) impact (80-200 Hz)
**MCP command**: `master_audio(album_slug, genre="flamenco")`

**Characteristics**:
- Nylon-string guitar is the harmonic and melodic center; preserve its warmth, attack, and rasgueado (strumming) energy
- Cante jondo vocals are raw, emotional, and dynamic; over-compression destroys the passionate delivery
- Palmas (hand claps) and cajon drive the compas rhythm; preserve their transient snap
- Zapateado (footwork) adds percussive low-end impact; keep it present but not boomy
- Traditional flamenco: wider dynamics, more acoustic; nuevo flamenco (Paco de Lucia, Rosalia): tighter, can push to -14 LUFS
- The room acoustic matters -- flamenco's intimate tablao setting should carry through in the master

### Fado
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the intimate, emotional delivery and natural dynamics; fado's saudade (longing) depends on dynamic vulnerability
**EQ focus**: Vocal warmth and presence (1-4 kHz), guitarra portuguesa shimmer (2-6 kHz), viola (acoustic guitar) body (200-500 Hz), gentle high-frequency air
**MCP command**: `master_audio(album_slug, genre="fado")`

**Characteristics**:
- The voice carries the saudade -- it must be warm, present, and emotionally transparent; avoid harsh sibilance
- Guitarra portuguesa (Portuguese guitar) has a distinctive bright, mandolin-like tone; preserve its shimmer without harshness
- Viola (classical guitar) provides harmonic foundation; keep it warm and supportive
- Traditional fado (Amalia Rodrigues): wider dynamics, vintage warmth; novo fado (Mariza, Ana Moura): slightly more polished, can sit at -15 LUFS
- The intimate cafe/fado house acoustic should be preserved; do not over-dry or over-brighten
- Quiet passages are as important as powerful moments; protect the dynamic range

### Afro-Cuban
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the clave-based rhythmic interplay between percussion layers; the polyrhythmic complexity must remain articulate
**EQ focus**: Conga/bongo warmth (200-500 Hz), horn brightness (1-4 kHz), bass (tumbao) definition (80-200 Hz), timbales and cowbell clarity (3-6 kHz), clave snap
**MCP command**: `master_audio(album_slug, genre="afro-cuban")`

**Characteristics**:
- The clave pattern is the rhythmic foundation -- all other instruments relate to it; preserve the polyrhythmic clarity
- Congas and bongos provide rhythmic and melodic content; keep their warmth and attack defined
- Horn sections (trumpet, trombone, saxophone) carry melodies; clarity without harshness above 3 kHz
- Bass (tumbao pattern) is both rhythmic and melodic; keep it warm and locked to the clave
- Son: warmer, more acoustic; mambo: brighter, more horn-forward; rumba: more percussion-focused
- Timba (modern Cuban): louder, more compressed; traditional son: wider dynamics, more acoustic

### Qawwali
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the ecstatic dynamic builds from quiet devotional passages to full-ensemble crescendos; the gradual build to spiritual ecstasy is the genre's emotional arc
**EQ focus**: Vocal group clarity (2-5 kHz), harmonium warmth (200-600 Hz), tabla definition (3-5 kHz), hand-clap rhythm (4-6 kHz)
**MCP command**: `master_audio(album_slug, genre="qawwali")`

**Characteristics**:
- Lead vocal must soar above the ensemble; preserve its dynamic range from whispered devotion to ecstatic crescendo
- Group vocals (chorus response) create call-and-response energy; keep them full and present behind the lead
- Harmonium drone provides the harmonic bed; warm, sustained, not muddy
- Tabla and dholak drive the accelerating rhythm; preserve transient clarity as tempos increase
- Hand claps (taali) are essential to the rhythmic texture; crisp and defined
- Nusrat Fateh Ali Khan-style: epic dynamics, minimal compression; modern/fusion qawwali: slightly tighter treatment acceptable

### Mandopop
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; polished, radio-ready production similar to mainstream pop; vocal clarity and warmth are the priority
**EQ focus**: Vocal presence and sweetness (2-5 kHz), piano/keyboard warmth (200-500 Hz), string arrangement body (300-600 Hz), clean top end
**MCP command**: `master_audio(album_slug, genre="mandopop")`

**Characteristics**:
- Vocals are the centerpiece -- clear, warm, and emotionally present; Mandopop emphasizes vocal beauty and lyrical delivery
- Ballads dominate the genre; preserve the emotional dynamic arc from quiet verses to full choruses
- Piano and string arrangements are common accompaniment; keep them lush but not competing with vocals
- Jay Chou-style R&B-influenced: warmer bass, groove-forward; ballad-focused (Teresa Teng lineage): wider dynamics, more delicate
- Production tends to be clean and polished; avoid overly aggressive processing
- High-end should be bright but not harsh; the genre favors a sweet, refined sonic character

### Amapiano
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the laid-back groove and rhythmic interplay between log drums, bass, and percussion; the bounce and swing are essential
**EQ focus**: Log drum presence (200-600 Hz), bass warmth (60-150 Hz), jazz chord voicings (300-800 Hz), shaker/percussion detail (6-10 kHz)
**MCP command**: `master_audio(album_slug, genre="amapiano")`

**Characteristics**:
- Log drums are the genre's signature sound -- their woody, melodic percussion must sit prominently in the mix
- Bass is warm, deep, and groovy; not aggressive or sub-heavy; it drives the slow-bounce feel
- Jazz-influenced chord voicings (piano, keys) provide harmonic sophistication; preserve their warmth
- Vocal elements range from spoken word to melodic singing; keep them clear and present
- The 108-120 BPM tempo creates a relaxed but danceable energy; over-compression kills the groove
- South African production aesthetics favor warmth and space; do not over-brighten or over-process

### Afroswing
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; polished, pop-forward production with Afrobeats-influenced groove; radio-ready loudness with bounce
**EQ focus**: Vocal clarity (2-5 kHz), bass warmth and punch (60-150 Hz), percussion detail (4-8 kHz), synth/pad warmth (200-500 Hz)
**MCP command**: `master_audio(album_slug, genre="afroswing")`

**Characteristics**:
- UK-born fusion: distinct from Nigerian Afrobeats; more polished, pop-leaning production
- Vocals should be clear, warm, and forward; melodic delivery is key
- Bass should be warm and bouncy; not as sub-heavy as UK grime or drill
- Percussion blends Afrobeats rhythms with UK production aesthetics; preserve the swing
- J Hus/Not3s-style: more melodic, pop-forward; darker UK Afro: more rhythm-focused
- The genre sits between Afrobeats and UK pop; master accordingly -- polished but with groove

### New Age
**LUFS target**: -16 LUFS
**Dynamics**: Minimal compression; preserve the spacious, meditative quality; new age music depends on wide dynamics and natural breathing room
**EQ focus**: Synth pad warmth (200-600 Hz), nature sound clarity (2-8 kHz), Celtic/world instrument presence (800 Hz-3 kHz), gentle high-frequency air and shimmer
**MCP command**: `master_audio(album_slug, genre="new-age")`

**Characteristics**:
- Spaciousness and atmosphere are paramount -- over-compression destroys the meditative quality
- Synth pads and drones should be warm, enveloping, and sustained; no harshness
- Nature sounds (water, birds, wind) are compositional elements; preserve their natural character
- Celtic elements (harp, flute, tin whistle) need clear mid-range presence; warm and inviting
- Enya-style layered vocals: preserve the choir-like depth; pure instrumental: focus on texture and space
- The genre is designed for relaxation and meditation; the master should feel effortless and natural

### Reggaeton
**LUFS target**: -12 LUFS
**Dynamics**: Heavy compression; reggaeton is club and radio music designed for impact and loudness; punchy, aggressive mastering is appropriate
**EQ focus**: Dembow kick punch (60-100 Hz), snare/rim shot crack (1-3 kHz), vocal presence (2-5 kHz), bass weight (40-80 Hz), hi-hat crispness (8-12 kHz)
**MCP command**: `master_audio(album_slug, genre="reggaeton")`

**Characteristics**:
- The dembow rhythm is the genre's backbone -- kick and snare must be punchy and relentless
- Bass should be heavy, defined, and felt physically; sub-bass is essential to the club experience
- Vocals need to cut through the heavy production; clear and present, often processed with effects
- Daddy Yankee/classic reggaeton: more raw, heavier; Bad Bunny/modern: more experimental, varied production
- Perreo tracks can push to -10 LUFS for maximum dancefloor impact
- Latin trap crossover tracks: slightly less compressed, more atmospheric; pure reggaeton: full loudness

### Spoken Word
**LUFS target**: -14 LUFS
**Dynamics**: Light compression; the voice is everything -- preserve the full dynamic range of the performance from whisper to shout
**EQ focus**: Vocal clarity and warmth (1-5 kHz), backing music/ambient texture warmth (200-600 Hz), sibilance control (6-8 kHz), low-end rumble removal
**MCP command**: `master_audio(album_slug, genre="spoken-word")`

**Characteristics**:
- The spoken voice is the absolute center; every word must be intelligible and emotionally present
- Dynamic delivery (whisper to shout) is performative; do not flatten it with over-compression
- Backing music or ambient textures should support, never compete with the voice
- Beat poetry: spare, jazz-influenced accompaniment; preserve the intimate, cafe atmosphere
- Slam poetry: more energetic, percussive delivery; slightly tighter compression acceptable
- Dub poetry (Linton Kwesi Johnson, Mutabaruka): reggae/dub backing; treat the music bed like dub mastering while keeping voice forward

### Ska
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve horn transients and the natural punch of the skank guitar; avoid squashing the rhythmic interplay between offbeat guitar and walking bass
**EQ focus**: Horn clarity (1-4 kHz), bass warmth and definition (80-200 Hz), gentle high-mid cut to tame brass brightness without killing sparkle, skank guitar presence (800 Hz-2 kHz)
**MCP command**: `master_audio(album_slug, genre="ska")`

**Characteristics**:
- Horns are the genre's melodic centerpiece -- they must cut through clearly without harshness; watch for Suno-generated brass brightness above 4 kHz
- Walking bass lines carry melody alongside the vocals; keep bass warm and defined, not boomy
- Offbeat skank guitar should be crisp and percussive, not muddy; clarity in the 800 Hz-2 kHz range is essential
- First wave / traditional ska: slightly warmer, more reverb-tolerant, echo effects are authentic to the Studio One sound
- 2 Tone ska: punchier, drier, more new wave-influenced production; tighter low end
- For ska-punk mastering, use the ska-punk preset instead (more aggressive high-mid cuts)
- Drum transients (especially hi-hat and rim clicks) should stay sharp to drive the rhythm

### Pop Punk
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; punchy and radio-ready but preserve the dynamic contrast between verse restraint and chorus energy; the sing-along hooks need headroom
**EQ focus**: Vocal clarity and brightness (2-5 kHz), palm-muted guitar punch (800 Hz-2 kHz), bass definition (80-200 Hz), snare crack (1-3 kHz)
**MCP command**: `master_audio(album_slug, genre="pop-punk")`

**Characteristics**:
- Vocals are melodic and upfront -- they carry the hooks and must be clear and present at all times
- Palm-muted power chord chugs need punch in the low-mids without muddiness
- Snare should be bright and snappy; it drives the fast tempos and singalong energy
- Green Day-style: tighter, punchier, radio-ready; Blink-182/early 2000s: slightly scooped, more bass-forward
- Pop-punk revival (Modern Baseball, PUP): slightly rawer, more dynamic; classic: polished and compressed
- Double-tracked vocals and gang vocals are common; keep them full but not smeared

### Riot Grrrl
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the raw, unpolished energy that defines the genre; riot grrrl's lo-fi aesthetic is intentional, not a deficiency -- over-compression removes the garage-recording character
**EQ focus**: Vocal presence and clarity (2-5 kHz), guitar distortion body (800 Hz-2 kHz), bass weight (80-200 Hz), gentle high-mid cut to tame lo-fi harshness without sterilizing the sound (3-5 kHz)
**MCP command**: `master_audio(album_slug, genre="riot-grrrl")`

**Characteristics**:
- Vocals are confrontational and forward -- shouted, chanted, or spoken-word delivery must remain urgent and present; do not bury them behind instrumentation
- Lo-fi recording quality is a feature, not a bug -- room noise, bleed, and tape hiss are authentic; do not over-clean or gate aggressively
- Guitar distortion is raw and fuzzy, not tight or polished; preserve the garage-punk character in the 800 Hz-2 kHz range
- Call-and-response and gang vocal sections need clarity without losing their rough, communal energy
- Bikini Kill-style raw punk: minimal processing, preserve the cassette-tape aesthetic; Sleater-Kinney-style: slightly more polished, tighter low end
- Bass guitar often follows guitar closely, creating a thick low-mid wall; keep it warm and present but defined enough that the rhythm stays clear
- High-mid harshness at 3-5 kHz from lo-fi recordings: gentle cuts only (-2 dB), aggressive cutting removes the abrasive edge that is part of the genre's identity

### Powerviolence
**LUFS target**: -14 LUFS
**Dynamics**: Heavy compression acceptable; the genre is already maximally dense and aggressive; preserve the contrast between blast-beat sections and sludge breakdowns -- the tempo shifts are the genre's defining structural element and must feel violent, not smoothed
**EQ focus**: Bass distortion weight (40-200 Hz), guitar fizz and dissonance (800 Hz-3 kHz), vocal presence through the chaos (1-4 kHz), high-mid cut for harshness control (3-5 kHz), gentle high shelf cut to tame cymbal wash during blast sections
**MCP command**: `master_audio(album_slug, genre="powerviolence")`

**Characteristics**:
- Blast-beat to sludge tempo shifts are the genre's signature -- these transitions must hit hard; compression should not soften the whiplash effect
- Bass guitar and bass distortion are often as loud as or louder than guitar; keep the low end thick and present, not clean
- Lo-fi production is intentional and genre-appropriate -- do not try to polish or brighten a deliberately raw mix; the ugliness is the point
- Vocals are screamed and panicked; preserve the urgency and hysteria without introducing painful high-frequency harshness
- Classic PV (Infest, Man Is the Bastard): rawer, more lo-fi tolerant; modern PV (Nails, Weekend Nachos): tighter, heavier, more metallic
- Songs are extremely short (many under 30 seconds); every fraction of a second matters for clarity and impact
- High-frequency content from cymbals during blast beats can become overwhelming; gentle high shelf cut at 8 kHz tames the wash without dulling the attack

### Screamo
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; preserve the explosive dynamics between quiet passages and screamed eruptions; the emotional contrast is the genre's core
**EQ focus**: Screamed vocal presence (1-4 kHz), guitar dissonance and texture (800 Hz-3 kHz), bass weight (60-200 Hz), high-mid cut to tame harshness without losing aggression (3-5 kHz)
**MCP command**: `master_audio(album_slug, genre="screamo")`

**Characteristics**:
- Screamed vocals are raw and emotionally intense; preserve their urgency without introducing painful harshness
- Quiet-to-explosive dynamic shifts are compositional; over-compression destroys the emotional arc
- Guitar work ranges from angular post-hardcore riffs to tremolo-picked walls of sound; preserve both clearly
- Saetia/Orchid-style chaotic screamo: rawer, more dynamic, lo-fi tolerance; post-screamo (Touche Amore): tighter, more produced
- Bass guitar often provides melodic counterpoint; keep it defined and present
- Short song formats (1-3 minutes) mean every second is dense; clarity is critical throughout

### Oi!
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the gang vocal energy and singalong dynamics; the pub-rock aesthetic needs punch without excessive polish; avoid over-compressing crowd-style vocal layers into a flat wall
**EQ focus**: Vocal presence and clarity (2-5 kHz), guitar power chord body (200 Hz-2 kHz), bass punch (80-200 Hz), gentle high-mid cut to tame guitar harshness without killing the rawness (3-5 kHz)
**MCP command**: `master_audio(album_slug, genre="oi")`

**Characteristics**:
- Vocals are the centerpiece -- gruff, shouted lead vocals and gang vocal choruses must be clear, forward, and singable; preserve the raw character without letting it become harsh
- Gang vocals and terrace-style chanting generate dense mid-range content; keep the layers distinct and powerful, not smeared
- Guitar tone is moderately distorted -- less gain than hardcore punk, more than pub rock; preserve the power chord attack and body
- Bass guitar follows root notes with occasional melodic runs; keep it punchy and defined at 80-200 Hz without muddying the guitars
- Drum production should be punchy and live-sounding; snare backbeat drives the songs; avoid overly processed or triggered drum sounds
- Classic Oi! (Sham 69, Cockney Rejects): rawer, more lo-fi tolerant; modern Oi! (Booze & Glory, Lion's Law): slightly tighter, cleaner, but still pub-ready
- Anthemic, slower tracks (Cock Sparrer-style, 120-130 BPM): slightly wider dynamics to let the singalong choruses breathe and build
- The genre's live, communal energy should carry through to the master -- clinical perfection is antithetical to Oi!

### D-Beat
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; sustain the relentless wall-of-sound intensity without crushing the galloping drum pattern that defines the genre; the D-beat must remain driving and articulate
**EQ focus**: Guitar distortion body (200 Hz-2 kHz), bass rumble (60-200 Hz), vocal presence through the distortion wall (1-4 kHz), high-mid cut to tame guitar fizz and cymbal harshness (3-5 kHz), gentle high shelf cut for blown-out cymbal wash
**MCP command**: `master_audio(album_slug, genre="d-beat")`

**Characteristics**:
- The signature D-beat drum pattern (galloping snare-kick alternation) is the genre's identity -- it must remain driving and articulate; over-compression blurs it into undifferentiated noise
- Guitar distortion is thick and all-consuming; preserve the wall-of-sound character without letting it become a featureless wash
- Bass guitar provides rumbling low-end foundation; keep it felt rather than heard clearly -- it adds weight, not melody
- Vocals are shouted and raw, often buried in the mix; preserve their presence at 1-4 kHz without pushing them artificially forward -- D-beat vocals sit inside the distortion, not on top of it
- High-frequency content from cymbals and guitar fizz can cause listening fatigue; gentle high shelf cut (-1 dB at 8 kHz) helps without dulling the aggression
- Classic D-beat (Discharge, Varukers): rawer, lo-fi-tolerant mastering; modern D-beat crust (Wolfbrigade, Disfear): slightly tighter, more defined, but still aggressive
- Noise D-beat (Disclose, Framtid): the blown-out, feedback-heavy production is intentional -- do not try to clean it up; treat it like noise rock mastering with even less restraint

### Crust Punk
**LUFS target**: -14 LUFS (neocrust with post-rock dynamics: -15 LUFS)
**Dynamics**: Moderate-to-heavy compression; preserve the contrast between slow crushing sections and fast d-beat blasts; crust punk relies on oppressive weight and frantic energy existing in the same track -- over-compression flattens both
**EQ focus**: Low-end body and distortion weight (40-200 Hz), vocal presence through the distortion wall (1-4 kHz), guitar distortion character (800 Hz-3 kHz), high-mid cut to control harshness without removing the abrasive edge (3-5 kHz), gentle high shelf cut for murky aesthetic (-1 dB at 8 kHz)
**MCP command**: `master_audio(album_slug, genre="crust-punk")`

**Characteristics**:
- Raw, murky production is intentional -- do not try to clean up the mix or add clarity; the lo-fi aesthetic is the genre's identity
- Bass distortion and guitar distortion occupy overlapping frequency ranges by design; separation is less important than combined crushing weight
- Vocals are harsh (screamed, shouted, growled) and often buried in the mix; preserve their presence without pushing them artificially forward
- D-beat drumming needs its rhythmic pattern preserved; the syncopated snare-kick pattern must remain recognizable through the distortion
- Stenchcore (Amebix, Antisect style): mid-tempo, doom-influenced, heavier compression acceptable for sustained crushing weight
- Neocrust (Tragedy, From Ashes Rise): wider dynamics to accommodate post-rock builds and melodic guitar harmonies; target -15 LUFS
- Blackened crust: tremolo riffing and blast beats generate dense high-frequency content; gentle high shelf cut prevents fatigue
- Sludge crust (Dystopia, His Hero Is Gone): treat like sludge metal mastering -- oppressive, heavy, feedback-tolerant
- Dual vocal arrangements (screamer + growler) need both voices present; do not let one dominate

### Groove Metal
**LUFS target**: -14 LUFS
**Dynamics**: Heavy compression; sustain the crushing rhythmic weight; the mid-tempo groove must feel relentless and physically heavy
**EQ focus**: Low-end tightness and weight (60-200 Hz), guitar groove articulation (800 Hz-3 kHz), vocal presence (1-4 kHz), high-mid cut for guitar harshness (3-5 kHz)
**MCP command**: `master_audio(album_slug, genre="groove-metal")`

**Characteristics**:
- The rhythmic groove is everything -- mid-tempo riffs must hit hard with each note clearly articulated; over-compression blurs the groove into mush
- Kick drum and bass guitar lock together; tight low-end definition is critical
- Vocals range from shouted to clean; both need to cut through the heavy instrumentation
- Pantera-style: tighter, more aggressive, guitar-forward; Lamb of God-style: slightly more polished, modern production
- Guitar tone is scooped but with aggressive high-mid attack; do not over-cut the bite
- Breakdowns and half-time sections need maximum impact; preserve dynamic contrast for these moments

### Sludge Metal
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; preserve the abrasive, crushing weight; sludge metal's oppressive atmosphere depends on sustained heaviness with dynamic breathing room
**EQ focus**: Low-end body and distortion (40-200 Hz), vocal rawness (1-4 kHz), guitar sludge and feedback (800 Hz-3 kHz), high-mid harshness controlled but not removed (3-5 kHz)
**MCP command**: `master_audio(album_slug, genre="sludge-metal")`

**Characteristics**:
- Slow, heavy, and abrasive is the point -- do not try to clean up the raw, ugly tone; it is intentional
- Bass and guitar distortion create a wall of low-mid content; separation is less important than combined weight
- Vocals are often screamed or shouted through heavy distortion; preserve their abrasive character
- Eyehategod/Crowbar-style: rawer, more punk-influenced, lo-fi tolerant; Neurosis/Isis-style: more atmospheric, wider dynamics
- Feedback and sustained distortion are compositional elements; do not gate or compress them out
- The genre benefits from a thick, oppressive master; clinical brightness is the enemy

### Progressive Metal
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the wide dynamic range from quiet clean passages to heavy sections; the complexity and nuance of arrangements must remain clear
**EQ focus**: Guitar clarity across clean and distorted tones (800 Hz-4 kHz), keyboard/synth layers (200-600 Hz), vocal intelligibility (2-5 kHz), bass articulation (80-200 Hz), drum precision (3-6 kHz)
**MCP command**: `master_audio(album_slug, genre="progressive-metal")`

**Characteristics**:
- Dynamic range is critical -- quiet interludes, acoustic passages, and heavy sections must each have their own space
- Complex time signatures and polyrhythms require precise transient preservation; over-compression blurs technical passages
- Dream Theater-style: polished, wide dynamics, keyboard prominence; Tool-style: darker, heavier, more bass-focused
- Extended compositions (10+ minutes) need consistent energy management without fatigue
- Clean and distorted guitar tones alternate frequently; both need clarity in the mix
- Bass guitar often carries complex melodic lines; keep it defined and articulate throughout

### Speed Metal
**LUFS target**: -14 LUFS
**Dynamics**: Heavy compression; sustain the relentless energy and velocity; the genre's defining speed must translate as controlled aggression, not chaotic mush
**EQ focus**: Guitar speed and articulation (1-4 kHz), vocal power and clarity (2-5 kHz), bass drum attack (60-100 Hz), bass guitar definition (80-200 Hz), high-mid cut for pick noise (3-5 kHz)
**MCP command**: `master_audio(album_slug, genre="speed-metal")`

**Characteristics**:
- Speed is the defining characteristic -- fast alternate picking and double bass must remain articulate at high tempos
- Vocals are powerful and melodic (cleaner than thrash); they must soar above the fast instrumentation
- Motorhead-style: rawer, punk-influenced, louder; Exciter/Agent Steel-style: more traditional metal, tighter production
- Guitar solos are a focal point; preserve their presence and clarity in the fast rhythmic backdrop
- Bass drum patterns are rapid and relentless; tight definition at 60-100 Hz prevents low-end blur
- The genre bridges NWOBHM melody with thrash aggression; balance both qualities

### Electroswing
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; balance the vintage swing elements with modern electronic production; preserve the dynamic swing feel while maintaining dancefloor energy
**EQ focus**: Brass and horn clarity (1-4 kHz), electronic bass punch (40-100 Hz), vocal warmth (2-5 kHz), hi-hat and percussion detail (8-12 kHz), vintage sample warmth (200-500 Hz)
**MCP command**: `master_audio(album_slug, genre="electroswing")`

**Characteristics**:
- Vintage swing samples (brass, vocals, piano) meet modern electronic production; both worlds need presence
- Brass and horn samples should sound warm and vintage, not harsh or over-bright
- Electronic kick and bass must punch through without overwhelming the acoustic swing elements
- Parov Stelar-style: more bass-heavy, club-oriented; Caravan Palace-style: more energetic, vocal-forward
- The swing rhythm must remain bouncy and danceable; over-compression kills the swing feel
- Vintage warmth in the mid-range is essential; do not over-modernize the retro aesthetic

### Future Bass
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the lush, layered supersaw chords and melodic dynamics; the genre's emotional impact comes from dynamic builds and drops
**EQ focus**: Supersaw warmth and width (200 Hz-2 kHz), vocal chop clarity (2-6 kHz), sub-bass weight (30-60 Hz), sparkle and air (10-14 kHz)
**MCP command**: `master_audio(album_slug, genre="future-bass")`

**Characteristics**:
- Supersaw chord stacks are the genre's signature -- they must be wide, warm, and lush without muddiness
- Vocal chops and pitched vocal samples need clarity and presence in the upper-mid range
- Sub-bass is heavy but melodic; keep it defined and separate from the mid-range
- Flume-style: grittier, more textured, experimental; ODESZA-style: warmer, more organic, cinematic
- Build-ups and drops are the emotional core; preserve the dynamic contrast between quiet breaks and full drops
- Side-chain compression effects are compositional; preserve the pumping feel if present

### Future House
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the sidechain pumping effect and dynamic contrast between breakdowns and drops; the genre's groove depends on the rhythmic push-pull between kick and bass
**EQ focus**: FM bass clarity and body (80-300 Hz), vocal chop presence (2-6 kHz), kick definition (40-80 Hz), hi-hat crispness (8-12 kHz), synth pluck brightness (1-4 kHz)
**MCP command**: `master_audio(album_slug, genre="future-house")`

**Characteristics**:
- The FM/frequency-modulated bassline is the genre's signature sound -- metallic, elastic, and rubbery; preserve its tonal character and movement without muddiness
- Sidechain compression pumping is a compositional element, not a mixing artifact; the rhythmic ducking of the bass against the kick must remain pronounced and groovy
- Pitched vocal chops function as melodic hooks; they need clarity and presence in the 2-6 kHz range without harshness
- Oliver Heldens-style: brighter, poppier, more melodic; Tchami-style: darker, funkier, heavier bass
- Builds and drops define the energy arc; preserve the contrast between stripped breakdowns and full drops
- Clean, polished production is expected; the genre rewards a precise, modern-sounding master over warmth or analog character

### Minimal Techno
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the hypnotic, repetitive groove and subtle textural details; minimal techno's power comes from micro-variations, not loudness
**EQ focus**: Kick definition (40-80 Hz), hi-hat crispness (8-12 kHz), subtle textural detail (1-6 kHz), sub-bass separation from kick (30-50 Hz)
**MCP command**: `master_audio(album_slug, genre="minimal-techno")`

**Characteristics**:
- Less is more -- every element must be precisely placed and clearly audible; do not over-process
- Kick drum is the rhythmic and tonal center; it must be tight, deep, and defined
- Hi-hats and micro-percussion drive the groove with subtle variations; preserve transient detail
- Richie Hawtin-style: stark, precise, digital; Ricardo Villalobos-style: warmer, more organic, longer-form
- Stereo field placement is critical; many elements are positioned carefully in the panorama
- The genre rewards restraint in mastering; aggressive processing destroys the minimalist aesthetic

### Gabber
**LUFS target**: -12 LUFS
**Dynamics**: Heavy compression; gabber is intentionally loud, aggressive, and relentless; the distorted kick drum must physically pound
**EQ focus**: Kick drum distortion and body (40-200 Hz), synth stab clarity (1-4 kHz), vocal/MC presence (2-5 kHz), hi-hat energy (8-12 kHz)
**MCP command**: `master_audio(album_slug, genre="gabber")`

**Characteristics**:
- The distorted kick drum IS the genre -- it must be massive, distorted, and felt in the chest; do not tame the distortion
- 160+ BPM tempos create relentless energy; the master must sustain this without fatigue (difficult balance)
- Synth stabs and hoover sounds need to cut through the kick wall
- Angerfist/Rotterdam style: maximum aggression, push to -10 LUFS; early gabber: slightly rawer, more industrial
- Vocal samples and MC shouts add intensity; keep them present above the kick
- The genre expects loudness and aggression; subtlety is not the goal

### Neo-Soul
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the warm, organic dynamics and live-instrument feel; neo-soul's intimacy depends on dynamic breathing room
**EQ focus**: Vocal warmth and presence (2-5 kHz), bass groove (60-150 Hz), keyboard/Rhodes warmth (200-600 Hz), drum kit naturalness (3-6 kHz), gentle top-end air
**MCP command**: `master_audio(album_slug, genre="neo-soul")`

**Characteristics**:
- Vocals are warm, intimate, and emotionally nuanced; preserve dynamic expression and subtle inflections
- Rhodes/Wurlitzer electric piano is the harmonic bed; keep it warm and present without muddiness
- Bass is melodic and groovy (jazz/hip-hop influenced); warm and round, not aggressive
- Erykah Badu-style: more experimental, lo-fi-tolerant, spacious; D'Angelo-style: denser, groovier, more layered
- Live-instrument feel is essential; do not over-process or make it sound clinical
- The genre rewards a warm, analog-sounding master; digital harshness is the enemy

### Motown
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; capture the classic Motown punch and warmth; the Funk Brothers' tight rhythm section must remain punchy and defined
**EQ focus**: Vocal clarity and warmth (2-5 kHz), bass punch (60-150 Hz), tambourine and percussion brightness (6-10 kHz), horn warmth (800 Hz-3 kHz), string sweetness (200-600 Hz)
**MCP command**: `master_audio(album_slug, genre="motown")`

**Characteristics**:
- Vocals are always the centerpiece -- clear, warm, powerful, and upfront; the Motown vocal sound is polished and professional
- The Funk Brothers rhythm section (bass, drums, piano) drives the groove; tight, punchy, locked-in
- James Jamerson-style bass is melodic and prominent; keep it warm, round, and clearly defined
- Tambourine is the secret weapon of Motown percussion; its brightness drives the energy without harshness
- Horn and string arrangements add sophistication; keep them lush but supportive, not competing with vocals
- Warm, slightly compressed master preferred; vintage warmth over modern clinical brightness

### Outlaw Country
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the raw, unpolished feel that defines the anti-Nashville aesthetic; dynamics should feel natural, not radio-processed
**EQ focus**: Vocal presence and character (2-5 kHz), acoustic/electric guitar warmth (200 Hz-2 kHz), bass definition (80-200 Hz), pedal steel shimmer (3-6 kHz)
**MCP command**: `master_audio(album_slug, genre="outlaw-country")`

**Characteristics**:
- The raw, unpolished aesthetic is intentional -- do not over-process or make it sound Nashville-slick
- Vocals should be present and characterful; imperfections are part of the authenticity
- Willie Nelson-style: spare, acoustic-forward, wider dynamics; Waylon Jennings-style: heavier, more electric, tighter compression
- Guitar tones range from clean acoustic to overdriven electric; preserve their natural character
- The rhythm section is stripped-down and groove-focused; keep it tight without making it mechanical
- A warm, slightly rough master captures the outlaw spirit better than clinical perfection

### Zydeco
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the infectious dance energy and accordion-driven groove; the bouncy, propulsive rhythm must stay alive
**EQ focus**: Accordion presence and warmth (800 Hz-3 kHz), frottoir (rubboard) brightness (4-8 kHz), bass punch (80-200 Hz), drum groove (1-4 kHz)
**MCP command**: `master_audio(album_slug, genre="zydeco")`

**Characteristics**:
- Accordion is the genre's voice -- it must be clear, warm, and prominent in the mix
- Frottoir (rubboard) provides the rhythmic drive; its metallic scrape should be bright and percussive without harshness
- Bass and drums provide the two-step dance rhythm; punchy and defined, driving the dance energy
- Clifton Chenier-style traditional: warmer, more organic; modern zydeco: can be tighter, more polished
- The genre is dance music at heart; the groove and energy must translate through the master
- Warm, live-sounding master preferred; zydeco thrives on feel and authenticity

### Tropicalia
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the eclectic, psychedelic production aesthetic; the genre's experimental spirit depends on dynamic variety and textural surprises
**EQ focus**: Guitar and berimbau clarity (800 Hz-3 kHz), bass warmth (60-200 Hz), vocal presence (2-5 kHz), percussion detail (4-8 kHz), psychedelic effects preservation
**MCP command**: `master_audio(album_slug, genre="tropicalia")`

**Characteristics**:
- Eclectic instrumentation (electric guitar, berimbau, traditional Brazilian percussion, electric bass) all need space in the mix
- Psychedelic production elements (distortion, panning, tape effects) are compositional; preserve their character
- Caetano Veloso-style: more acoustic, vocal-forward; Os Mutantes-style: heavier, more psychedelic, distorted
- Brazilian rhythmic foundations (bossa nova, samba, baiao) underpin the experimentation; preserve rhythmic clarity
- Vocals range from intimate singing to experimental spoken word; both need intelligibility
- The genre is intentionally boundary-crossing; the master should not impose a single sonic framework

### Zouk
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the sensual, rhythmic groove and warm Caribbean feel; the dance rhythm must remain bouncy and inviting
**EQ focus**: Synth pad warmth (200-500 Hz), bass groove (60-150 Hz), percussion crispness (4-8 kHz), vocal sweetness (2-5 kHz), guitar clarity (800 Hz-2 kHz)
**MCP command**: `master_audio(album_slug, genre="zouk")`

**Characteristics**:
- The rhythmic groove is sensual and danceable; over-compression kills the gentle bounce
- Synth pads and keyboards provide warm harmonic beds; keep them lush without muddiness
- Bass is warm, round, and groove-focused; not aggressive or sub-heavy
- Kassav'-style: full band energy, horn and guitar elements; zouk love: slower, more intimate, vocal-focused
- Percussion (ka, ti-bwa, shakers) drives the rhythm; preserve transient detail and clarity
- The genre rewards a warm, polished master that preserves the tropical atmosphere

### Gnawa
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the hypnotic, trance-inducing quality; the repetitive patterns build spiritual intensity through subtle dynamic growth
**EQ focus**: Sintir (bass lute) warmth and depth (60-300 Hz), krakeb (metal castanets) brightness (3-8 kHz), vocal chant presence (1-4 kHz), handclap rhythm (4-6 kHz)
**MCP command**: `master_audio(album_slug, genre="gnawa")`

**Characteristics**:
- The sintir (three-stringed bass lute) is the tonal and rhythmic foundation; its deep, buzzy tone must be warm and prominent
- Krakebs (large metal castanets) provide the hypnotic rhythmic pulse; their metallic ring should be clear without being harsh
- Call-and-response vocal chanting builds intensity over time; preserve the gradual dynamic arc
- Traditional gnawa (Maalem musicians): wider dynamics, more acoustic, trance-ceremony atmosphere; fusion gnawa: tighter, more produced
- The trance-inducing quality depends on repetition and subtle variation; do not over-process the hypnotic groove
- Warm, organic master preferred; the spiritual quality of the music should carry through

### Bhangra
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; punchy, energetic, and dancefloor-ready; the dhol-driven rhythm must hit hard and propel movement
**EQ focus**: Dhol punch and body (60-200 Hz), tumbi brightness (2-6 kHz), vocal clarity (2-5 kHz), synth/bass weight (40-100 Hz), percussion detail (4-8 kHz)
**MCP command**: `master_audio(album_slug, genre="bhangra")`

**Characteristics**:
- The dhol is the genre's heartbeat -- its double-headed punch must be powerful, tight, and felt physically
- Tumbi (single-stringed instrument) provides the iconic melodic hook; keep it bright and cutting
- Vocals are energetic and call-and-response oriented; clear and present above the dense rhythmic production
- Traditional bhangra: more acoustic, dhol-forward; UK British Asian bhangra: heavier electronic production, bass-forward
- Modern bhangra-pop fusion: treat more like mainstream pop with dhol elements; keep it radio-ready
- The genre is party music -- energy, punch, and dancefloor impact are the priorities

### Enka
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the wide dynamic range and emotional delivery; enka's melismatic vocal technique (kobushi) requires headroom for ornamental expression
**EQ focus**: Vocal warmth and presence (1-4 kHz), shamisen/koto clarity (2-6 kHz), string arrangement body (200-600 Hz), gentle high-frequency air
**MCP command**: `master_audio(album_slug, genre="enka")`

**Characteristics**:
- The vocal is everything -- kobushi (melismatic vibrato technique) requires careful dynamic preservation; over-compression flattens the ornamental delivery
- Yonanuki (pentatonic) scale gives the genre its distinctive Japanese melancholy; preserve the tonal purity
- Traditional instruments (shamisen, koto, shakuhachi) sit alongside Western strings; both need clear presence
- Classic enka: wider dynamics, more orchestral; modern enka: slightly tighter, pop-influenced production
- The emotional arc from quiet restraint to powerful climax defines the genre; protect this dynamic range
- A warm, spacious master captures enka's melancholy better than aggressive processing

### Boogaloo
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the funky, loose groove and party energy; the dance rhythm must feel alive and bouncy
**EQ focus**: Bass groove (60-150 Hz), horn brightness (1-4 kHz), piano and organ warmth (200-600 Hz), percussion clarity (3-6 kHz), vocal presence (2-5 kHz)
**MCP command**: `master_audio(album_slug, genre="boogaloo")`

**Characteristics**:
- The fusion of Afro-Cuban rhythms with R&B creates a unique dance groove; preserve the rhythmic interplay
- Bass lines are melodic and funky (R&B influenced); keep them warm, round, and groove-driving
- Horn sections carry the melody; bright and punchy without harshness
- Piano/organ comping provides harmonic bed; warm and rhythmic, locked to the percussion
- Joe Cuba/Pete Rodriguez-style: tighter, more produced; raw boogaloo: looser, more live-sounding
- The genre bridges Latin and soul; the master should honor both traditions with warmth and punch

### Musical Comedy
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; vocal clarity is paramount as comedic timing depends on every word being heard; preserve dynamic contrasts for comedic effect
**EQ focus**: Vocal presence and clarity (2-5 kHz), backing track warmth (200-500 Hz), instrument separation for comedic timing, sibilance control (6-8 kHz)
**MCP command**: `master_audio(album_slug, genre="musical-comedy")`

**Characteristics**:
- Every word must be heard -- comedic timing depends on perfect vocal intelligibility; this is non-negotiable
- Musical style varies wildly (parody can mimic any genre); adapt EQ approach to the style being parodied while keeping vocals forward
- Weird Al-style parody: match the production style of the original genre but keep vocals clearer than the original would
- Bo Burnham-style comedy songs: more intimate, singer-songwriter production; preserve the dry delivery
- Spoken word comedy sections within songs need the same clarity standard as sung sections
- Dynamic contrasts for comedic effect (sudden quiet, loud punchlines) are intentional; do not flatten them

### Video Game Music
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the wide dynamic range from quiet ambient exploration to epic boss battle themes; the cinematic scope must translate
**EQ focus**: Orchestral warmth (200-600 Hz), synth clarity (1-4 kHz), chiptune brightness (2-8 kHz), bass definition (60-150 Hz), percussion impact (3-6 kHz)
**MCP command**: `master_audio(album_slug, genre="video-game-music")`

**Characteristics**:
- Style ranges from chiptune 8-bit to full orchestral; identify the subgenre and master accordingly
- Chiptune/retro (Koji Kondo NES era): preserve the bright, square-wave character; do not over-smooth the digital aesthetic
- Orchestral (Nobuo Uematsu, Yoko Shimomura): treat like cinematic/classical mastering with wider dynamics
- Electronic/modern (Doom, Celeste): treat like electronic or rock mastering depending on the style
- Boss battle themes need maximum impact and energy; exploration/ambient themes need space and subtlety
- The genre often includes wide tonal variety within a single album; master each track to its style while maintaining album cohesion

### Cabaret
**LUFS target**: -15 LUFS
**Dynamics**: Light-to-moderate compression; preserve the theatrical dynamics and vocal performance; the intimate-to-dramatic range defines the genre's emotional power
**EQ focus**: Vocal clarity and theatricality (2-5 kHz), piano/accordion warmth (200-600 Hz), bass definition (80-200 Hz), brass presence (1-4 kHz)
**MCP command**: `master_audio(album_slug, genre="cabaret")`

**Characteristics**:
- The vocal performance is the centerpiece -- theatrical, intimate, and dynamic; every word and inflection matters
- Weimar cabaret: darker, more intimate, wider dynamics; dark cabaret (Dresden Dolls, Tiger Lillies): edgier, can push to -14 LUFS
- Burlesque/neo-cabaret: more polished, showier; vintage warmth appropriate
- Piano is the primary accompaniment; keep it warm and supportive without competing with the voice
- Brass and wind instruments add color; clear without harshness
- The intimate venue atmosphere should carry through; do not over-brighten or make it sound like a stadium

### Tropical House
**LUFS target**: -14 LUFS
**Dynamics**: Light compression; preserve the breezy, open feel and the sidechain pump that defines the groove; avoid over-compressing -- tropical house relies on space and air between elements
**EQ focus**: Warm low-end (60-150 Hz), marimba/pan flute clarity (1-5 kHz), vocal presence (2-4 kHz), gentle high-mid cut to tame digital synth harshness (3-5 kHz), airy highs (10+ kHz)
**MCP command**: `master_audio(album_slug, genre="tropical-house")`

**Characteristics**:
- Marimba, steel drums, and pan flute sit in the 1-5 kHz range -- preserve their brightness and attack without harshness; these are the genre's signature timbres
- Soft kick drums should be warm and round, not punchy or aggressive; avoid boosting kick transients
- Sidechain compression on pads is a core production technique -- the pumping effect is intentional and should be preserved through mastering
- Vocals are soft and breathy; they need presence at 2-4 kHz without sibilance; de-essing may be needed
- Acoustic guitar and plucked synths need clarity without sharpness; warm low-mids (200-400 Hz) add body
- The overall mix should feel warm, spacious, and polished -- do not add aggression or density that contradicts the genre's laid-back character
- Hi-hats and shakers provide subtle rhythmic texture; preserve their sparkle at 8-12 kHz without letting them dominate

### Bass House
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; sustain the energy and impact of the bass drop while preserving the four-on-the-floor groove; the distorted bass must feel heavy and physical without losing definition against the kick drum
**EQ focus**: Sub-bass weight (30-60 Hz), distorted mid-bass presence and definition (80-400 Hz), kick drum punch (60-100 Hz), hi-hat and percussion crispness (8-12 kHz), gentle high-mid cut to tame synth harshness in the bass design (3-5 kHz)
**MCP command**: `master_audio(album_slug, genre="bass-house")`

**Characteristics**:
- The distorted bassline is the genre's centerpiece -- it must be heavy, present, and felt physically; preserve the saturation and harmonic content that gives bass house its gritty character
- Kick and bass must coexist cleanly despite occupying overlapping frequency ranges; tight sidechain compression between kick and bass is essential to maintain the pumping groove
- Sub-bass (30-60 Hz) provides the foundation beneath the distorted mid-bass (80-400 Hz); careful layering separation prevents mud without thinning the combined impact
- Vocal chops and samples are production elements, not lead vocals; keep them punchy and defined but not competing with the bass for attention
- Festival-ready variants (Jauz, Habstrakt style): can push slightly louder, more aggressive limiting; underground/Night Bass style: slightly more dynamic, groove-focused
- Builds and breakdowns create tension-release arcs; preserve the contrast between stripped-back sections and full bass drops
- Hi-hats and percussion should remain crisp and swung; over-compression flattens the groove feel that distinguishes bass house from straight EDM

### Art Pop
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the experimental production details and dynamic contrasts; art pop's sonic ambition depends on headroom for unconventional arrangements
**EQ focus**: Vocal clarity (2-5 kHz), synth/production detail (1-6 kHz), bass definition (60-150 Hz), high-frequency sparkle for textural elements
**MCP command**: `master_audio(file, genre="art-pop")`

**Characteristics**:
- Production is the instrument -- every sonic detail is intentional; preserve experimental textures and unconventional arrangements
- Vocals range from intimate to theatrical; dynamic range in the vocal performance must be maintained
- Kate Bush/Bjork-style: wider dynamics, more experimental; St. Vincent-style: tighter, more rock-forward
- Synth layers, samples, and sound design occupy the full spectrum; avoid broad EQ moves that flatten intentional choices
- Bass can be minimal or prominent depending on the track; follow the production intent
- The genre rewards careful, detail-oriented mastering that preserves the artist's sonic vision

### Piano Pop
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the piano's natural dynamics while maintaining vocal clarity; the interplay between voice and piano is the genre's emotional core
**EQ focus**: Vocal warmth and presence (2-5 kHz), piano body (200-600 Hz), piano attack clarity (2-4 kHz), gentle high-frequency air
**MCP command**: `master_audio(file, genre="piano-pop")`

**Characteristics**:
- Piano and voice are the two primary elements; both need space without competing
- Piano body in the 200-600 Hz range should be warm and full without muddiness
- Vocal sibilance control important since sparse arrangements expose harshness
- Sara Bareilles/Ben Folds-style: more produced, fuller arrangements; intimate singer-songwriter piano: wider dynamics, less compression
- String and band elements (when present) support the piano-vocal core; keep them lush but behind
- The genre rewards a warm, intimate master; over-processing removes the emotional directness

### Noise Pop
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the contrast between sweet melodies and abrasive textures; noise pop's charm is the collision of pop structure with noise elements
**EQ focus**: Vocal melody presence (2-5 kHz), guitar noise and feedback character (800 Hz-3 kHz), bass warmth (80-200 Hz), high-mid cut to tame harshness without removing the noise (-1.5 dB at 3.5 kHz)
**MCP command**: `master_audio(file, genre="noise-pop")`

**Characteristics**:
- Melodic vocals sit on top of noisy, distorted instrumentation; vocal clarity is essential despite the chaos
- Guitar feedback and distortion are compositional elements; preserve their character
- Jesus and Mary Chain-style: wall of feedback behind pop hooks; DIIV/No Age-style: cleaner noise textures
- Bass should be warm and present beneath the noise; it anchors the pop structure
- High-frequency content from distortion and feedback needs management but not elimination
- The sweet-and-sour balance between melody and noise defines the genre; protect both sides

### Jangle Pop
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the bright, chiming guitar textures and vocal clarity; the ringing, arpeggiated guitars need headroom
**EQ focus**: Guitar shimmer and chime (2-6 kHz), vocal warmth (2-4 kHz), bass definition (80-200 Hz), high-frequency sparkle for guitar harmonics (8-12 kHz)
**MCP command**: `master_audio(file, genre="jangle-pop")`

**Characteristics**:
- Chiming, arpeggiated Rickenbacker-style guitars define the genre; preserve their bright, ringing quality
- Vocals are melodic and often multi-tracked; keep them warm and present
- R.E.M.-style: slightly murky, more atmospheric; The Byrds-lineage: brighter, more crystalline
- Bass provides melodic counterpoint; keep it defined and not competing with guitar shimmer
- Drum production should be natural and not overly punchy; the genre favors a live, room-sound aesthetic
- High-mid harshness from bright guitars: gentle cuts at 3.5-5 kHz without dulling the chime

### Anisong
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; dense, polished J-Pop-influenced production with dramatic builds for anime openings; match the high-energy market expectations
**EQ focus**: Vocal brightness and clarity (2-6 kHz), guitar and synth energy (1-4 kHz), bass punch (60-100 Hz), orchestral layers (200-600 Hz)
**MCP command**: `master_audio(file, genre="anisong")`

**Characteristics**:
- Vocals are bright, powerful, and forward; anisong demands vocal energy and clarity above all
- Dense arrangements with guitars, synths, strings, and drums all competing for space; careful separation essential
- Dramatic builds to chorus are the genre's emotional payoff; preserve the dynamic arc
- LiSA/Aimer-style power vocals: more compression acceptable; quieter character songs: wider dynamics
- Mix density is typically very high; every element needs its frequency pocket
- The genre expects loudness and energy; a polished, radio-ready master is appropriate

### Cantopop
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; polished, radio-ready production; vocal clarity and sweetness are the priority
**EQ focus**: Vocal presence and warmth (2-5 kHz), piano/keyboard body (200-500 Hz), string arrangement sweetness (300-600 Hz), clean top end
**MCP command**: `master_audio(file, genre="cantopop")`

**Characteristics**:
- Vocals are the absolute center; Cantopop emphasizes vocal beauty and emotional delivery
- Ballads are the dominant form; preserve the dynamic arc from quiet verse to full chorus
- Sam Hui-style classic: warmer, more vintage; contemporary Cantopop: cleaner, more produced
- Production is clean and polished; avoid overly aggressive processing
- Piano, strings, and synth pads support the vocal; keep them lush but behind
- Cantonese tones require careful vocal treatment; avoid processing that obscures tonal distinctions

### Thai Pop
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; polished mainstream pop production with local melodic character
**EQ focus**: Vocal clarity (2-5 kHz), synth/keyboard warmth (200-500 Hz), bass definition (60-150 Hz), percussion detail (4-8 kHz)
**MCP command**: `master_audio(file, genre="thai-pop")`

**Characteristics**:
- Vocals are clear, warm, and emotionally present; Thai pop emphasizes vocal melody and delivery
- Production ranges from acoustic ballads to electronic dance-pop; adapt mastering to the specific style
- Luk thung-influenced tracks: warmer, more traditional; modern T-Pop: cleaner, K-Pop-influenced
- String and keyboard arrangements add emotional color; keep them supportive but not competing with vocals
- Bass should be defined and modern; not overly sub-heavy
- A polished, radio-ready master is appropriate for the genre's commercial orientation

### Turkish Pop
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve vocal ornamentation and melismatic delivery while maintaining radio-ready loudness
**EQ focus**: Vocal presence (1-4 kHz), saz/baglama clarity (2-6 kHz), bass punch (60-150 Hz), darbuka transients (3-5 kHz), high-mid cut to tame synth harshness
**MCP command**: `master_audio(file, genre="turkish-pop")`

**Characteristics**:
- Melismatic vocal ornamentation needs headroom; over-compression smears the ornamental delivery
- Saz/baglama provides the genre's distinctive melodic flavor; preserve its bright, metallic character
- Darbuka and percussion transients should remain crisp and defined
- Tarkan/Sezen Aksu-style: more polished, pop-forward; Arabesque-influenced: warmer, more emotional dynamics
- Modal melodic inflections distinguish Turkish pop from Western pop; preserve tonal purity
- Bass can be electronic or acoustic depending on production style; follow the mix intent

### Trot
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; polished Korean retro-pop production; vocal clarity and warmth are the priority
**EQ focus**: Vocal presence and sweetness (2-5 kHz), bass punch (60-150 Hz), synth warmth (200-500 Hz), percussion crispness (4-8 kHz)
**MCP command**: `master_audio(file, genre="trot")`

**Characteristics**:
- Vocals are clear, emotive, and forward; trot emphasizes vocal power and emotional delivery
- The genre's distinctive rhythmic bounce must remain lively; over-compression kills the groove
- Classic trot (Na Hoon-a style): warmer, more vintage; new trot (Young Tak style): modern, K-Pop-influenced production
- Synth and keyboard arrangements provide harmonic color; keep them bright but supportive
- The two-beat rhythm pattern is the genre's rhythmic identity; preserve its driving energy
- A polished, radio-ready master matches the genre's commercial aspirations

### Kayokyoku
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; polished 1960s-80s Japanese pop production aesthetic with warm, vintage character
**EQ focus**: Vocal warmth and presence (2-5 kHz), orchestral arrangement body (200-600 Hz), guitar clarity (800 Hz-2 kHz), vintage top-end air
**MCP command**: `master_audio(file, genre="kayokyoku")`

**Characteristics**:
- Vocals are the centerpiece; warm, clear, and emotionally delivered in the classic Japanese popular song tradition
- Orchestral and band arrangements support the vocal; lush strings and brass add drama
- Production aesthetic should feel warm and slightly vintage; avoid clinical modern brightness
- Hibari Misora/Seiko Matsuda-style: wider dynamics, more theatrical; pop-rock kayokyoku: tighter, more energetic
- The genre bridges enka tradition and modern pop; balance traditional warmth with contemporary clarity
- A warm, rounded master captures the genre's golden-age aesthetic

### Laiko
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve bouzouki ornamentation and vocal melisma; radio-ready loudness with dynamic expression
**EQ focus**: Vocal presence (1-4 kHz), bouzouki clarity (2-6 kHz), bass warmth (60-150 Hz), percussion crispness (4-8 kHz)
**MCP command**: `master_audio(file, genre="laiko")`

**Characteristics**:
- Bouzouki is the genre's signature instrument; its bright, metallic tone needs clear presence without harshness
- Melismatic vocal delivery with modal inflections requires headroom; over-compression flattens ornamentation
- Classic laiko (Kazantzidis style): warmer, wider dynamics; moderna laika: more polished, synth-driven
- Zeimbekiko and hasapiko rhythms inherited from rebetiko define the groove; preserve rhythmic clarity
- Synths and electronic production in modern laiko should be balanced with traditional instrument character
- A warm, full-bodied master suits the genre's emotional intensity

### Abstract Hip-Hop
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the experimental production details and unconventional beat structures; the genre's sonic adventurousness needs headroom
**EQ focus**: Vocal clarity (2-5 kHz), experimental production detail (full spectrum), bass definition (60-150 Hz), sample texture preservation
**MCP command**: `master_audio(file, genre="abstract-hip-hop")`

**Characteristics**:
- Production is experimental and detail-oriented; every sonic element is intentional; preserve unconventional textures
- Vocals carry dense, layered lyricism; clarity and intelligibility are critical despite complex production
- Aesop Rock/MF DOOM-style: denser, lo-fi-tolerant; Antipop Consortium-style: more electronic, cleaner
- Beat structures may be non-traditional; preserve rhythmic complexity and micro-details
- Sample-based production with unusual sources needs careful treatment; do not over-process
- The genre rewards a mastering approach that respects the experimental intent

### Horrorcore
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; dark, aggressive production with horror-film atmosphere; punchy and menacing
**EQ focus**: Vocal presence and clarity (2-5 kHz), bass weight (40-100 Hz), dark synth textures (200-600 Hz), percussion punch (3-6 kHz)
**MCP command**: `master_audio(file, genre="horrorcore")`

**Characteristics**:
- Vocals are clear and forward; the lyrical content depends on intelligibility for impact
- Dark, cinematic production with horror-film sound design elements; preserve atmospheric textures
- Bass should be heavy and menacing; sub-bass adds to the ominous atmosphere
- Three 6 Mafia/Brotha Lynch Hung-style: more lo-fi, Southern; Tech N9ne-style: more polished, faster
- Sound effects and samples are compositional elements; preserve their character and placement
- A dark, punchy master suits the genre's aggressive, theatrical character

### Jazz Rap
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the warmth and organic quality of jazz instrumentation while maintaining hip-hop vocal presence
**EQ focus**: Vocal clarity (2-5 kHz), jazz sample warmth (200-600 Hz), bass groove (60-150 Hz), horn/piano detail (1-4 kHz)
**MCP command**: `master_audio(file, genre="jazz-rap")`

**Characteristics**:
- Jazz instrumentation (piano, bass, horns, drums) provides the harmonic bed; keep it warm and organic
- Vocals must be clear and present above the musical arrangement
- A Tribe Called Quest/Guru's Jazzmatazz-style: smoother, more integrated; modern jazz rap: more experimental
- Live instrument feel is essential; do not over-process or make it sound clinical
- Bass is melodic and warm (jazz tradition); not aggressive or sub-heavy
- The fusion of jazz warmth with hip-hop punch requires balanced mastering

### Emo Rap
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve emotional vocal dynamics and atmospheric production; the genre blends melodic vulnerability with hip-hop punch
**EQ focus**: Vocal presence and emotion (2-5 kHz), guitar textures (800 Hz-2 kHz), bass weight (40-100 Hz), atmospheric reverb preservation, high-mid cut for guitar harshness
**MCP command**: `master_audio(file, genre="emo-rap")`

**Characteristics**:
- Vocals blend rapping with singing; both styles need clarity and emotional presence
- Guitar-driven production (emo/pop-punk influence) combined with trap beats; balance both elements
- Lil Peep/Juice WRLD-style: more melodic, atmospheric; $uicideboy$-style: darker, harder
- Bass is typically heavy (trap influence); keep it punchy and defined
- Reverb and atmospheric effects are compositional; preserve the dreamy or dark mood
- Emotional dynamic range matters; do not flatten vulnerability with over-compression

### Latin Trap
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; punchy, bass-heavy production with trap rhythms; radio and club ready
**EQ focus**: Bass weight (40-80 Hz), vocal presence (2-5 kHz), hi-hat crispness (8-12 kHz), 808 kick definition (40-60 Hz)
**MCP command**: `master_audio(file, genre="latin-trap")`

**Characteristics**:
- 808 bass is the foundation; heavy, defined, and physically felt
- Vocals blend Spanish-language delivery with melodic auto-tuned hooks; clarity essential
- Bad Bunny/Anuel AA-style: more melodic, varied; harder Latin trap: more aggressive, closer to drill
- Hi-hats and trap percussion patterns need crisp transient detail
- Dembow rhythm elements when present should be punchy and driving
- A loud, polished, club-ready master is appropriate for the genre

### Plugg
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the dreamy, spacious quality of the production; plugg's ethereal beat textures need headroom
**EQ focus**: Vocal presence with auto-tune warmth (2-5 kHz), synth melody clarity (1-4 kHz), bass warmth (40-100 Hz), sparkle and shimmer (8-12 kHz)
**MCP command**: `master_audio(file, genre="plugg")`

**Characteristics**:
- Airy, melodic synth patterns define the beat; preserve their dreamy, bell-like quality
- Auto-tuned vocals need warmth and clarity; the melodic vocal style is central
- Bass is warm and round, not aggressive; it supports the dreamy atmosphere
- Hi-hats and trap percussion are subtle, not dominant; preserve their crisp detail without harshness
- The genre favors a spacious, lo-fi-adjacent aesthetic; do not over-process or over-brighten
- A warm, airy master preserves plugg's distinctive ethereal character

### Alternative R&B
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the atmospheric, experimental production and intimate vocal dynamics; the genre's innovation lives in sonic detail
**EQ focus**: Vocal intimacy and presence (2-5 kHz), electronic texture detail (1-6 kHz), bass depth (40-100 Hz), high-frequency shimmer for production elements
**MCP command**: `master_audio(file, genre="alternative-rnb")`

**Characteristics**:
- Vocals are intimate, often processed with effects (reverb, distortion, pitch manipulation); preserve the production intent
- Electronic and experimental production textures occupy the full spectrum; avoid broad EQ moves
- Frank Ocean/The Weeknd-style: atmospheric, spacious; SZA/Kelela-style: more textured, experimental
- Bass can be deep and atmospheric or minimal; follow the production intent
- The genre rewards detail-oriented mastering that preserves sonic experimentation
- Spatial effects (reverb, delay, panning) are compositional; do not collapse the stereo image

### Quiet Storm
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the intimate, late-night atmosphere; quiet storm depends on warmth, space, and gentle dynamics
**EQ focus**: Vocal warmth and intimacy (2-4 kHz), bass groove (60-150 Hz), keyboard/synth warmth (200-500 Hz), gentle high-frequency air
**MCP command**: `master_audio(file, genre="quiet-storm")`

**Characteristics**:
- Vocals are warm, intimate, and seductive; never harsh or bright; sibilance control important
- Bass is smooth and groovy; warm and round, felt rather than punchy
- Keyboards and synth pads create the late-night atmosphere; warm and enveloping
- Luther Vandross/Sade-style: polished, sophisticated; Anita Baker-style: jazzier, more dynamic
- The genre is designed for intimate listening; the master should feel effortless and warm
- Over-compression or brightness destroys the late-night mood; less processing is more

### New Jack Swing
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; punchy, drum-machine-driven production with R&B vocal smoothness; radio-ready energy
**EQ focus**: Drum machine punch (60-100 Hz), vocal clarity and sweetness (2-5 kHz), synth bass definition (40-80 Hz), percussion crispness (4-8 kHz)
**MCP command**: `master_audio(file, genre="new-jack-swing")`

**Characteristics**:
- Drum machine patterns (808/909) must be punchy and driving; they define the genre's rhythmic energy
- Vocals blend R&B smoothness with hip-hop attitude; clear and present
- Teddy Riley-style production: tight, punchy, radio-ready; the genre demands a polished master
- Synth bass is prominent and defined; not overly sub-heavy
- Group vocal harmonies are common; keep them full without smearing
- The genre bridges hip-hop and R&B; the master should honor both the punch and the smoothness

### Northern Soul
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the energy and urgency of the vocals and driving rhythm; the dancefloor energy must translate
**EQ focus**: Vocal power and clarity (2-5 kHz), bass punch (80-200 Hz), tambourine and percussion brightness (6-10 kHz), horn warmth (1-4 kHz)
**MCP command**: `master_audio(file, genre="northern-soul")`

**Characteristics**:
- Vocals are powerful, urgent, and emotionally charged; they must cut through clearly
- The driving, uptempo rhythm is the genre's identity; preserve the dancefloor energy
- Bass and drums provide the propulsive backbone; punchy and defined
- Tambourine and percussion add brightness and drive; crisp without harshness
- The genre favors a warm, analog-influenced master; vintage character is appropriate
- Horn and string arrangements add drama; keep them present but behind vocals

### Psychedelic Soul
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the trippy production effects and dynamic range; psychedelic elements need space
**EQ focus**: Vocal warmth (2-5 kHz), bass groove (60-150 Hz), psychedelic effects preservation, wah-wah guitar presence (800 Hz-3 kHz)
**MCP command**: `master_audio(file, genre="psychedelic-soul")`

**Characteristics**:
- Psychedelic production effects (phaser, wah-wah, reverb, tape manipulation) are compositional; preserve their character
- Vocals should be warm and present but can sit within the psychedelic haze
- Sly Stone/Temptations-style: more experimental, wider dynamics; Curtis Mayfield-style: warmer, more orchestral
- Bass is groovy and prominent (funk influence); warm and defined
- String and horn arrangements add orchestral color; keep them lush and psychedelic
- The genre rewards a warm, spacious master that preserves the trippy atmosphere

### P-Funk
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the bass-heavy groove and funky dynamics; the low end is the genre's foundation
**EQ focus**: Bass guitar warmth and groove (40-150 Hz), synth presence (200-600 Hz), vocal clarity (2-5 kHz), horn brightness (1-4 kHz), percussion punch (3-6 kHz)
**MCP command**: `master_audio(file, genre="p-funk")`

**Characteristics**:
- Bootsy Collins-style bass is the genre's identity; deep, funky, and prominent; never buried
- Layered production with multiple synths, horns, guitars, and vocals all competing for space
- George Clinton/Parliament-Funkadelic: maximalist, dense, funky; everything is turned up
- Vocal layers and group vocals are common; keep them full and funky without smearing
- Horn sections add brass punch and melody; bright without harshness
- The genre expects a fat, bass-heavy, funky master; clinical brightness is the enemy

### Boogie
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the groovy, dancefloor-ready energy; the rhythm and bass drive must remain alive
**EQ focus**: Bass groove (60-150 Hz), synth presence (200-600 Hz), vocal clarity (2-5 kHz), drum machine punch (60-100 Hz), hi-hat crispness (8-12 kHz)
**MCP command**: `master_audio(file, genre="boogie")`

**Characteristics**:
- Bass (synth or electric) drives the dance groove; warm, funky, and prominent
- Drum machine patterns provide the rhythmic backbone; punchy and defined
- Vocals blend R&B smoothness with disco energy; clear and present
- Synth pads and melodic lines add harmonic color; keep them warm and groovy
- The genre bridges disco, funk, and early electro; the master should be warm and punchy
- A polished, dancefloor-ready master is appropriate

### Trap Soul
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the atmospheric, intimate production and vocal nuance; the genre's emotional depth lives in dynamic subtlety
**EQ focus**: Vocal warmth and intimacy (2-5 kHz), 808 bass weight (40-80 Hz), synth pad atmosphere (200-500 Hz), hi-hat detail (8-12 kHz)
**MCP command**: `master_audio(file, genre="trap-soul")`

**Characteristics**:
- Vocals are intimate, often heavily processed with reverb and auto-tune; preserve the moody atmosphere
- 808 bass is deep and warm; it provides the low-end foundation without being aggressive
- Bryson Tiller/6LACK-style: atmospheric, moody; Summer Walker-style: more intimate, R&B-forward
- Trap hi-hats and percussion provide subtle rhythmic texture; crisp but not dominant
- Synth pads create the dark, atmospheric mood; warm and enveloping
- The genre rewards a warm, spacious master that preserves emotional intimacy

### Doo-Wop
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the vocal harmony dynamics and natural room sound; the genre's charm is in the vocal interplay
**EQ focus**: Vocal group warmth and clarity (2-5 kHz), bass vocal presence (80-200 Hz), gentle vintage warmth (200-500 Hz), high-frequency air
**MCP command**: `master_audio(file, genre="doo-wop")`

**Characteristics**:
- Multi-part vocal harmonies are the genre's core; each voice part needs clarity within the blend
- Bass vocal provides the rhythmic and harmonic foundation; warm and defined
- Lead vocal soars above the harmony; present and emotionally delivered
- Minimal instrumentation means the vocal arrangement is exposed; imperfections are character
- A warm, vintage-sounding master captures the genre's 1950s aesthetic
- Over-processing removes the intimate, street-corner charm that defines the genre

### Arena Rock
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; punchy, stadium-ready production; the genre demands power and clarity at scale
**EQ focus**: Guitar power (800 Hz-3 kHz), vocal clarity and power (2-5 kHz), bass and kick punch (60-150 Hz), cymbal energy (8-12 kHz), keyboard layers (200-600 Hz)
**MCP command**: `master_audio(file, genre="arena-rock")`

**Characteristics**:
- Big, powerful guitar riffs and solos need clarity and presence; they define the genre's energy
- Vocals must cut through dense, loud arrangements; clear, powerful, and anthemic
- Journey/Def Leppard-style: more polished, melodic; AC/DC-style: rawer, more riff-driven
- Drums are big and punchy; room sound and reverb add the arena scale
- Keyboard and synth layers add width and drama; keep them present but behind guitars and vocals
- The genre expects a loud, polished, radio-ready master; subtlety is not the goal

### Heartland Rock
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the raw, emotional dynamics and working-class authenticity; polished but not slick
**EQ focus**: Vocal presence and character (2-5 kHz), guitar warmth (800 Hz-2 kHz), bass punch (80-200 Hz), piano/organ body (200-500 Hz), drum room sound
**MCP command**: `master_audio(file, genre="heartland-rock")`

**Characteristics**:
- Vocals are raw, honest, and emotionally direct; preserve the character and grit
- Guitar tones range from clean jangle to overdriven power chords; both need space
- Springsteen/Mellencamp-style: driving, band-oriented; Tom Petty-style: cleaner, more melodic
- Piano and organ add harmonic depth; warm and supportive
- The E Street Band-style wall of sound needs careful management; every instrument contributes
- A warm, powerful master that preserves authenticity over polish

### Piano Rock
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the interplay between piano and rock instrumentation; the piano must remain articulate in the context of full-band arrangements
**EQ focus**: Piano clarity and attack (1-4 kHz), vocal presence (2-5 kHz), guitar body (800 Hz-2 kHz), bass punch (80-200 Hz), drum impact (3-6 kHz)
**MCP command**: `master_audio(file, genre="piano-rock")`

**Characteristics**:
- Piano is both rhythmic and melodic; preserve its attack and body alongside guitars
- Vocals are clear and expressive; they must cut through the dense piano-guitar arrangement
- Billy Joel/Elton John-style: more polished, pop-leaning; Ben Folds-style: punkier, more energetic
- Bass provides the rhythmic foundation; punchy and defined beneath piano and guitar
- Guitar and piano occupy similar frequency ranges; careful separation prevents muddiness
- The genre demands clarity and energy; a polished, dynamic master is appropriate

### Space Rock
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the expansive, atmospheric quality and extended psychedelic passages; space rock needs sonic room to breathe
**EQ focus**: Guitar texture and effects (800 Hz-3 kHz), bass warmth (60-200 Hz), synth atmosphere (200-600 Hz), reverb and delay preservation, high-frequency shimmer
**MCP command**: `master_audio(file, genre="space-rock")`

**Characteristics**:
- Reverb, delay, and other spatial effects are compositional elements; over-compression collapses the vast sonic spaces
- Guitar textures range from ambient washes to distorted riffs; preserve their spatial character
- Hawkwind-style: heavier, more propulsive; Spiritualized-style: more layered, orchestral; Spacemen 3-style: more minimal, droning
- Bass provides a warm, constant foundation; not aggressive but deeply felt
- Extended instrumental passages need dynamic breathing room; do not flatten the sonic journey
- The genre rewards a spacious, atmospheric master; clinical tightness is antithetical

### Rockabilly
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the raw, energetic slap-back echo and rhythmic drive; the genre's energy comes from its loose, live feel
**EQ focus**: Vocal presence (2-5 kHz), upright bass slap (80-200 Hz + 2-4 kHz attack), guitar twang (2-6 kHz), drum snap (3-6 kHz)
**MCP command**: `master_audio(file, genre="rockabilly")`

**Characteristics**:
- Slap-back echo on vocals is a genre-defining effect; preserve its character
- Upright/standup bass slap provides both low end and percussive attack; both elements need clarity
- Guitar is bright, twangy, and raw; preserve the rockabilly tone without harshness
- Eddie Cochran/Gene Vincent-style: rawer, more primitive; Stray Cats/neo-rockabilly: tighter, more polished
- Drum production should feel live and energetic; minimal processing preserves authenticity
- A warm, slightly raw master captures the genre's rebellious energy

### Psychobilly
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; aggressive, high-energy production combining punk speed with rockabilly rawness
**EQ focus**: Upright bass distortion and slap (60-200 Hz + 2-4 kHz), guitar aggression (800 Hz-3 kHz), vocal urgency (2-5 kHz), drum attack (3-6 kHz)
**MCP command**: `master_audio(file, genre="psychobilly")`

**Characteristics**:
- Distorted upright bass is the genre's signature; heavy, aggressive slapping needs punch and definition
- Guitar is raw and aggressive; more distorted than rockabilly, less than punk
- The Cramps/Meteors-style: rawer, more horror-influenced; Tiger Army-style: more polished, melodic
- Vocals are urgent and often shouted; clear and present above the chaos
- Drum production should be fast and aggressive; snare cracks through the mix
- A punchy, aggressive master suits the genre's manic energy

### Krautrock
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the hypnotic, motorik rhythms and experimental textures; krautrock's repetitive structures build intensity through subtle variation
**EQ focus**: Motorik drum pattern clarity (3-6 kHz), synth texture detail (200 Hz-4 kHz), bass pulse (60-150 Hz), guitar texture and effects, high-frequency air for electronic textures
**MCP command**: `master_audio(file, genre="krautrock")`

**Characteristics**:
- Motorik beat (steady, metronomic 4/4) is the rhythmic foundation; preserve its hypnotic quality
- Synth textures and electronic experimentation are compositional elements; preserve their full character
- Can/Neu!-style: more rhythmic, driving; Tangerine Dream/Cluster-style: more ambient, electronic
- Guitar textures range from atmospheric to abrasive; follow the production intent
- Bass is often repetitive and hypnotic; warm and steady, anchoring the groove
- The genre rewards patient, minimal mastering; over-processing removes the hypnotic quality

### Jam Band
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the wide dynamic range of extended improvisations; jam bands live in the dynamic interplay between instruments
**EQ focus**: Guitar clarity (800 Hz-3 kHz), bass definition (80-200 Hz), keyboard/organ warmth (200-600 Hz), drum naturalness (3-6 kHz), vocal presence (2-5 kHz)
**MCP command**: `master_audio(file, genre="jam-band")`

**Characteristics**:
- Extended improvisations require wide dynamics; quiet passages and peaks are equally important
- Guitar solos and interplay are the focal point; clear and present across varied tones
- Grateful Dead-style: rawer, more psychedelic; Phish-style: more precise, technically complex
- Organ and keyboard provide harmonic bed; warm and present without muddiness
- Bass is melodic and interactive; it carries countermelodies alongside the guitar
- The genre rewards a live, natural-sounding master; studio polish is not the goal

### Canterbury Scene
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the sophisticated jazz-rock dynamics and complex arrangements; the genre's progressive nature depends on dynamic nuance
**EQ focus**: Keyboard/organ clarity (200 Hz-4 kHz), bass articulation (80-200 Hz), guitar textures (800 Hz-3 kHz), horn presence (1-4 kHz), drum precision (3-6 kHz)
**MCP command**: `master_audio(file, genre="canterbury-scene")`

**Characteristics**:
- Jazz-rock fusion arrangements with complex time signatures; preserve the technical interplay
- Keyboards (organ, electric piano) are central to the sound; warm and articulate
- Soft Machine/Caravan-style: more experimental, jazzier; Hatfield-style: more whimsical, song-oriented
- Bass is melodic and prominent (jazz influence); keep it warm and clearly defined
- The genre blends humor and complexity; dynamic expression is essential to the character
- A natural, wide-dynamic master preserves the genre's progressive sophistication

### Slowcore
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the sparse, minimal dynamics and quiet intensity; slowcore's emotional power comes from restraint and space
**EQ focus**: Vocal intimacy (2-4 kHz), guitar texture and reverb (800 Hz-3 kHz), bass warmth (80-200 Hz), high-frequency air, drum subtlety (3-6 kHz)
**MCP command**: `master_audio(file, genre="slowcore")`

**Characteristics**:
- Sparse arrangements mean every element is exposed; careful, minimal mastering is essential
- Vocals are intimate, quiet, and emotionally charged; preserve the vulnerability
- Low/Codeine-style: more minimalist, quieter; Red House Painters-style: warmer, more layered
- Guitar textures (clean, reverb-heavy) create atmospheric space; preserve the sonic depth
- Bass is sparse and supportive; warm and round, not prominent
- The genre is defined by its restraint; over-processing is the worst possible approach

### Post-Britpop
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; polished, radio-ready rock with melodic focus; anthemic and accessible
**EQ focus**: Vocal clarity and melody (2-5 kHz), guitar body (800 Hz-2 kHz), bass punch (80-200 Hz), drum energy (3-6 kHz)
**MCP command**: `master_audio(file, genre="post-britpop")`

**Characteristics**:
- Vocals are melodic, clear, and anthemic; they carry the hooks
- Guitar-driven but polished production; less raw than Britpop, more radio-friendly
- Coldplay/Travis-style: softer, more atmospheric; Stereophonics-style: harder, more rock-forward
- Bass and drums provide the rhythmic backbone; punchy and defined
- The genre favors a polished, commercial master; clean and anthemic
- Keyboard and string elements add emotional depth; supportive but not competing with guitar

### Dance-Punk
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the angular rhythmic energy and dancefloor drive; the genre fuses punk urgency with dance groove
**EQ focus**: Bass groove (60-150 Hz), angular guitar presence (800 Hz-3 kHz), vocal energy (2-5 kHz), drum machine/live drum punch (3-6 kHz), synth elements (200-600 Hz)
**MCP command**: `master_audio(file, genre="dance-punk")`

**Characteristics**:
- Bass drives the dance groove; prominent, funky, and rhythmically locked
- Angular guitar riffs add punk energy; preserve their jagged, percussive quality
- LCD Soundsystem-style: more electronic, longer; Gang of Four-style: tighter, more angular
- Vocals are energetic and sometimes spoken-word; clear and present
- Drum patterns blend punk energy with dance groove; punchy and driving
- The genre demands both punk urgency and dancefloor functionality; balance both

### No Wave
**LUFS target**: -14 LUFS
**Dynamics**: Minimal compression; preserve the abrasive, confrontational dynamics; no wave deliberately rejects sonic polish and conventional structure
**EQ focus**: Dissonant guitar/sax presence (1-5 kHz), bass noise (60-200 Hz), vocal rawness (2-5 kHz), high-mid harshness preserved intentionally (3-5 kHz)
**MCP command**: `master_audio(file, genre="no-wave")`

**Characteristics**:
- Abrasiveness and dissonance are intentional; do not try to smooth or tame the sound
- Atonal saxophone, detuned guitars, and noise are compositional elements
- James Chance-style: funk-influenced chaos; DNA/Mars-style: fractured, arrhythmic noise
- Lo-fi production quality is a feature; do not over-process or clean up
- Vocals are confrontational and raw; preserve their urgency and aggression
- The genre rejects all conventions including mastering conventions; minimal intervention is best

### Post-Punk Revival
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the angular guitar textures and bass-driven groove; the genre updates post-punk's sonic palette with modern production
**EQ focus**: Bass presence (80-200 Hz), angular guitar texture (800 Hz-3 kHz), vocal clarity (2-5 kHz), drum punch (3-6 kHz), synth atmosphere (200-600 Hz)
**MCP command**: `master_audio(file, genre="post-punk-revival")`

**Characteristics**:
- Bass is melodically prominent (post-punk tradition); clear, defined, and driving
- Angular guitar textures with effects (chorus, delay) define the sound; preserve their character
- Interpol/Editors-style: darker, more atmospheric; Franz Ferdinand-style: brighter, more danceable
- Vocals sit within the mix, not on top; present but not dominant
- Drum production is punchy and modern; tighter than original post-punk
- A polished but textured master suits the genre's updated aesthetic

### Hair Metal
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; polished, radio-ready production with big guitar tones and powerful vocals; the genre demands loudness and impact
**EQ focus**: Vocal power and clarity (2-5 kHz), guitar solo presence (1-4 kHz), bass punch (80-200 Hz), snare crack (1-3 kHz), keyboard shimmer (4-8 kHz)
**MCP command**: `master_audio(file, genre="hair-metal")`

**Characteristics**:
- Big, polished guitar tones with lots of gain; preserve the sustain and harmonic richness
- Vocals are powerful, high-register, and melodic; they must soar above the guitars
- Def Leppard-style: heavily layered, studio-polished; Motley Crue-style: rawer, more aggressive
- Drum production is big and reverberant; the 1980s gated reverb snare is a signature sound
- Guitar solos are a centerpiece; clear, singing tone with sustain
- The genre expects a big, loud, polished master; subtlety is not appropriate

### NWOBHM
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; raw, energetic production with twin-guitar harmonies and galloping rhythms; preserve the live-band energy
**EQ focus**: Guitar harmony clarity (1-4 kHz), vocal power (2-5 kHz), bass gallop (80-200 Hz), drum energy (3-6 kHz), high-mid cut for vintage rawness (3-5 kHz)
**MCP command**: `master_audio(file, genre="nwobhm")`

**Characteristics**:
- Twin guitar harmonies are the genre's signature; both guitar parts need clarity and separation
- Galloping bass and drum patterns define the rhythmic drive; preserve their energy and articulation
- Iron Maiden-style: more melodic, technical; Diamond Head-style: heavier, rawer
- Vocals are powerful and operatic; they must cut through the dense guitar work
- Production should retain a raw, live-band quality; not overly polished
- The genre bridges punk energy with metal complexity; the master should honor both

### Blackgaze
**LUFS target**: -16 LUFS
**Dynamics**: Light-to-moderate compression; preserve the wall of tremolo-picked guitars and ethereal atmosphere; blackgaze blends black metal's density with shoegaze's dreaminess
**EQ focus**: Guitar wall texture (800 Hz-4 kHz), vocal atmosphere (1-4 kHz), bass depth (60-200 Hz), high-mid cut to manage harshness while preserving the wash (-2 dB at 3.5 kHz), high-frequency shimmer
**MCP command**: `master_audio(file, genre="blackgaze")`

**Characteristics**:
- The guitar wall blends tremolo picking with shoegaze effects; preserve the lush, layered texture
- Vocals are often buried in the mix (shoegaze tradition); preserve their distant, ethereal quality
- Deafheaven/Alcest-style: more dynamic, melodic; heavier variants: closer to atmospheric black metal
- Bass provides depth beneath the guitar wash; felt rather than heard distinctly
- Clean/quiet passages contrast with walls of sound; preserve the dynamic range
- The genre rewards a warm, atmospheric master that preserves both beauty and harshness

### Melodic Death Metal
**LUFS target**: -14 LUFS
**Dynamics**: Heavy compression; sustain the intensity while preserving melodic guitar lines and harmonic complexity; the genre balances aggression with melody
**EQ focus**: Guitar melody clarity (1-4 kHz), growled vocal presence (1-4 kHz), bass tightness (60-200 Hz), high-mid cut for guitar harshness (3-5 kHz), high shelf cut for cymbal wash (-1 dB at 8 kHz)
**MCP command**: `master_audio(file, genre="melodic-death-metal")`

**Characteristics**:
- Melodic guitar harmonies must remain clear through the heavy distortion; the melody defines the genre
- Growled vocals need presence without overwhelming the guitar melodies
- At the Gates/In Flames-style Gothenburg sound: brighter, more melodic; Amon Amarth-style: heavier, more rhythmic
- Blast beats and double bass generate dense high-frequency cymbal content; high shelf cut prevents fatigue
- Clean vocal passages (when present) need dynamic contrast with harsh sections
- The genre demands both aggression and melodic clarity; balance is critical

### Drone Metal
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the massive, sustained tones and glacial dynamics; drone metal's power comes from sustained heaviness, not transient impact
**EQ focus**: Low-end body and sustain (30-200 Hz), guitar drone texture (200 Hz-2 kHz), feedback and harmonic overtones, minimal high-frequency processing
**MCP command**: `master_audio(file, genre="drone-metal")`

**Characteristics**:
- Sustained, monolithic tones are the genre's identity; preserve the massive, immovable quality
- Feedback and harmonic overtones are compositional elements; do not tame or gate them
- Sunn O)))-style: slower, more abstract; Earth-style: warmer, more melodic drone
- Bass frequencies can be extremely heavy; ensure low-end is powerful without distortion artifacts
- Dynamic movement is glacial; subtle shifts in texture matter more than loud-quiet contrast
- The genre demands patient mastering; less processing preserves the crushing weight

### Post-Metal
**LUFS target**: -16 LUFS
**Dynamics**: Light-to-moderate compression; preserve the wide dynamic range from quiet ambient passages to crushing heavy sections; the dynamic arc defines the genre
**EQ focus**: Guitar texture across clean and heavy tones (800 Hz-4 kHz), bass depth (60-200 Hz), vocal presence (1-4 kHz), atmospheric effects preservation, high-mid cut for heavy sections
**MCP command**: `master_audio(file, genre="post-metal")`

**Characteristics**:
- Quiet-to-heavy dynamic arcs over extended tracks are the genre's emotional structure; protect this dynamic range
- Guitar textures range from tremolo-picked walls to clean, reverb-heavy atmospherics; both need space
- Isis/Neurosis-style: more rhythmic, heavier; Russian Circles-style: more melodic, instrumental
- Bass provides depth and weight in heavy sections; warm atmosphere in quiet passages
- Reverb and delay are compositional; over-compression collapses the spatial depth
- Extended compositions (8-15 minutes) need careful energy management without fatigue

### Viking Metal
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; epic, battle-ready production with both heaviness and melodic grandeur
**EQ focus**: Guitar riff power (800 Hz-3 kHz), vocal clarity across clean and harsh (2-5 kHz), bass weight (60-200 Hz), keyboard/choir layers (200-600 Hz), high-mid cut for guitar harshness
**MCP command**: `master_audio(file, genre="viking-metal")`

**Characteristics**:
- Epic, anthemic quality with clean choir vocals and heavy instrumentation
- Vocals alternate between harsh and clean; both need intelligibility
- Amon Amarth-style: heavier, more death metal; Bathory-style: more epic, atmospheric
- Keyboard and choir elements add the epic scale; keep them present alongside the metal heaviness
- Folk instruments (when present) need clear mid-range presence
- The genre demands a powerful, epic-scale master with heaviness and grandeur

### Crossover Thrash
**LUFS target**: -14 LUFS
**Dynamics**: Heavy compression; fast, aggressive, and relentless; the genre fuses thrash metal speed with hardcore punk energy
**EQ focus**: Guitar speed and aggression (800 Hz-3 kHz), vocal urgency (2-5 kHz), bass punch (60-200 Hz), drum attack (3-6 kHz), high-mid cut for harshness (3-5 kHz)
**MCP command**: `master_audio(file, genre="crossover-thrash")`

**Characteristics**:
- Fast, aggressive riffs need articulation at speed; over-compression blurs rapid picking
- Vocals are shouted and urgent (hardcore influence); clear and present above the thrash chaos
- Suicidal Tendencies/D.R.I.-style: more punk-influenced; Municipal Waste-style: more thrash-influenced
- Bass is punchy and driving; locked in with the kick drum
- Short, fast songs need consistent energy; no wasted sonic space
- The genre expects aggression and energy; a tight, punchy master is appropriate

### Trap Metal
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; aggressive, bass-heavy production blending trap beats with metal intensity
**EQ focus**: 808 bass weight (30-80 Hz), distorted guitar presence (800 Hz-3 kHz), vocal aggression (2-5 kHz), hi-hat crispness (8-12 kHz), high-mid cut for harshness
**MCP command**: `master_audio(file, genre="trap-metal")`

**Characteristics**:
- 808 bass and metal guitars compete for low-frequency space; careful separation essential
- Vocals blend screaming/shouting with rap delivery; both styles need clarity
- Scarlxrd/City Morgue-style: more aggressive, industrial; softer variants: more melodic, emo-influenced
- Hi-hats and trap percussion patterns contrast with metal aggression; preserve both elements
- Distortion and noise are intentional production elements; preserve their character
- A loud, aggressive master suits the genre's confrontational energy

### Afro-House
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the organic percussion layers and deep groove; the genre blends African rhythmic traditions with house music structure
**EQ focus**: Percussion clarity (3-8 kHz), bass warmth (60-150 Hz), vocal chant presence (2-5 kHz), synth pad warmth (200-500 Hz), kick definition (40-80 Hz)
**MCP command**: `master_audio(file, genre="afro-house")`

**Characteristics**:
- Layered African percussion creates polyrhythmic complexity; preserve transient clarity and rhythmic interplay
- Bass is warm and groovy; supports the dance groove without overwhelming the percussion
- Black Coffee/Culoe De Song-style: deeper, more minimal; festival Afro-house: more energetic, bigger builds
- Vocal chants and melodic elements add African musical identity; keep them prominent and warm
- The genre's organic feel sets it apart from mainstream house; do not over-process
- A warm, spacious master preserves the genre's cultural and rhythmic richness

### Deep Techno
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the hypnotic, immersive quality and subtle textural details; deep techno's power comes from repetition and micro-variation
**EQ focus**: Kick definition (40-80 Hz), dub-influenced bass (60-150 Hz), pad atmosphere (200-600 Hz), hi-hat detail (8-12 kHz), textural detail (1-6 kHz)
**MCP command**: `master_audio(file, genre="deep-techno")`

**Characteristics**:
- Hypnotic, repetitive structures build intensity through subtle variation; preserve the gradual evolution
- Dub influences mean reverb and delay are compositional; do not collapse the spatial depth
- Ben Klock/Marcel Dettmann-style: harder, more driving; deepchord-style: more ambient, dub-influenced
- Kick drum provides the rhythmic anchor; tight and defined but not aggressive
- Sub-bass and bass occupy distinct roles; careful separation preserves the depth
- The genre rewards restraint in mastering; over-processing destroys the hypnotic quality

### Brostep
**LUFS target**: -14 LUFS
**Dynamics**: Heavy compression; aggressive, bass-heavy dubstep variant designed for maximum impact; the drops must hit hard
**EQ focus**: Mid-range bass wobble and growl (100-500 Hz), sub-bass weight (30-60 Hz), vocal/synth clarity (2-5 kHz), kick punch (60-100 Hz), high-mid cut for bass harshness
**MCP command**: `master_audio(file, genre="brostep")`

**Characteristics**:
- The bass drop is the genre's defining moment; massive, aggressive, and physically felt
- Mid-range bass design (wobbles, growls, screeches) occupies 100-500 Hz; preserve their aggressive character
- Skrillex/Excision-style: maximum aggression, complex bass design; the genre expects loudness
- Builds and drops create extreme dynamic contrast; the drop must feel like an event
- Vocal chops and synths in the build need presence; they set up the drop's impact
- A loud, aggressive master is appropriate; the genre rewards impact over subtlety

### Post-Dubstep
**LUFS target**: -16 LUFS
**Dynamics**: Light-to-moderate compression; preserve the atmospheric, spacious production and subtle bass work; post-dubstep is about texture and mood, not aggression
**EQ focus**: Sub-bass warmth (30-80 Hz), vocal processing detail (2-5 kHz), synth texture (200-600 Hz), percussion detail (4-8 kHz), high-frequency air
**MCP command**: `master_audio(file, genre="post-dubstep")`

**Characteristics**:
- Spacious, atmospheric production with restrained bass; not aggressive or drop-focused
- Vocal processing (pitch-shifting, chopping, reverb) is compositional; preserve the artistic intent
- James Blake/Mount Kimbie-style: more vocal, intimate; Burial-style: darker, more textured
- Sub-bass is present but warm and round; not aggressive or wobbling
- Garage and 2-step rhythm influences create subtle swing; preserve the rhythmic nuance
- The genre rewards a spacious, detailed master that preserves atmospheric depth

### Post-Disco
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the sophisticated groove and dynamic dancefloor energy; polished but funky
**EQ focus**: Bass groove (60-150 Hz), synth clarity (200-600 Hz), vocal warmth (2-5 kHz), hi-hat crispness (8-12 kHz), string/horn lushness (200-600 Hz)
**MCP command**: `master_audio(file, genre="post-disco")`

**Characteristics**:
- Bass is groovy, melodic, and driving; the foundation of the dance groove
- Synthesizer and production sophistication distinguish post-disco from classic disco; preserve the layered production
- Chic/Nile Rodgers-style: guitar-driven groove; Arthur Russell-style: more experimental, atmospheric
- Strings and horns add sophistication; keep them lush but not competing with the rhythm section
- Drum production is tighter and more produced than classic disco; punchy and defined
- The genre bridges disco's energy with electronic production sophistication; balance both

### Space Disco
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the cosmic, atmospheric quality and hypnotic groove; space disco's dreamy character needs sonic room
**EQ focus**: Synth pad warmth (200-600 Hz), bass groove (60-150 Hz), cosmic effects preservation, vocal processing detail (2-5 kHz), sparkle (8-12 kHz)
**MCP command**: `master_audio(file, genre="space-disco")`

**Characteristics**:
- Cosmic synth textures and spacey effects define the genre; preserve their ethereal character
- Bass is groovy but not aggressive; warm and hypnotic
- Giorgio Moroder/Cerrone-style: more driving, sequencer-based; Lindstrom-style: more spaced-out, atmospheric
- Reverb and delay create the cosmic atmosphere; over-compression collapses the spaciousness
- Vocal elements (when present) are often processed and distant; part of the atmosphere
- The genre rewards a warm, spacious master that preserves the cosmic journey

### Rave
**LUFS target**: -12 LUFS
**Dynamics**: Heavy compression; aggressive, high-energy production designed for massive sound systems; the genre demands loudness and physical impact
**EQ focus**: Kick punch (40-80 Hz), synth stab energy (1-4 kHz), vocal/MC sample presence (2-5 kHz), hi-hat and breakbeat energy (6-12 kHz), sub-bass weight (30-60 Hz)
**MCP command**: `master_audio(file, genre="rave")`

**Characteristics**:
- Breakbeats, piano stabs, and vocal samples define the classic rave sound; all need energy and presence
- Bass must be heavy and physically felt; massive sub-bass for large sound systems
- The Prodigy/SL2-style: aggressive, breakbeat-driven; piano house rave: euphoric, more melodic
- Hoover synths and rave stabs are signature sounds; preserve their aggressive, cutting quality
- The genre expects maximum energy and loudness; push to -12 LUFS or louder
- Dynamic restraint is not the goal; controlled aggression with clear transients

### UK Funky
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the syncopated groove and percussive detail; the genre's rhythmic complexity defines it
**EQ focus**: Percussion clarity (3-8 kHz), bass warmth (60-150 Hz), vocal chop presence (2-5 kHz), conga/drum detail (3-6 kHz), kick definition (40-80 Hz)
**MCP command**: `master_audio(file, genre="uk-funky")`

**Characteristics**:
- Syncopated, conga-driven rhythms define the genre; preserve the polyrhythmic detail
- Bass is warm and bouncy; supports the dance groove without overwhelming percussion
- Roska/Crazy Cousinz-style: more bass-heavy; vocal UK funky: more R&B-influenced
- Vocal chops and samples add melodic hooks; crisp and present
- The genre blends UK garage, house, and Afro-Caribbean rhythms; preserve the fusion character
- A punchy, groove-forward master that maintains rhythmic clarity

### Vocal House
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the vocal performance dynamics alongside the four-on-the-floor groove; vocals are the genre's emotional center
**EQ focus**: Vocal clarity and warmth (2-5 kHz), kick punch (40-80 Hz), bass groove (60-150 Hz), pad warmth (200-500 Hz), hi-hat crispness (8-12 kHz)
**MCP command**: `master_audio(file, genre="vocal-house")`

**Characteristics**:
- Diva vocals are the genre's centerpiece; powerful, clear, and emotionally delivered
- Four-on-the-floor kick must be punchy and driving; the dance-floor foundation
- Bass is warm and groovy; supports the vocal without competing
- Synth pads and strings add emotional depth; lush but behind the vocal
- Classic vocal house (Frankie Knuckles, Larry Levan): warmer, more soulful; modern: cleaner, more produced
- The genre demands a polished master that serves the vocal while maintaining dancefloor energy

### Dark Electro
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; aggressive, dark production with industrial influences; the genre demands weight and menace
**EQ focus**: Distorted synth bass (60-200 Hz), harsh mid-range textures (800 Hz-3 kHz), vocal processing (2-5 kHz), kick impact (40-80 Hz), high-mid cut for harshness management
**MCP command**: `master_audio(file, genre="dark-electro")`

**Characteristics**:
- Dark, aggressive synth textures define the genre; distortion and harshness are intentional
- Bass is heavy, often distorted; menacing and physically felt
- Combichrist/Hocico-style: more aggressive, industrial; softer variants: more atmospheric, EBM-influenced
- Vocals are processed, often distorted or vocoded; preserve the production intent
- Industrial noise elements are compositional; do not clean them up
- A dark, heavy master suits the genre's aggressive character; brightness is unwelcome

### Cyberpunk
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the futuristic, dystopian atmosphere; the genre blends electronic production with industrial edge
**EQ focus**: Synth clarity and edge (1-4 kHz), bass weight (40-100 Hz), glitch/noise detail (3-8 kHz), vocal processing (2-5 kHz), atmospheric depth
**MCP command**: `master_audio(file, genre="cyberpunk")`

**Characteristics**:
- Futuristic, dystopian sound design is the genre's identity; preserve the sci-fi atmosphere
- Bass is heavy and synthetic; often dark and aggressive
- Perturbator-style: more synthwave-influenced; industrial cyberpunk: harsher, noisier
- Glitch effects and digital noise are compositional; do not treat them as problems
- Atmospheric depth and spatial effects create the dystopian world; preserve the immersion
- A polished but edgy master suits the genre's futuristic aesthetic

### Gqom
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the raw, minimal, bass-heavy groove; gqom's power comes from stripped-back intensity
**EQ focus**: Bass weight (40-100 Hz), kick punch (40-80 Hz), percussion rawness (3-8 kHz), vocal chant presence (2-5 kHz), minimal synth elements
**MCP command**: `master_audio(file, genre="gqom")`

**Characteristics**:
- Minimal, repetitive production with heavy bass and raw percussion; the stripped-back quality is intentional
- Bass is heavy, dark, and driving; the foundation of the entire track
- DJ Lag/Naked Boyz-style: more minimal, rawer; the genre resists polish
- Vocal chants and samples are sparse but important; crisp and present
- Lo-fi production quality is a feature; do not over-process or clean up
- The genre rewards a raw, bass-heavy master that preserves its Durban street-party energy

### Benga
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the guitar-driven rhythmic groove and vocal harmonies; the genre's bounce and swing are essential
**EQ focus**: Guitar clarity (800 Hz-3 kHz), bass warmth (80-200 Hz), vocal harmony presence (2-5 kHz), percussion detail (4-8 kHz)
**MCP command**: `master_audio(file, genre="benga")`

**Characteristics**:
- Interlocking guitar patterns define the genre's rhythmic identity; preserve their clarity and bounce
- Vocal harmonies add melodic richness; keep them warm and full
- Bass guitar provides the rhythmic and harmonic foundation; warm and defined
- Percussion (including traditional Kenyan drums) drives the rhythm; transient clarity matters
- The genre has a warm, live-band character; preserve the natural feel
- A warm, punchy master suits benga's dance-oriented energy

### Dembow
**LUFS target**: -12 LUFS
**Dynamics**: Heavy compression; aggressive, bass-heavy production designed for maximum dancefloor impact; the genre demands loudness
**EQ focus**: Bass weight (40-80 Hz), kick punch (60-100 Hz), vocal presence (2-5 kHz), hi-hat crispness (8-12 kHz), synth energy (1-4 kHz)
**MCP command**: `master_audio(file, genre="dembow")`

**Characteristics**:
- The dembow rhythm pattern drives everything; punchy, aggressive, and relentless
- Bass is heavy, physically felt; sub-bass is essential to the genre's impact
- El Alfa-style: maximum energy, aggressive; the genre expects loudness
- Vocals are energetic and rhythmically precise; clear above the heavy production
- Synth and sample elements add melodic hooks; present and cutting
- Push to -12 LUFS or louder for maximum dancefloor impact

### Guaracha
**LUFS target**: -12 LUFS
**Dynamics**: Heavy compression; high-energy, festival-ready electronic Latin music; the genre demands maximum impact
**EQ focus**: Kick punch (40-80 Hz), bass weight (60-150 Hz), tribal percussion energy (3-8 kHz), synth lead clarity (1-4 kHz), vocal sample presence
**MCP command**: `master_audio(file, genre="guaracha")`

**Characteristics**:
- Tribal percussion patterns create the driving energy; punchy and relentless
- Bass is heavy and physically felt; the foundation of the festival experience
- Builds and drops are extreme; preserve the dynamic contrast for maximum impact
- Synth leads and effects add melodic hooks; cutting and energetic
- The genre is designed for massive sound systems; push to -12 LUFS
- A loud, aggressive master suits the genre's festival-oriented energy

### Coupe-Decale
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the energetic, celebratory groove and rhythmic drive; polished and dancefloor-ready
**EQ focus**: Percussion crispness (4-8 kHz), bass groove (60-150 Hz), synth presence (200-600 Hz), vocal clarity (2-5 kHz), kick punch (40-80 Hz)
**MCP command**: `master_audio(file, genre="coupe-decale")`

**Characteristics**:
- Uptempo, celebratory electronic production with Ivorian rhythmic character; energy and groove are paramount
- Percussion is dense and driving; African rhythmic patterns with electronic production
- Bass is warm and bouncy; supports the dance groove
- Vocal chants and call-and-response add party energy; clear and present
- DJ Arafat-style: more aggressive, bass-heavy; lighter variants: more melodic, pop-influenced
- A polished, energetic master suits the genre's celebratory character

### Kuduro
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the raw, high-energy rhythmic drive; kuduro's frenetic percussion patterns must remain articulate
**EQ focus**: Percussion energy (3-8 kHz), bass punch (60-150 Hz), synth elements (200-600 Hz), vocal clarity (2-5 kHz), kick definition (40-80 Hz)
**MCP command**: `master_audio(file, genre="kuduro")`

**Characteristics**:
- Rapid, complex percussion patterns are the genre's identity; preserve their articulation and energy
- Bass is punchy and driving; supports the rhythmic intensity
- Buraka Som Sistema-style: more electronic, club-oriented; traditional kuduro: rawer, more street
- Vocal delivery is energetic and rhythmic; clear above the dense percussion
- The genre's Angolan street-party energy should translate through the master
- A punchy, energetic master that preserves rhythmic complexity

### Kwaito
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the laid-back, bass-heavy groove; kwaito's slow, deep bounce is its defining character
**EQ focus**: Bass depth (40-100 Hz), vocal presence (2-5 kHz), percussion warmth (3-6 kHz), synth pad atmosphere (200-500 Hz), kick softness (40-80 Hz)
**MCP command**: `master_audio(file, genre="kwaito")`

**Characteristics**:
- Slow, deep groove (90-110 BPM) with heavy bass; the genre's laid-back bounce is essential
- Bass is deep and warm; not aggressive but physically present
- Vocal delivery is often spoken or chanted; clear and rhythmically placed
- Arthur Mafokate/Mandoza-style: more energetic; mellow kwaito: deeper, more atmospheric
- Synth pads create atmospheric depth; warm and supportive
- A warm, bass-heavy master preserves kwaito's South African street-music character

### Gengetone
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; raw, energetic Kenyan electronic music; bass-heavy and rhythmically driven
**EQ focus**: Bass weight (40-100 Hz), vocal presence (2-5 kHz), percussion energy (3-8 kHz), synth hooks (1-4 kHz), kick punch (40-80 Hz)
**MCP command**: `master_audio(file, genre="gengetone")`

**Characteristics**:
- Raw, bass-heavy production with energetic rhythms; the street-music character is intentional
- Bass is heavy and punchy; the genre's physical foundation
- Vocal delivery is energetic, often in Sheng; clear and present above the beat
- Ethic Entertainment/Sailors-style: raw, party-oriented; the genre resists over-polish
- Dancehall and hip-hop influences blend with Kenyan musical identity
- A punchy, bass-forward master preserves the genre's raw street energy

### Dangdut
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the tabla/gendang groove and vocal ornamentations; Indonesian pop-dance energy with traditional character
**EQ focus**: Vocal presence (1-4 kHz), tabla/gendang clarity (3-6 kHz), bass groove (60-150 Hz), keyboard/organ warmth (200-600 Hz), suling (flute) clarity (2-6 kHz)
**MCP command**: `master_audio(file, genre="dangdut")`

**Characteristics**:
- Tabla/gendang rhythms define the genre's groove; preserve their transient clarity and bounce
- Melismatic vocal ornamentation needs headroom; over-compression flattens the delivery
- Rhoma Irama-style classic: more traditional, guitar-forward; koplo/modern: more electronic, faster
- Suling (bamboo flute) adds melodic color; preserve its breathy, warm character
- Bass is groovy and driving; the foundation of the dance rhythm
- A warm, punchy master preserves dangdut's unique blend of Indian, Malay, and Western elements

### Drone
**LUFS target**: -18 LUFS
**Dynamics**: Minimal compression; preserve the sustained, slowly evolving tones and extreme dynamic range; drone music's power is in sustained immersion
**EQ focus**: Full-spectrum frequency content, harmonic overtone preservation, minimal EQ intervention, low-end body (20-200 Hz)
**MCP command**: `master_audio(file, genre="drone")`

**Characteristics**:
- Sustained tones that evolve over extended durations; patience in mastering is essential
- Harmonic overtones and beating frequencies are compositional elements; preserve their detail
- La Monte Young-style: more minimal, pure; drone ambient: more textural, layered
- Extremely wide dynamic range possible; protect quiet passages and sustained crescendos
- Feedback and acoustic phenomena are intentional; do not process them away
- The genre demands the most minimal mastering approach possible; intervention destroys the intent

### Psybient
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the spacious, psychedelic atmosphere and organic textures; the genre creates immersive sonic worlds
**EQ focus**: Synth texture detail (200 Hz-4 kHz), bass warmth (40-100 Hz), nature sound clarity (2-8 kHz), high-frequency shimmer, spatial effects preservation
**MCP command**: `master_audio(file, genre="psybient")`

**Characteristics**:
- Psychedelic textures and ambient atmospheres create immersive soundscapes; preserve their depth
- Bass is warm, round, and enveloping; not aggressive or punchy
- Shpongle/Ott-style: more rhythmic, world-music-influenced; pure psybient: more ambient, less structured
- Nature sounds and field recordings are compositional elements; preserve their natural character
- The genre is designed for deep listening; the master should feel spacious and immersive
- Over-processing destroys the psychedelic depth; minimal intervention is best

### Dungeon Synth
**LUFS target**: -18 LUFS
**Dynamics**: Minimal compression; preserve the lo-fi, atmospheric quality; the genre's medieval fantasy aesthetic depends on raw, unpolished character
**EQ focus**: Synth pad warmth (200-600 Hz), low-end atmosphere (40-200 Hz), high-frequency rolloff for vintage character, tape hiss preservation
**MCP command**: `master_audio(file, genre="dungeon-synth")`

**Characteristics**:
- Lo-fi production is intentional; tape hiss, noise, and roughness are features, not flaws
- Synth textures should be warm and vintage-sounding; do not brighten or modernize
- Mortiis/Burzum-style: more raw, minimal; modern dungeon synth: slightly more produced but still lo-fi
- Medieval and fantasy atmosphere is the goal; the master should feel ancient and mysterious
- Very wide dynamics; quiet passages and crescendos are compositional
- The genre rejects modern production values; minimal mastering preserves the aesthetic

### Electroacoustic
**LUFS target**: -18 LUFS
**Dynamics**: Minimal compression; preserve the full dynamic range of acoustic and electronic sound sources; the genre treats dynamics as a compositional element
**EQ focus**: Full-spectrum detail preservation, acoustic source clarity, electronic texture definition, minimal intervention
**MCP command**: `master_audio(file, genre="electroacoustic")`

**Characteristics**:
- Acoustic sounds are transformed through electronic processing; preserve both the source and the transformation
- Dynamic range can be extreme; protect the full range from silence to loud
- Pierre Schaeffer/Luc Ferrari-style: more musique concrete; modern: more digital, varied
- Every sound is carefully composed and placed; broad EQ moves can destroy the intent
- Spatial placement (panning, depth) is often compositional; preserve the stereo image
- The genre demands the most detail-oriented mastering; less is always more

### Lounge
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the relaxed, sophisticated atmosphere; lounge music is designed for background listening comfort
**EQ focus**: Vocal warmth (2-4 kHz), jazz instrument clarity (200 Hz-4 kHz), bass smoothness (60-150 Hz), gentle high-frequency air, cocktail-bar ambience
**MCP command**: `master_audio(file, genre="lounge")`

**Characteristics**:
- The atmosphere is relaxed, sophisticated, and intimate; over-processing destroys the mood
- Vocals (when present) are smooth and warm; never harsh or bright
- Jazz-influenced instrumentation needs natural presence; warm and inviting
- Bass is smooth and unobtrusive; supportive, not prominent
- Esquivel-style: more quirky, retro; modern lounge: smoother, more ambient
- The genre rewards a warm, effortless-sounding master; the music should feel like a warm bath

### Celtic
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the natural dynamics of acoustic instruments and vocal traditions; the genre's warmth comes from organic character
**EQ focus**: Fiddle/tin whistle clarity (2-6 kHz), bodhran warmth (200-500 Hz), acoustic guitar body (200-600 Hz), vocal presence (2-5 kHz), pipe/uilleann pipe richness (800 Hz-4 kHz)
**MCP command**: `master_audio(file, genre="celtic")`

**Characteristics**:
- Acoustic instruments (fiddle, tin whistle, uilleann pipes, bodhran) define the sound; preserve their natural character
- Vocals range from unaccompanied sean-nos to full-band Celtic rock; adapt dynamics accordingly
- Chieftains-style: more traditional, wider dynamics; Celtic Woman-style: more produced, polished
- Bodhran and percussion provide rhythmic drive; warm and resonant
- The genre favors a warm, natural master; acoustic authenticity is paramount
- Pub session energy (when appropriate) should feel live and communal

### Singer-Songwriter
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the intimate, personal dynamics; the genre's emotional power depends on vulnerability and dynamic nuance
**EQ focus**: Vocal intimacy (2-4 kHz), acoustic guitar body (200-600 Hz), piano warmth (200-500 Hz), sibilance control (6-8 kHz), gentle high-frequency air
**MCP command**: `master_audio(file, genre="singer-songwriter")`

**Characteristics**:
- The voice is the absolute center; intimate, personal, and emotionally transparent
- Sparse arrangements expose every sonic detail; careful mastering is essential
- Acoustic guitar and/or piano are the primary accompaniment; warm and supportive
- Joni Mitchell/Nick Drake-style: spare, acoustic; more produced variants: fuller, but voice still forward
- Sibilance control is important in sparse mixes where harshness is easily noticed
- The genre rewards minimal mastering; over-processing removes the personal intimacy

### Polka
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the lively, bouncy dance energy; the genre's rhythmic drive must remain infectious
**EQ focus**: Accordion brightness (800 Hz-3 kHz), tuba/bass definition (60-150 Hz), vocal clarity (2-5 kHz), drums and percussion punch (3-6 kHz), clarinet/trumpet clarity (1-4 kHz)
**MCP command**: `master_audio(file, genre="polka")`

**Characteristics**:
- Accordion is the genre's signature instrument; bright, present, and energetic
- The oom-pah rhythm (bass on beat 1, chord on beat 2) must be bouncy and driving
- Frankie Yankovic-style: more polished, orchestral; Brave Combo-style: quirkier, more eclectic
- Tuba or bass provides the rhythmic foundation; punchy and defined
- Vocals are clear and singable; the genre is communal music
- A warm, lively master preserves the genre's party energy

### Norteno
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the accordion-driven groove and bajo sexto character; the genre demands warmth and rhythmic clarity
**EQ focus**: Accordion presence (800 Hz-3 kHz), bajo sexto body (200-600 Hz), bass definition (60-150 Hz), vocal warmth (2-5 kHz), percussion detail (3-6 kHz)
**MCP command**: `master_audio(file, genre="norteno")`

**Characteristics**:
- Accordion and bajo sexto (twelve-string guitar) are the core instruments; both need clear presence
- Vocals are warm and powerful; corrido-style narrative delivery needs intelligibility
- Los Tigres del Norte-style: more polished, narrative; conjunto: more stripped-down, accordion-forward
- Bass provides the rhythmic foundation; warm and steady
- The genre has a warm, live-band character; preserve the communal feel
- A warm, punchy master suits norteno's working-class musical identity

### Bebop
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the full dynamic range of virtuosic improvisation; bebop's explosive energy depends on dynamic freedom
**EQ focus**: Horn clarity (1-4 kHz), piano comping warmth (200-600 Hz), bass walk (80-200 Hz), drum brush/ride detail (6-12 kHz), minimal EQ intervention
**MCP command**: `master_audio(file, genre="bebop")`

**Characteristics**:
- Virtuosic improvisation is the genre's core; every note in a rapid-fire solo must be clear
- Dynamic range from whispered phrases to explosive runs must be preserved
- Charlie Parker/Dizzy Gillespie-style: faster, more explosive; later bebop: more refined
- Piano comping provides harmonic support; warm and responsive
- Walking bass is the rhythmic anchor; clear, defined, and melodic
- The genre demands natural, transparent mastering; processing removes the live energy

### Cool Jazz
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the relaxed, understated dynamics; cool jazz's restraint and subtlety depend on wide dynamic range
**EQ focus**: Horn warmth (1-4 kHz), piano clarity (200-600 Hz), bass smoothness (80-200 Hz), brush and cymbal detail (6-12 kHz), gentle high-frequency air
**MCP command**: `master_audio(file, genre="cool-jazz")`

**Characteristics**:
- Understated, relaxed playing style; dynamics are subtle and refined
- Horn tones (especially trumpet and sax) are warm and breathy; preserve their intimate character
- Miles Davis/Chet Baker-style: intimate, sparse; Dave Brubeck-style: more rhythmic, accessible
- Piano and vibraphone provide cool harmonic color; warm without muddiness
- The genre favors a transparent, natural master; over-processing adds unwanted energy
- Space and silence are musical elements; protect them

### Hard Bop
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the soulful, rhythmic dynamics; hard bop brings blues and gospel feeling to jazz's harmonic complexity
**EQ focus**: Horn fire and warmth (1-4 kHz), piano gospel-influenced voicings (200-600 Hz), bass groove (80-200 Hz), drum swing and drive (3-8 kHz)
**MCP command**: `master_audio(file, genre="hard-bop")`

**Characteristics**:
- More rhythmic drive and soul than bebop; blues and gospel influences add emotional warmth
- Horn playing is passionate and soulful; preserve the fire and expressiveness
- Art Blakey-style: more driving, drum-forward; Horace Silver-style: funkier, more groove-oriented
- Piano comping is more bluesy and gospel-influenced; warm and soulful
- Walking bass is melodic and groovy; warm and defined
- The genre demands a warm, natural master that preserves the soulful energy

### Modal Jazz
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the spacious, meditative quality; modal jazz's open harmonic approach creates wide sonic landscapes
**EQ focus**: Horn tone clarity (1-4 kHz), piano space (200-600 Hz), bass depth (80-200 Hz), cymbal shimmer (8-12 kHz), room and atmosphere
**MCP command**: `master_audio(file, genre="modal-jazz")`

**Characteristics**:
- Spacious, open harmonic landscapes; the modal approach creates room for exploration
- Dynamic range from quiet meditation to passionate crescendo; protect the full range
- Miles Davis *Kind of Blue*-style: intimate, spacious; Coltrane-style: more intense, searching
- Piano voicings are open and resonant; let them breathe and sustain
- Bass and drums create a gentle rhythmic bed; supportive but not driving
- The genre rewards a transparent, spacious master; let the space speak

### Jazz Fusion
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the technical virtuosity and dynamic range while managing the louder, more electric character
**EQ focus**: Electric guitar/synth clarity (800 Hz-4 kHz), bass groove (60-200 Hz), keyboard layers (200-600 Hz), drum precision (3-6 kHz), horn presence (1-4 kHz)
**MCP command**: `master_audio(file, genre="jazz-fusion")`

**Characteristics**:
- Technical virtuosity requires clarity across all instruments; each player needs space
- Electric instruments are louder and more aggressive than acoustic jazz; adapt dynamics accordingly
- Weather Report/Herbie Hancock-style: more electronic, synth-forward; Mahavishnu Orchestra-style: more rock, aggressive
- Bass (electric or fretless) is often virtuosic and prominent; clear and articulate
- The genre bridges jazz complexity with rock/electronic energy; balance sophistication with impact
- A polished, dynamic master that preserves technical detail

### Smooth Jazz
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; polished, radio-ready production; the genre demands accessible, easy-listening clarity
**EQ focus**: Saxophone warmth and sweetness (800 Hz-4 kHz), keyboard smoothness (200-600 Hz), bass groove (60-150 Hz), drum precision (3-6 kHz), vocal warmth (2-5 kHz)
**MCP command**: `master_audio(file, genre="smooth-jazz")`

**Characteristics**:
- Saxophone is the melodic centerpiece; warm, sweet, and smooth without harshness
- Production is polished and radio-ready; the genre rewards clean, accessible mastering
- Kenny G-style: sweeter, more pop; Grover Washington Jr.-style: funkier, more groove-oriented
- Bass and drums provide the smooth groove; polished and defined
- Keyboards add harmonic sweetness; warm and supportive
- The genre is designed for easy listening; a warm, polished master is appropriate

### Nu-Jazz
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the blend of live jazz elements with electronic production; the genre bridges acoustic warmth and electronic precision
**EQ focus**: Horn/instrument clarity (1-4 kHz), electronic bass definition (40-100 Hz), beat precision (3-8 kHz), synth texture (200-600 Hz), vocal sample presence (2-5 kHz)
**MCP command**: `master_audio(file, genre="nu-jazz")`

**Characteristics**:
- Live jazz instruments coexist with electronic beats and production; balance both worlds
- Bass can be acoustic or electronic; keep it warm and groovy either way
- Jazzanova/St Germain-style: more lounge, electronic; The Cinematic Orchestra-style: more cinematic, orchestral
- Beat programming adds rhythmic precision; it should complement, not replace, the jazz feel
- The genre rewards a polished master that honors both the jazz warmth and electronic clarity
- A modern, warm production aesthetic is appropriate

### Gypsy Jazz
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the virtuosic acoustic guitar dynamics and natural room sound; the genre's fire comes from dynamic expression
**EQ focus**: Guitar attack and warmth (200 Hz-4 kHz), bass definition (80-200 Hz), violin clarity (2-6 kHz), accordion warmth (800 Hz-3 kHz), room ambience
**MCP command**: `master_audio(file, genre="gypsy-jazz")`

**Characteristics**:
- Acoustic guitar is the centerpiece; rapid-fire soloing and rhythmic La Pompe strumming both need clarity
- Django Reinhardt's legacy defines the genre; preserve the virtuosic fire and swing
- Violin adds melodic color; bright and present without harshness
- Rhythm guitar (La Pompe) provides the driving swing; percussive attack clarity essential
- Bass (acoustic) provides the harmonic and rhythmic foundation; warm and steady
- A natural, acoustic-sounding master preserves the genre's intimate cafe-concert atmosphere

### Ethio-Jazz
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the blend of Ethiopian pentatonic melodies with jazz harmony and funk groove; the genre's unique character depends on this fusion
**EQ focus**: Horn and keyboard clarity (1-4 kHz), bass groove (60-200 Hz), percussion detail (3-8 kHz), vocal presence (2-5 kHz), organ/piano warmth (200-600 Hz)
**MCP command**: `master_audio(file, genre="ethio-jazz")`

**Characteristics**:
- Ethiopian pentatonic scales give the genre its distinctive melodic character; preserve the modal beauty
- Horn arrangements (saxophone, trumpet) carry the melody; warm and clear
- Mulatu Astatke-style: more laid-back, groovier; modern Ethio-jazz: more energetic, fuller arrangements
- Organ and electric piano provide harmonic warmth; vintage character preferred
- Bass is funky and driving; keeps the groove moving
- A warm, groove-oriented master preserves the genre's unique Ethiopian-jazz fusion

### Dark Jazz
**LUFS target**: -18 LUFS
**Dynamics**: Minimal compression; preserve the dark, atmospheric quality and extremely wide dynamics; the genre creates nocturnal, cinematic soundscapes
**EQ focus**: Saxophone and horn warmth (800 Hz-3 kHz), bass depth (40-150 Hz), ambient texture detail, reverb and delay preservation, minimal EQ intervention
**MCP command**: `master_audio(file, genre="dark-jazz")`

**Characteristics**:
- Dark, slow, atmospheric jazz with cinematic quality; the genre creates mood, not rhythm
- Saxophones and horns are muted, reverb-heavy, and distant; preserve their nocturnal character
- Bohren & der Club of Gore-style: glacially slow, minimal; The Kilimanjaro Darkjazz Ensemble: more layered, cinematic
- Bass is deep and sustained; warm and enveloping
- Reverb and atmospheric effects are essential to the mood; over-compression destroys the noir atmosphere
- The genre demands patient, minimal mastering; preserve the darkness and space

### Latin Jazz
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the polyrhythmic percussion interplay and dynamic swing; Latin jazz's energy comes from rhythmic complexity
**EQ focus**: Horn brightness (1-4 kHz), piano montuno clarity (200-600 Hz), bass tumbao definition (80-200 Hz), percussion detail (3-8 kHz), conga/timbales warmth
**MCP command**: `master_audio(file, genre="latin-jazz")`

**Characteristics**:
- Polyrhythmic percussion (congas, timbales, bongos) is the rhythmic foundation; preserve the layered complexity
- Clave-based rhythms must remain clear; the clave pattern anchors everything
- Tito Puente/Cal Tjader-style: more swing, vibraphone-forward; Eddie Palmieri-style: more experimental, piano-forward
- Horn sections carry the melodic energy; bright and punchy without harshness
- Bass (tumbao patterns) is both rhythmic and melodic; warm and defined
- The genre rewards a warm, punchy master that preserves rhythmic vitality

### Vocal Jazz
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the vocal dynamics and interpretive nuance; the singer's phrasing and expression are paramount
**EQ focus**: Vocal warmth and presence (1-4 kHz), piano/guitar accompaniment body (200-600 Hz), bass smoothness (80-200 Hz), brush/cymbal detail (6-12 kHz), sibilance control
**MCP command**: `master_audio(file, genre="vocal-jazz")`

**Characteristics**:
- The voice is the absolute center; every nuance of phrasing, dynamics, and interpretation must be preserved
- Ella Fitzgerald/Sarah Vaughan-style: more powerful, wider dynamics; Diana Krall-style: more intimate, modern
- Accompaniment (piano trio, guitar, strings) is supportive; warm and responsive
- Sibilance control is critical in the intimate vocal setting; harshness is immediately noticeable
- Room and venue atmosphere contribute to the listening experience; preserve natural ambience
- The genre demands transparent mastering that serves the vocal performance

### Soul Jazz
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the groovy, soulful dynamics; the genre brings R&B and gospel feeling to jazz instrumentation
**EQ focus**: Organ warmth (200-600 Hz), tenor sax soul (800 Hz-3 kHz), bass groove (60-150 Hz), drum swing (3-6 kHz), guitar funk (800 Hz-2 kHz)
**MCP command**: `master_audio(file, genre="soul-jazz")`

**Characteristics**:
- Hammond B3 organ is the genre's signature sound; warm, full, and groovy with Leslie speaker character
- Tenor saxophone plays soulful, bluesy melodies; warm and expressive
- Jimmy Smith/Grant Green-style: more groove-oriented; Lee Morgan-style: harder-driving, more bop-influenced
- Bass is funky and walking; warm and defined, locked to the groove
- Drums swing with soul; snare backbeat and ride cymbal drive the feel
- A warm, groove-forward master preserves the genre's soulful energy

### Big Band
**LUFS target**: -16 LUFS
**Dynamics**: Moderate compression; preserve the wide dynamics of full orchestral-scale jazz ensemble; from whispered brass to full-blast shout chorus
**EQ focus**: Brass section brightness (1-4 kHz), saxophone warmth (800 Hz-3 kHz), rhythm section definition (80-200 Hz), drum swing (3-6 kHz), piano comping (200-600 Hz)
**MCP command**: `master_audio(file, genre="big-band")`

**Characteristics**:
- Full brass and saxophone sections create dense harmonic content; careful frequency management essential
- Dynamic range from quiet background swing to full-blast shout chorus must be preserved
- Count Basie-style: more relaxed, swinging; Stan Kenton-style: more modern, aggressive
- Rhythm section (piano, bass, drums, guitar) anchors the ensemble; tight and swinging
- Solo instruments must cut through the section; preserve their clarity during solo passages
- The genre rewards a natural, wide-dynamic master that preserves the big-band experience

### Delta Blues
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the raw, acoustic intimacy and dynamic expression; the genre's emotional power comes from unprocessed directness
**EQ focus**: Vocal presence and rawness (1-4 kHz), acoustic guitar body and slide tone (200 Hz-3 kHz), minimal EQ intervention, room sound preservation
**MCP command**: `master_audio(file, genre="delta-blues")`

**Characteristics**:
- Raw, acoustic performance is the genre's identity; preserve the unvarnished character
- Vocal delivery is emotionally intense and dynamically free; do not compress the passion
- Robert Johnson/Son House-style: solo performer, intimate; fuller arrangements: slightly more produced
- Acoustic guitar (often slide) provides both harmony and rhythm; warm and resonant
- Lo-fi quality and room sound are features; do not clean up or brighten
- The genre demands the most minimal mastering approach; authenticity over polish

### Piano Blues
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the dynamic range of the piano performance; the genre's emotion lives in the touch and dynamics
**EQ focus**: Piano body and warmth (200-600 Hz), piano brightness (2-4 kHz), vocal presence (2-5 kHz), bass definition (80-200 Hz), room ambience
**MCP command**: `master_audio(file, genre="piano-blues")`

**Characteristics**:
- Piano is the lead instrument; its full dynamic range from delicate to thundering must be preserved
- Vocal delivery is raw and emotionally direct; clear and present alongside the piano
- Otis Spann/Professor Longhair-style: more acoustic, rawer; modern: slightly more polished
- Left-hand bass patterns and right-hand melodies both need clarity
- Room sound contributes to the atmosphere; preserve the natural space
- A warm, natural master preserves the genre's intimate, performance-focused character

### Desert Blues
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the hypnotic, repetitive guitar patterns and trance-like quality; the genre builds intensity through subtle rhythmic variation
**EQ focus**: Guitar clarity and twang (800 Hz-3 kHz), bass warmth (80-200 Hz), percussion detail (3-8 kHz), vocal presence (2-5 kHz), calabash/drum warmth
**MCP command**: `master_audio(file, genre="desert-blues")`

**Characteristics**:
- Hypnotic, repetitive guitar patterns are the genre's core; preserve their trance-like quality
- Guitar tones have a distinctive dry, desert character; preserve the bright, cutting attack
- Tinariwen/Ali Farka Toure-style: more traditional, acoustic-electric; Bombino-style: more rock-influenced
- Percussion (calabash, djembe, hand drums) provides the rhythmic foundation; warm and steady
- Vocals carry the melody and narrative; present and warm
- The genre's Saharan origin gives it a unique sonic character; preserve its desert spaciousness

### Gregorian Chant
**LUFS target**: -18 LUFS
**Dynamics**: Minimal compression; preserve the full dynamic range of the choral performance and cathedral acoustic; the reverb is the instrument
**EQ focus**: Vocal clarity (1-4 kHz), cathedral reverb preservation, minimal EQ intervention, low-end room resonance management
**MCP command**: `master_audio(file, genre="gregorian-chant")`

**Characteristics**:
- Unaccompanied vocal performance in reverberant space; the acoustic is part of the music
- Dynamic range from solo voice to full choir must be preserved completely
- Cathedral reverb and natural acoustics are essential; over-processing destroys the sacred atmosphere
- Low-frequency room resonances may need gentle management; but preserve the sense of vast space
- The genre demands the most transparent mastering possible; the music is ancient and should feel timeless
- Any processing artifacts are immediately noticeable in the exposed vocal texture

### Spaghetti Western
**LUFS target**: -16 LUFS
**Dynamics**: Light-to-moderate compression; preserve the cinematic dynamics from quiet tension to explosive action; the genre's dramatic storytelling depends on dynamic range
**EQ focus**: Guitar twang and harmonica clarity (1-4 kHz), orchestral warmth (200-600 Hz), percussion impact (3-6 kHz), vocal/whistle presence (2-6 kHz), reverb and space
**MCP command**: `master_audio(file, genre="spaghetti-western")`

**Characteristics**:
- Ennio Morricone's scores define the genre; electric guitar, harmonica, orchestra, and choir create the iconic sound
- Dramatic dynamic contrasts (tense quiet to explosive crescendo) are essential storytelling devices
- Guitar (often Fender-style twang) and harmonica carry the iconic melodies; bright and present
- Orchestral elements provide cinematic scale; warm and sweeping
- Reverb creates the vast, open landscape feeling; preserve the spaciousness
- A cinematic, wide-dynamic master preserves the genre's storytelling power

### Dark Cabaret
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the theatrical dynamics and dark, satirical character; the genre blends cabaret intimacy with punk/goth edge
**EQ focus**: Vocal theatricality and clarity (2-5 kHz), piano/accordion body (200-600 Hz), bass punch (80-200 Hz), percussion attack (3-6 kHz), dark atmosphere
**MCP command**: `master_audio(file, genre="dark-cabaret")`

**Characteristics**:
- Theatrical vocal delivery ranges from whispered to shouted; dynamic range matters for dramatic effect
- Dresden Dolls/Tiger Lillies-style: raw, punk-influenced; more polished dark cabaret: closer to goth rock
- Piano and/or accordion provide the harmonic foundation; percussive and present
- Bass adds weight and dark character; punchy and defined
- Dark, sometimes macabre atmosphere should carry through the master; do not brighten or lighten
- A punchy, dynamic master preserves the genre's theatrical intensity

### Dabke
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the driving dance rhythm and mijwiz/buzuq character; the genre demands energy and rhythmic clarity
**EQ focus**: Mijwiz/buzuq clarity (1-4 kHz), tablah definition (3-6 kHz), bass warmth (60-150 Hz), vocal presence (2-5 kHz), percussion energy (4-8 kHz)
**MCP command**: `master_audio(file, genre="dabke")`

**Characteristics**:
- Driving, stomping dance rhythm is the genre's identity; the pulse must be powerful and relentless
- Mijwiz (double-pipe reed) and buzuq (long-necked lute) carry the melody; bright and piercing
- Tablah and drum patterns drive the rhythm; punchy and defined transients
- Vocals are powerful and ornamented; clear above the dense rhythmic production
- The genre is communal dance music; the energy must translate for group participation
- A punchy, energetic master suits the genre's celebratory, dance-oriented character

### Shaabi
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the raw, street-level energy and vocal ornamentation; Egyptian working-class pop with character
**EQ focus**: Vocal presence and ornamentation (1-4 kHz), keyboard/organ body (200-600 Hz), tablah clarity (3-6 kHz), bass definition (60-150 Hz), percussion punch
**MCP command**: `master_audio(file, genre="shaabi")`

**Characteristics**:
- Raw, energetic vocal delivery with melismatic ornamentation; clear and present
- Keyboard-driven production with traditional percussion; warm and punchy
- Ahmed Adaweyah-style classic: rawer, more traditional; modern shaabi: more electronic, bass-heavy
- Tablah rhythms are complex and driving; transient clarity essential
- The genre has a street-party character; the master should preserve the raw energy
- Over-polishing removes the working-class authenticity that defines the genre

### Sufi
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the devotional dynamics and trance-inducing quality; the genre builds spiritual ecstasy through gradual dynamic growth
**EQ focus**: Vocal warmth and presence (1-4 kHz), harmonium/ney drone (200-600 Hz), frame drum definition (3-6 kHz), hand-clap rhythm, room acoustics
**MCP command**: `master_audio(file, genre="sufi")`

**Characteristics**:
- Devotional vocal delivery builds from quiet meditation to ecstatic crescendo; wide dynamics essential
- Repetitive melodic patterns create the trance-inducing quality; preserve the hypnotic groove
- Turkish Sufi (Mevlevi whirling): ney flute-centered, spacious; Pakistani Sufi: closer to qawwali
- Harmonium or ney flute provides the harmonic drone; warm and sustained
- Frame drum (bendir, daf) provides the rhythmic pulse; clear without being aggressive
- The sacred, spiritual quality demands minimal processing; preserve the devotional atmosphere

### Rebetiko
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the raw, emotional dynamics and bouzouki ornamentation; the genre's pain and passion depend on dynamic expression
**EQ focus**: Bouzouki clarity (2-6 kHz), vocal rawness and presence (1-4 kHz), baglamas shimmer (3-8 kHz), minimal bass, room acoustics
**MCP command**: `master_audio(file, genre="rebetiko")`

**Characteristics**:
- Bouzouki is the genre's voice; its metallic, ornamented tone needs clear, present treatment
- Vocals are raw, passionate, and ornamented; preserve the emotional directness
- Vasilis Tsitsanis/Markos Vamvakaris-style: historic, rawer; modern rebetiko revival: slightly more produced
- Acoustic character is paramount; the taverna atmosphere should carry through
- Very sparse arrangements (often just bouzouki and voice) expose every detail
- The genre demands minimal mastering; authenticity and emotional rawness are everything

### Turbo-Folk
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; polished, radio-ready production combining folk elements with pop-dance energy; the genre demands commercial impact
**EQ focus**: Vocal ornamentation presence (1-4 kHz), synth/keyboard brightness (200-600 Hz), bass punch (60-150 Hz), accordion clarity (800 Hz-3 kHz), drum machine punch
**MCP command**: `master_audio(file, genre="turbo-folk")`

**Characteristics**:
- Electronic dance production meets Balkan folk vocal style; both elements need presence
- Vocals are ornamented and powerful; clear and present above the electronic production
- Ceca/Seka-style: more polished, pop-forward; raw turbo-folk: more folk-influenced
- Synth and drum machine production should be punchy and radio-ready
- Accordion and folk instruments blend with electronic elements; balance traditional and modern
- A polished, commercial master suits the genre's pop-oriented aspirations

### Sevdah
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the intimate, melancholic dynamics; sevdah's emotional depth depends on dynamic vulnerability and silence
**EQ focus**: Vocal warmth and sorrow (1-4 kHz), saz/guitar body (200-600 Hz), accordion warmth (800 Hz-2 kHz), room acoustics, gentle high-frequency air
**MCP command**: `master_audio(file, genre="sevdah")`

**Characteristics**:
- Vocal delivery is intimate, sorrowful, and dynamically free; preserve every nuance
- Saz and acoustic guitar provide spare accompaniment; warm and resonant
- Amira Medunjanin-style modern: slightly more produced; traditional: rawer, more intimate
- The genre is Bosnian saudade; the emotional depth requires wide dynamics
- Sparse arrangements mean every sound is exposed; careful mastering essential
- Over-processing destroys the intimate, confessional quality; less is always more

### Manele
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; polished, radio-ready production with Oriental-influenced vocal ornamentation; the genre demands commercial punch
**EQ focus**: Vocal ornamentation presence (1-4 kHz), keyboard/synth brightness (200-600 Hz), bass punch (60-150 Hz), accordion clarity (800 Hz-3 kHz), percussion drive
**MCP command**: `master_audio(file, genre="manele")`

**Characteristics**:
- Melismatic vocal delivery with Turkish/Arabic-influenced ornamentation; headroom for ornamentation critical
- Electronic production with synthesizers and drum machines; polished and radio-ready
- Bass is punchy and prominent; drives the dance energy
- Keyboard arrangements provide the harmonic and melodic framework; bright and present
- The genre is Romanian party music; the energy must translate for dance
- A polished, punchy master suits the genre's commercial character

### Morna
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the intimate, melancholic dynamics; morna is Cape Verdean saudade; emotional vulnerability is paramount
**EQ focus**: Vocal warmth and sorrow (1-4 kHz), guitar/cavaquinho body (200-600 Hz), violin clarity (2-6 kHz), bass smoothness (80-200 Hz), room acoustics
**MCP command**: `master_audio(file, genre="morna")`

**Characteristics**:
- Vocal delivery is intimate, sorrowful, and beautiful; Cesaria Evora defined the modern sound
- Guitar and cavaquinho provide the harmonic bed; warm and gently strummed
- Violin adds melodic ornamentation; clear and expressive
- Bass is smooth and supportive; not prominent
- The genre is music of longing and separation; the emotional depth needs wide dynamics
- A warm, intimate master preserves morna's gentle, melancholic character

### Afropop
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; polished, modern production blending African musical elements with contemporary pop; radio-ready energy
**EQ focus**: Vocal clarity (2-5 kHz), guitar interlocking patterns (800 Hz-3 kHz), bass groove (60-150 Hz), percussion detail (4-8 kHz), synth/keyboard warmth (200-500 Hz)
**MCP command**: `master_audio(file, genre="afropop")`

**Characteristics**:
- Polished, modern production with diverse African musical roots; the genre spans the continent
- Vocals are clear, melodic, and often multilingual; present and warm
- Youssou N'Dour-style: Senegalese-flavored; Angelique Kidjo-style: more eclectic, pan-African
- Interlocking guitar patterns provide rhythmic and harmonic interest; clear and defined
- Percussion blends traditional and electronic; preserve the rhythmic complexity
- A polished, warm master suits the genre's contemporary commercial orientation

### Hindustani
**LUFS target**: -18 LUFS
**Dynamics**: Minimal compression; preserve the full dynamic range of raga performance from meditative alap to energetic jhala; the musical structure IS the dynamics
**EQ focus**: Sitar/sarod clarity (1-6 kHz), tanpura drone warmth (80-300 Hz), tabla definition (3-8 kHz), vocal presence (1-4 kHz), minimal EQ intervention
**MCP command**: `master_audio(file, genre="hindustani")`

**Characteristics**:
- Raga performance unfolds from quiet alap through jor to fast jhala; the dynamic arc is compositional
- Sitar/sarod/sarangi carry the melodic exploration; preserve every ornament and microtone
- Tanpura drone provides the harmonic foundation; warm, sustained, and ever-present
- Tabla rhythms are complex and virtuosic; every stroke must be clear and defined
- Ravi Shankar-style: wider dynamics, more meditative sections; shorter compositions: tighter
- The genre demands transparent mastering that does not impose Western conventions on Indian music

### Carnatic
**LUFS target**: -18 LUFS
**Dynamics**: Minimal compression; preserve the full dynamic range and complex rhythmic patterns (tala); Carnatic music's mathematical precision depends on clarity
**EQ focus**: Vocal ornamentation detail (1-4 kHz), veena/violin clarity (800 Hz-6 kHz), mridangam definition (3-8 kHz), tanpura drone warmth, minimal intervention
**MCP command**: `master_audio(file, genre="carnatic")`

**Characteristics**:
- Highly ornamented vocal or instrumental performance; every gamaka (ornament) must be audible
- Rhythmic complexity (intricate tala patterns) requires precise transient clarity
- M.S. Subbulakshmi-style vocal: devotional, dynamic; instrumental kritis: more technical
- Mridangam and ghatam provide rhythmic accompaniment; complex and virtuosic
- Tanpura drone provides the harmonic foundation; warm and steady
- The genre demands the same minimal mastering approach as Hindustani music; cultural sensitivity is essential

### Indian Classical
**LUFS target**: -18 LUFS
**Dynamics**: Minimal compression; preserve the full dynamic range of classical performance; this is the umbrella covering both Hindustani and Carnatic traditions
**EQ focus**: Vocal/instrument clarity (1-6 kHz), drone warmth (80-300 Hz), tabla/mridangam definition (3-8 kHz), minimal EQ intervention
**MCP command**: `master_audio(file, genre="indian-classical")`

**Characteristics**:
- The dynamic arc of raga/ragam performance is compositional; protect the full range from silence to climax
- Microtonal ornamentation (gamakas, meend) must be preserved; they are the music's expressive language
- Performance can be Hindustani or Carnatic; identify the tradition and master accordingly
- Drone (tanpura) is the harmonic anchor; warm, steady, and ever-present
- Rhythmic accompaniment is virtuosic and complex; transient clarity is essential
- The most minimal mastering approach is appropriate; let the music speak

### Ghazal
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the intimate vocal dynamics and poetic delivery; ghazal's emotional refinement depends on subtle expression
**EQ focus**: Vocal warmth and ornamentation (1-4 kHz), harmonium/sitar body (200-600 Hz), tabla subtlety (3-6 kHz), gentle high-frequency air
**MCP command**: `master_audio(file, genre="ghazal")`

**Characteristics**:
- Vocal delivery is intimate, refined, and heavily ornamented; every nuance matters
- Ghulam Ali/Jagjit Singh-style: more traditional, wider dynamics; modern fusion: slightly more produced
- Harmonium provides the harmonic bed; warm and sustained
- Tabla accompaniment is gentle and responsive; supporting the vocal, not driving
- The genre is poetry set to music; the words and their delivery are paramount
- A warm, intimate master that preserves the poetic refinement

### Chutney
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the energetic, Caribbean-Indo fusion dance energy; the genre demands party-ready production
**EQ focus**: Dholak/tassa drum punch (3-6 kHz), vocal clarity (2-5 kHz), bass groove (60-150 Hz), sitar/keyboard presence (200-600 Hz), percussion energy (4-8 kHz)
**MCP command**: `master_audio(file, genre="chutney")`

**Characteristics**:
- Indo-Caribbean fusion combines Indian rhythms with calypso/soca energy; preserve both elements
- Dholak and tassa drums provide the driving rhythm; punchy and energetic
- Vocals blend Indian vocal style with Caribbean delivery; clear and present
- Bass is groovy and dance-oriented; supports the party energy
- Sundar Popo/Drupatee-style: more traditional; modern soca-chutney: more electronic, bass-heavy
- A punchy, energetic master suits the genre's party-music character

### Bachata
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the requinto guitar's melodic ornamentation and romantic vocal dynamics; the genre balances intimacy with dancefloor energy
**EQ focus**: Requinto guitar clarity (2-6 kHz), vocal warmth (2-5 kHz), bass groove (60-150 Hz), bongo detail (3-6 kHz), guira shimmer (6-10 kHz)
**MCP command**: `master_audio(file, genre="bachata")`

**Characteristics**:
- Requinto (lead guitar) carries the iconic melodic ornamentation; its bright, clean tone is the genre's signature
- Vocals are warm, romantic, and emotionally present; the lyrics are the heart of bachata
- Juan Luis Guerra/Romeo Santos-style: more polished, pop-influenced; traditional: rawer, more guitar-forward
- Bongo and guira provide the rhythmic drive; crisp and defined
- Bass is warm and groovy; supports the dance rhythm
- A warm, polished master preserves bachata's romantic, dance-ready character

### Bolero
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the intimate, romantic dynamics; bolero's emotional power comes from restraint and vulnerability
**EQ focus**: Vocal warmth and intimacy (1-4 kHz), guitar body (200-600 Hz), string arrangement sweetness (300-600 Hz), gentle bass (80-200 Hz), room acoustics
**MCP command**: `master_audio(file, genre="bolero")`

**Characteristics**:
- Vocal delivery is intimate, romantic, and dynamically nuanced; every breath and whisper matters
- Guitar (classical or requinto) provides the harmonic bed; warm and gentle
- Trio Los Panchos/Lucho Gatica-style: classic, sparse; modern: slightly fuller arrangements
- String arrangements add romantic drama; lush but never overpowering the vocal
- Bass is gentle and supportive; barely there but providing warmth
- The genre rewards the most intimate, careful mastering; over-processing destroys the romance

### Tango
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the wide dynamic range between dramatic forte passages and intimate, sparse sections; tango's emotional power lives in the contrast
**EQ focus**: Bandoneón body and breath (200-800 Hz), violin section shimmer and attack (1-5 kHz), piano clarity (200-600 Hz), double bass warmth (60-200 Hz), vocal presence (2-4 kHz)
**MCP command**: `master_audio(file, genre="tango")`

**Characteristics**:
- Bandoneón is tango's emotional center; preserve its mid-range complexity, the reedy breath and attack without harshness
- Osvaldo Pugliese-style dramatic dynamics: deep dynamic swings, heavy bass ostinato, sudden explosions of intensity — protect the full range
- Juan d'Arienzo-style rhythmic tangos: tighter, punchier; maintain rhythmic clarity without crushing transients
- Violin sections carry melodic lines with expressive vibrato; preserve warmth and string attack above 3 kHz
- Double bass provides harmonic and rhythmic foundation; deep, warm, and clearly defined from 60-200 Hz
- Nuevo tango (Piazzolla): can sit at -15 LUFS; more polished, concert-ready treatment; preserve the jazz-influenced harmonic complexity
- Electrotango (Gotan Project, Bajofondo): treat more like electronic production; -14 LUFS acceptable; programmed elements need clarity and punch
- Tango canción (vocal tangos): vocal presence and intimacy are paramount — center the voice, protect its dynamic expression

### Mambo
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the explosive big-band energy and dancing rhythm; the genre demands power and joy
**EQ focus**: Horn section brightness (1-4 kHz), bass tumbao groove (80-200 Hz), percussion detail (3-8 kHz), piano montuno clarity (200-600 Hz), vocal energy (2-5 kHz)
**MCP command**: `master_audio(file, genre="mambo")`

**Characteristics**:
- Big horn sections create explosive, joyful energy; bright, punchy, and powerful
- Tito Puente/Perez Prado-style: full big-band power; the genre demands energy
- Bass tumbao provides the rhythmic foundation; warm and locked to the clave
- Layered percussion (timbales, congas, bongos) creates polyrhythmic complexity; preserve clarity
- Piano montuno drives the harmonic rhythm; clear and percussive
- A punchy, energetic master preserves mambo's dancefloor joy and power

### Merengue
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the fast, driving rhythm and accordion energy; the genre is high-energy party music
**EQ focus**: Accordion brightness (800 Hz-3 kHz), tambora punch (80-200 Hz), guira drive (4-8 kHz), bass definition (60-150 Hz), vocal clarity (2-5 kHz)
**MCP command**: `master_audio(file, genre="merengue")`

**Characteristics**:
- Fast, driving 2/4 rhythm is the genre's identity; energetic and relentless
- Accordion carries the melody; bright, fast, and present
- Tambora and guira provide the rhythmic backbone; punchy and crisp
- Juan Luis Guerra/Wilfrido Vargas-style: more polished; traditional perico ripiao: rawer, accordion-forward
- Bass is punchy and driving; supports the fast dance rhythm
- A punchy, energetic master suits the genre's party-music character

### Son Cubano
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the clave-based rhythmic interplay and tres guitar ornamentation; the genre balances sophistication with dance energy
**EQ focus**: Tres guitar clarity (2-6 kHz), bass tumbao warmth (80-200 Hz), horn presence (1-4 kHz), bongo detail (3-6 kHz), vocal warmth (2-5 kHz)
**MCP command**: `master_audio(file, genre="son-cubano")`

**Characteristics**:
- Clave pattern is the rhythmic foundation; everything relates to it; preserve the polyrhythmic clarity
- Tres (three-course guitar) carries the melodic guajeo; bright, rhythmic, and ornamented
- Buena Vista Social Club-style: warmer, vintage; modern son: slightly more produced
- Bass tumbao is both rhythmic and melodic; warm and defined
- Vocal delivery ranges from intimate to powerful; clear and warm
- A warm, groove-oriented master preserves son cubano's elegant dance-music tradition

### Ranchera
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the powerful vocal dynamics from intimate whisper to full-voice bravura; ranchera's emotional power depends on dynamic range
**EQ focus**: Vocal power and presence (2-5 kHz), trumpet brightness (1-4 kHz), violin warmth (2-6 kHz), guitarron depth (60-150 Hz), vihuela sparkle (3-6 kHz)
**MCP command**: `master_audio(file, genre="ranchera")`

**Characteristics**:
- Powerful vocal delivery (grito, falsetto, full voice) requires wide dynamic range; the bravura is the genre's soul
- Trumpet and violin sections carry the mariachi arrangement; bright, present, and emotional
- Jose Alfredo Jimenez/Vicente Fernandez-style: more traditional, vocal-forward; modern: slightly more polished
- Guitarron provides the bass foundation; deep and steady
- Vihuela adds rhythmic sparkle; bright and percussive
- A warm, dynamic master preserves ranchera's emotional depth and vocal power

### Mariachi
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the ensemble dynamics and trumpet brilliance; the genre's festive energy demands clarity and power
**EQ focus**: Trumpet brightness (1-4 kHz), violin sweetness (2-6 kHz), guitarron depth (60-150 Hz), vocal clarity (2-5 kHz), vihuela sparkle (3-6 kHz)
**MCP command**: `master_audio(file, genre="mariachi")`

**Characteristics**:
- Trumpet section is the genre's voice; brilliant, powerful, and present without harshness
- Violins add melodic sweetness; warm and expressive
- Guitarron provides the bass foundation; deep, resonant, and steady
- Vocal performance is powerful and emotive; clear above the full ensemble
- The ensemble plays together tightly; preserve the rhythmic precision and balance
- A warm, balanced master that preserves the festive, celebratory ensemble sound

### Corridos Tumbados
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; modern production blending corrido tradition with trap/urban elements; radio-ready with regional Mexican character
**EQ focus**: Requinto/tololoche clarity (2-6 kHz), 808 bass weight (40-80 Hz), vocal presence (2-5 kHz), hi-hat crispness (8-12 kHz), tuba definition (60-150 Hz)
**MCP command**: `master_audio(file, genre="corridos-tumbados")`

**Characteristics**:
- Traditional Mexican instruments meet trap production; balance both worlds
- Requinto guitar provides melodic character; bright and present
- 808 bass or tuba provides low-end foundation; heavy and defined
- Natanael Cano/Peso Pluma-style: more urban, trap-influenced; the genre is evolving rapidly
- Vocal delivery blends corrido narrative with modern melodic style; clear and present
- A polished, modern master that bridges traditional and contemporary production

### Banda
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the big brass band energy and rhythmic drive; the genre demands power and festivity
**EQ focus**: Brass section brightness (1-4 kHz), bass drum/tuba depth (60-150 Hz), percussion energy (3-6 kHz), vocal clarity (2-5 kHz), clarinet presence (1-4 kHz)
**MCP command**: `master_audio(file, genre="banda")`

**Characteristics**:
- Full brass section creates powerful, festive energy; bright and punchy without harshness
- Tuba and bass drum provide the rhythmic foundation; deep and driving
- Banda El Recodo-style: more traditional, polished; smaller bandas: rawer, more energetic
- Vocal performance is powerful and emotive; must cut through the dense brass arrangement
- The genre is Mexican party music; the energy and joy must translate
- A punchy, bright master preserves banda's celebratory big-band character

### Tejano
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the accordion-driven cumbia groove and vocal warmth; polished but with working-class authenticity
**EQ focus**: Accordion brightness (800 Hz-3 kHz), bajo sexto body (200-600 Hz), bass definition (60-150 Hz), vocal warmth (2-5 kHz), percussion detail (3-6 kHz)
**MCP command**: `master_audio(file, genre="tejano")`

**Characteristics**:
- Accordion and bajo sexto are the genre's signature instruments; both need clear presence
- Vocals are warm, powerful, and emotionally direct; Selena set the standard
- Selena-style: polished, pop-influenced; Grupo Mazz-style: more traditional, cumbia-driven
- Cumbia rhythms underpin much of the genre; preserve the dance groove
- The genre blends Mexican, American, and dance-music elements; balance all influences
- A warm, polished master preserves Tejano's unique Tex-Mex identity

### Vallenato
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the accordion ornamentation and rhythmic groove; the genre balances virtuosic musicianship with dance energy
**EQ focus**: Accordion brightness (800 Hz-3 kHz), caja drum punch (3-6 kHz), guacharaca shimmer (4-8 kHz), bass warmth (60-150 Hz), vocal clarity (2-5 kHz)
**MCP command**: `master_audio(file, genre="vallenato")`

**Characteristics**:
- Accordion is the genre's voice; virtuosic runs and ornamentation must be clear and present
- Caja (small drum) and guacharaca (scraper) provide the rhythmic backbone; crisp and driving
- Carlos Vives-style modern: more polished, pop-influenced; traditional: rawer, more acoustic
- Vocal delivery is warm and storytelling-oriented; clear and emotionally present
- Bass is warm and supportive; drives the dance rhythm
- A warm, balanced master preserves vallenato's Colombian dance-music character

### Chicha
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the psychedelic guitar effects and Andean rhythmic character; the genre blends psychedelia with cumbia
**EQ focus**: Electric guitar psychedelic effects (800 Hz-3 kHz), bass groove (60-150 Hz), percussion detail (3-6 kHz), keyboard/organ warmth (200-600 Hz), vocal presence (2-5 kHz)
**MCP command**: `master_audio(file, genre="chicha")`

**Characteristics**:
- Psychedelic electric guitar with reverb, delay, and tremolo defines the sound; preserve the effects
- Cumbia rhythm provides the dance foundation; bouncy and driving
- Los Destellos/Los Mirlos-style: classic, rawer; modern chicha: more produced, bass-heavy
- Peruvian/Andean musical identity is central; preserve the distinctive melodic character
- Bass is warm and groovy (cumbia influence); supports the dance rhythm
- A warm, slightly psychedelic master preserves chicha's unique Andean-psychedelic fusion

### Huayno
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the charango/harp character and Andean vocal style; the genre's mountain-music identity needs warmth and clarity
**EQ focus**: Charango/harp brightness (2-6 kHz), vocal warmth (2-5 kHz), bass/bombo depth (60-150 Hz), quena/zamponas clarity (1-4 kHz), guitar body (200-600 Hz)
**MCP command**: `master_audio(file, genre="huayno")`

**Characteristics**:
- Charango and/or harp carry the melody; bright, sparkling, and present
- Quena (flute) and zampona (pan pipes) add Andean color; clear and warm
- Vocal delivery is powerful and emotive; Andean vocal style is distinctive
- Traditional huayno: more acoustic, wider dynamics; modern: more electric, polished
- Bombo provides the rhythmic pulse; warm and deep
- A warm, clear master preserves huayno's Andean mountain-music identity

### Axe
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the Carnival energy and rhythmic drive; axe is Brazilian party music designed for massive street parades
**EQ focus**: Percussion energy (3-8 kHz), vocal clarity (2-5 kHz), bass groove (60-150 Hz), guitar/synth presence (200-600 Hz), brass brightness (1-4 kHz)
**MCP command**: `master_audio(file, genre="axe")`

**Characteristics**:
- Driving percussion (samba-reggae influenced) creates the Carnival energy; powerful and relentless
- Vocals are energetic and singable; clear above the dense percussion
- Ivete Sangalo-style: more pop, polished; Olodum-influenced: more percussion-heavy, raw
- Bass is punchy and groove-oriented; supports the dance rhythm
- The genre is designed for massive outdoor celebrations; energy and loudness are essential
- A punchy, energetic master preserves axe's Bahian Carnival spirit

### Forro
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the accordion-driven dance groove and triangle shimmer; the genre is northeastern Brazilian party music
**EQ focus**: Accordion brightness (800 Hz-3 kHz), zabumba punch (60-200 Hz), triangle shimmer (6-10 kHz), vocal warmth (2-5 kHz), bass definition (60-150 Hz)
**MCP command**: `master_audio(file, genre="forro")`

**Characteristics**:
- Accordion carries the melody; bright, fast, and virtuosic
- Zabumba (bass drum) and triangle provide the rhythmic backbone; punchy and shimmering
- Luiz Gonzaga-style traditional: rawer, more acoustic; forro universitario: more polished, pop-influenced
- Vocal delivery is warm and engaging; storytelling-oriented
- The trio (accordion, zabumba, triangle) is the core instrumentation; all three need clear presence
- A warm, energetic master preserves forro's northeastern Brazilian dance-party character

### MPB
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the sophisticated arrangements and dynamic range; MPB is Brazilian art-pop with wide stylistic range
**EQ focus**: Vocal warmth and presence (2-5 kHz), guitar body (200-600 Hz), bass groove (60-150 Hz), percussion detail (3-8 kHz), orchestral warmth (200-600 Hz)
**MCP command**: `master_audio(file, genre="mpb")`

**Characteristics**:
- Sophisticated arrangements blending bossa nova, samba, jazz, and pop; the production is artful
- Vocals are warm, expressive, and central; Caetano Veloso/Gilberto Gil-style vocal beauty
- Production ranges from sparse acoustic to full orchestral; adapt mastering to the arrangement
- Bass is melodic and groovy (Brazilian tradition); warm and defined
- Brazilian rhythmic foundations underpin the sophistication; preserve rhythmic clarity
- A warm, polished master preserves MPB's artistic sophistication and beauty

### Pagode
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the intimate, party-oriented groove and cavaquinho sparkle; pagode is friends-around-a-table samba
**EQ focus**: Cavaquinho brightness (2-6 kHz), tantan/repique punch (3-6 kHz), vocal warmth (2-5 kHz), bass groove (60-150 Hz), pandeiro shimmer (6-10 kHz)
**MCP command**: `master_audio(file, genre="pagode")`

**Characteristics**:
- Cavaquinho carries the melodic and harmonic foundation; bright, percussive, and sparkling
- Tantan and repique provide the rhythmic drive; punchy and bouncy
- Vocals are warm, intimate, and conversational; party-singing style
- Zeca Pagodinho/Beth Carvalho-style: more traditional; modern pagode: more polished, romantic
- The genre has a backyard-party intimacy; preserve the warm, communal feeling
- A warm, groovy master preserves pagode's intimate, celebratory character

### Soca
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; high-energy Carnival music designed for maximum dancefloor impact; the genre demands energy and punch
**EQ focus**: Bass weight (40-100 Hz), vocal energy (2-5 kHz), hi-hat and percussion crispness (6-12 kHz), synth brightness (1-4 kHz), kick punch (40-80 Hz)
**MCP command**: `master_audio(file, genre="soca")`

**Characteristics**:
- Driving, uptempo Carnival rhythm demands energy and physical impact
- Bass is heavy and punchy; the foundation of the dancefloor experience
- Machel Montano/Bunji Garlin-style: maximum energy; groovy soca: slightly less aggressive
- Vocals are energetic and call-and-response oriented; clear above the dense production
- Electronic production elements add modern punch; bright and cutting
- Push to -12 LUFS for power soca; -14 for groovy soca; energy is everything

### Calypso
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the witty vocal delivery and rhythmic groove; calypso's charm is in the lyrical cleverness and dance feel
**EQ focus**: Vocal clarity (2-5 kHz), steel pan shimmer (2-8 kHz), bass warmth (80-200 Hz), percussion detail (3-8 kHz), horn brightness (1-4 kHz)
**MCP command**: `master_audio(file, genre="calypso")`

**Characteristics**:
- Vocal delivery carries the wit and social commentary; every word must be clear and present
- Steel pan provides the iconic melodic color; bright, shimmering, and present
- Mighty Sparrow/Lord Kitchener-style: more traditional; modern calypso: more produced
- Bass is warm and groovy; supports the dance rhythm
- Horn sections add melodic brightness; present without harshness
- A warm, clear master preserves calypso's witty, danceable character

### Mento
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the acoustic, pre-ska Jamaican folk character; the genre has a gentle, rural charm
**EQ focus**: Guitar/banjo clarity (800 Hz-3 kHz), rumba box bass (60-150 Hz), vocal warmth (2-5 kHz), percussion detail (3-6 kHz), flute/harmonica presence (1-4 kHz)
**MCP command**: `master_audio(file, genre="mento")`

**Characteristics**:
- Acoustic, rural Jamaican folk music; the precursor to ska and reggae
- Rumba box provides the bass; unique resonant character needs preservation
- Guitar and banjo carry the melody; bright and acoustic
- Vocal delivery is warm and storytelling-oriented; often humorous
- The genre predates studio polish; preserve the natural, organic character
- A warm, acoustic-sounding master preserves mento's folk-music charm

### Kompa
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the smooth, groovy dance rhythm and guitar-driven character; Haitian dance music with sophistication
**EQ focus**: Guitar clarity (800 Hz-3 kHz), bass groove (60-150 Hz), keyboard warmth (200-500 Hz), vocal sweetness (2-5 kHz), percussion detail (3-6 kHz)
**MCP command**: `master_audio(file, genre="kompa")`

**Characteristics**:
- Smooth, rolling guitar patterns define the genre's groove; clear and melodic
- Bass is groovy and driving; the foundation of the dance rhythm
- Tabou Combo-style: full band, more energetic; modern kompa: smoother, more R&B-influenced
- Vocals are sweet and melodic; warm and present
- Keyboard and synth elements add harmonic color; warm and supportive
- A polished, warm master preserves kompa's smooth Haitian dance-music character

### Champeta
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the energetic, bass-heavy groove and African-Colombian rhythmic drive; street-party energy
**EQ focus**: Bass weight (40-100 Hz), percussion energy (3-8 kHz), synth/keyboard brightness (200-600 Hz), vocal clarity (2-5 kHz), kick punch (40-80 Hz)
**MCP command**: `master_audio(file, genre="champeta")`

**Characteristics**:
- Bass-heavy production with African-influenced rhythms; heavy and driving
- Electronic/synth-heavy production with Afro-Colombian rhythmic patterns
- Modern champeta: more electronic, bass-heavy; traditional: more acoustic, soukous-influenced
- Vocal delivery is energetic and rhythmic; clear above the heavy production
- The genre is Colombian street-party music; raw energy is essential
- A punchy, bass-forward master preserves champeta's dancefloor impact

### Punta
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the driving, polyrhythmic dance groove and Garifuna rhythmic character
**EQ focus**: Drum energy (3-8 kHz), bass groove (60-150 Hz), guitar/keyboard presence (200-600 Hz), vocal clarity (2-5 kHz), turtle shell percussion
**MCP command**: `master_audio(file, genre="punta")`

**Characteristics**:
- Polyrhythmic drum patterns define the genre's driving energy; preserve their complexity
- Bass is groovy and supportive; drives the dance rhythm
- Andy Palacio-style: more traditional, cultural; punta rock: more electric, modern
- Vocal delivery is energetic and call-and-response; clear and present
- The genre is Garifuna cultural music; the rhythmic identity is sacred
- A punchy, rhythm-forward master preserves punta's cultural energy

### Soukous
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the interlocking guitar patterns and dance energy; Congolese rumba-derived party music with technical guitar virtuosity
**EQ focus**: Guitar clarity and sparkle (800 Hz-4 kHz), bass groove (60-150 Hz), vocal warmth (2-5 kHz), percussion detail (3-8 kHz), horn presence (1-4 kHz)
**MCP command**: `master_audio(file, genre="soukous")`

**Characteristics**:
- Virtuosic, interlocking guitar patterns are the genre's signature; every note must be clear
- Sebene (instrumental dance section) is the genre's climax; guitar fireworks need headroom and clarity
- Franco/TPOK Jazz-style: classic, full-band; Kanda Bongo Man-style: faster, more dance-oriented
- Bass guitar is melodic and prominent; warm and defined, locked to the rhythm
- Vocal delivery is warm and engaging; melodic and harmonized
- A warm, guitar-forward master preserves soukous's dancefloor virtuosity

### Juju
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the layered guitar patterns and talking drum character; Nigerian party music with hypnotic groove
**EQ focus**: Guitar clarity and shimmer (800 Hz-4 kHz), talking drum presence (800 Hz-3 kHz), bass warmth (60-150 Hz), vocal clarity (2-5 kHz), percussion detail (3-8 kHz)
**MCP command**: `master_audio(file, genre="juju")`

**Characteristics**:
- Layered guitar patterns create a shimmering, hypnotic texture; preserve the interplay
- Talking drum carries melodic and rhythmic communication; its tonal character must be clear
- King Sunny Ade/Ebenezer Obey-style: classic, more spacious; modern: tighter, more produced
- Pedal steel guitar adds melodic color (King Sunny Ade innovation); preserve its shimmer
- Vocal delivery is warm and call-and-response; clear and communal
- A warm, spacious master preserves juju's hypnotic Nigerian party-music character

### Fuji
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the percussion-driven energy and vocal ornamentation; Yoruba cultural music with intense rhythmic complexity
**EQ focus**: Drum ensemble energy (3-8 kHz), vocal presence and ornamentation (1-4 kHz), bass rhythm (60-150 Hz), percussion detail, shekere shimmer (6-10 kHz)
**MCP command**: `master_audio(file, genre="fuji")`

**Characteristics**:
- Dense percussion ensemble drives the rhythm; multiple drum parts must remain distinct
- Vocal delivery is powerful, ornamented, and dynamically free; preserve the melismatic character
- Sikiru Ayinde Barrister/Wasiu Ayinde K1-style: more traditional; modern: more electronic
- The genre is percussion and voice-centered; no Western harmonic instruments traditionally
- Shekere and other percussion add rhythmic texture; crisp and present
- A punchy, rhythm-forward master preserves fuji's intense Yoruba percussion-music character

### Mbalax
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the sabar drum complexity and dance energy; Senegalese pop music with polyrhythmic sophistication
**EQ focus**: Sabar drum clarity (3-8 kHz), guitar sparkle (800 Hz-3 kHz), bass groove (60-150 Hz), vocal presence (2-5 kHz), keyboard warmth (200-500 Hz)
**MCP command**: `master_audio(file, genre="mbalax")`

**Characteristics**:
- Sabar drums (ensemble of tuned hand drums) create the signature polyrhythmic foundation; every stroke matters
- Guitar provides melodic and rhythmic patterns; bright and interlocking
- Youssou N'Dour-style: more polished, global; traditional mbalax: rawer, more sabar-forward
- Vocal delivery is powerful and ornamented; Wolof singing tradition needs headroom
- Bass is groovy and supportive; drives the dance rhythm
- A punchy, percussion-forward master preserves mbalax's Senegalese dance-music energy

### Chimurenga
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the mbira patterns and polyrhythmic interplay; Zimbabwean liberation music with deep cultural character
**EQ focus**: Mbira clarity (1-6 kHz), vocal warmth (2-5 kHz), bass groove (60-150 Hz), percussion detail (3-8 kHz), guitar presence (800 Hz-3 kHz)
**MCP command**: `master_audio(file, genre="chimurenga")`

**Characteristics**:
- Mbira (thumb piano) patterns are the genre's soul; their bright, metallic tone with buzzing resonance must be clear
- Thomas Mapfumo-style: definitive, electric adaptation of mbira music; preserve the cultural roots
- Vocal delivery is warm and powerful; Shona singing tradition
- Bass is groovy and hypnotic; supports the mbira-driven groove
- Guitar often translates mbira patterns to electric instrument; preserve the interplay
- A warm, clear master preserves chimurenga's Zimbabwean cultural identity

### Mbaqanga
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the driving bass groove and vocal harmonies; South African township jive with infectious energy
**EQ focus**: Bass guitar prominence (60-200 Hz), vocal harmony clarity (2-5 kHz), guitar jive patterns (800 Hz-3 kHz), drum punch (3-6 kHz), horn brightness (1-4 kHz)
**MCP command**: `master_audio(file, genre="mbaqanga")`

**Characteristics**:
- Bass guitar is unusually prominent; deep, melodic, and driving; it carries the song
- Vocal harmonies (often male/female call and response) are warm and full
- Mahlathini/Mahotella Queens-style: classic, rawer; modern: more polished
- Guitar patterns are rhythmic and jive-oriented; bright and percussive
- The genre has a joyful, township-party energy; preserve the communal feeling
- A warm, bass-forward master preserves mbaqanga's South African township character

### Isicathamiya
**LUFS target**: -16 LUFS
**Dynamics**: Minimal compression; preserve the a cappella vocal dynamics and harmonies; the genre is unaccompanied vocal performance with extreme dynamic sensitivity
**EQ focus**: Vocal harmony clarity (1-5 kHz), bass voice presence (80-200 Hz), room acoustics, minimal EQ intervention
**MCP command**: `master_audio(file, genre="isicathamiya")`

**Characteristics**:
- Unaccompanied vocal performance; the voices are everything; pristine clarity required
- Dynamic range from soft, whispered passages to full-voice harmony; protect the full range
- Ladysmith Black Mambazo-style: the genre's global ambassadors; gentle yet powerful
- Bass voices provide the harmonic foundation; warm, deep, and resonant
- The gentle, tiptoeing (isicathamiya means "walk softly") quality is essential; do not add aggression
- The most minimal mastering approach is appropriate; let the voices speak

### Maskandi
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the guitar picking patterns and vocal energy; Zulu folk-pop with rhythmic drive
**EQ focus**: Guitar picking clarity (800 Hz-4 kHz), vocal presence (2-5 kHz), bass groove (60-150 Hz), percussion detail (3-6 kHz), concertina warmth
**MCP command**: `master_audio(file, genre="maskandi")`

**Characteristics**:
- Acoustic/electric guitar picking patterns are the genre's identity; fast, rhythmic, and melodic
- Vocal delivery is powerful and often includes Zulu vocal techniques (umqokozo)
- Phuzekhemisi/Shwi noMtekhala-style: more traditional; modern: more electric, produced
- Bass is groovy and supportive; drives the dance rhythm
- Concertina adds melodic color in some substyles; warm and present
- A warm, guitar-forward master preserves maskandi's Zulu cultural character

### Bongo Flava
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; polished, modern production blending Tanzanian musical identity with hip-hop and R&B; radio-ready
**EQ focus**: Vocal clarity (2-5 kHz), bass weight (40-100 Hz), synth/keyboard warmth (200-500 Hz), percussion detail (4-8 kHz), hi-hat crispness (8-12 kHz)
**MCP command**: `master_audio(file, genre="bongo-flava")`

**Characteristics**:
- Modern, polished production with hip-hop and R&B influences; radio-ready
- Vocals blend Swahili with English; clear and present
- Diamond Platnumz-style: more polished, Afrobeats-influenced; street bongo flava: rawer
- Bass is modern and heavy; supports the dancefloor energy
- The genre is Tanzania's mainstream pop; commercial production quality expected
- A polished, modern master suits bongo flava's contemporary aspirations

### Taarab
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the ornate orchestral arrangements and vocal ornamentation; Swahili coast art music with Arabic influences
**EQ focus**: Vocal ornamentation (1-4 kHz), oud/qanun clarity (2-6 kHz), string warmth (200-600 Hz), percussion subtlety (3-6 kHz), bass definition (80-200 Hz)
**MCP command**: `master_audio(file, genre="taarab")`

**Characteristics**:
- Ornate vocal delivery with Arabic-influenced ornamentation; headroom for melisma essential
- Oud, qanun, and violin carry melodic lines; warm, clear, and expressive
- Bi Kidude/Siti binti Saad-style: more traditional; modern taarab: more produced, electric
- String sections add lush harmonic depth; warm and supportive
- The genre is Swahili coast wedding and celebration music; elegance is key
- A warm, spacious master preserves taarab's ornate, refined character

### Sega
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the driving dance rhythm and ravanne drum energy; Mauritian party music with Creole character
**EQ focus**: Ravanne drum warmth (200-600 Hz), vocal clarity (2-5 kHz), guitar/bass groove (80-200 Hz), percussion detail (3-8 kHz), triangl shimmer
**MCP command**: `master_audio(file, genre="sega")`

**Characteristics**:
- Ravanne (frame drum) drives the rhythm; warm, resonant, and danceable
- Vocal delivery is energetic and Creole-language; clear and present
- Traditional sega: more acoustic, wider dynamics; seggae (reggae fusion): more modern, bass-heavy
- Guitar provides harmonic support; warm and rhythmic
- The genre is Mauritian national music; preserve its island-party character
- A warm, energetic master preserves sega's Creole dance-music identity

### Semba
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the guitar-driven groove and vocal warmth; Angolan dance music that influenced Brazilian samba
**EQ focus**: Guitar clarity (800 Hz-3 kHz), bass groove (60-150 Hz), vocal warmth (2-5 kHz), percussion detail (3-6 kHz), dikanza shimmer (4-8 kHz)
**MCP command**: `master_audio(file, genre="semba")`

**Characteristics**:
- Guitar patterns (acoustic and electric) drive the groove; melodic and rhythmic
- Bass is prominent and groovy; the foundation of the dance rhythm
- Bonga-style: more internationally polished; traditional: more acoustic, rawer
- Vocal delivery is warm, emotive, and often narrative; clear and present
- Dikanza (scraper) and percussion add rhythmic texture; crisp detail
- A warm, groove-forward master preserves semba's Angolan dance-music character

### Kizomba
**LUFS target**: -14 LUFS
**Dynamics**: Light-to-moderate compression; preserve the sensual, intimate groove and smooth vocal delivery; the genre is designed for close-embrace partner dancing
**EQ focus**: Vocal sweetness (2-5 kHz), bass warmth (40-100 Hz), synth pad atmosphere (200-500 Hz), percussion subtlety (3-6 kHz), high-frequency air
**MCP command**: `master_audio(file, genre="kizomba")`

**Characteristics**:
- Smooth, sensual groove (semba-influenced rhythm) is the genre's identity; the bounce must be gentle and inviting
- Bass is warm, round, and felt; not aggressive or sub-heavy; it supports the intimate dance
- Vocal delivery is smooth and romantic; clear and warm
- Synth pads create atmospheric warmth; supportive and enveloping
- Nelson Freitas/Anselmo Ralph-style: more polished, R&B-influenced; the genre demands smoothness
- A warm, intimate master preserves kizomba's sensual, dance-ready character

### A Cappella
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the vocal dynamics and harmony balance; the genre is pure vocal performance without instrumental accompaniment
**EQ focus**: Vocal harmony clarity (1-5 kHz), bass voice definition (80-200 Hz), beat-boxing definition (when present), sibilance control, room acoustics
**MCP command**: `master_audio(file, genre="a-cappella")`

**Characteristics**:
- Voices are the only instruments; every vocal part needs clarity within the blend
- Dynamic range from soft harmony to powerful climax must be preserved
- Pentatonix-style: more produced, beat-boxed; traditional choral: wider dynamics, more natural
- Bass voice provides the harmonic foundation; warm, deep, and resonant
- Vocal percussion (beat-boxing) needs punch and clarity when present
- The genre demands careful mastering that preserves the purity of vocal performance

### Barbershop
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the vocal harmony dynamics and ring (the overtone resonance that defines the style); minimal processing
**EQ focus**: Vocal harmony clarity (1-5 kHz), bass voice warmth (80-200 Hz), overtone ring preservation (2-6 kHz), sibilance control
**MCP command**: `master_audio(file, genre="barbershop")`

**Characteristics**:
- Four-part close harmony creates the signature "ring" (locking overtones); preserve this acoustic phenomenon
- Dynamic range from tag endings (soft) to powerful chords must be preserved
- Bass voice anchors the harmony; warm, deep, and resonant
- The ring (overtone resonance) is the genre's defining sound quality; do not process it away
- No instrumental accompaniment means the vocal blend is completely exposed
- The most minimal mastering approach preserves the acoustic purity that barbershop demands

### Choir
**LUFS target**: -18 LUFS
**Dynamics**: Minimal compression; preserve the full dynamic range of choral performance from pianissimo to fortissimo; the conductor's dynamics are sacrosanct
**EQ focus**: Vocal clarity (1-5 kHz), bass section warmth (80-200 Hz), room acoustics preservation, minimal EQ intervention, sibilance management
**MCP command**: `master_audio(file, genre="choir")`

**Characteristics**:
- Full dynamic range from whispered passages to thunderous fortissimo must be preserved
- Room acoustics (church, concert hall) are part of the performance; do not over-dry or over-brighten
- Classical choir: widest dynamics, most natural treatment; gospel choir: tighter, more energetic
- Bass, tenor, alto, soprano sections all need clarity within the blend
- Sibilance from massed voices can build up; gentle control without affecting vowel warmth
- The genre demands transparent mastering; the conductor's musical vision must not be altered

### Beatboxing
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the percussive dynamics and timbral variety; the human voice creates drum and bass sounds that need punch and clarity
**EQ focus**: Kick simulation depth (40-100 Hz), snare crack (1-3 kHz), hi-hat crispness (6-12 kHz), bass simulation (40-80 Hz), vocal clarity for melodic sections
**MCP command**: `master_audio(file, genre="beatboxing")`

**Characteristics**:
- The human voice simulates drum kit, bass, and effects; preserve the impressive timbral range
- Kick drum simulations need low-end punch; surprisingly deep for a vocal technique
- Hi-hat and snare simulations need crisp transients; clarity in the upper range
- Bass drops and dubstep-style sounds need definition; the vocal bass is the foundation
- Beardyman/Reeps One-style: more experimental, layered (with loopers); pure beatbox: raw, single-voice
- A punchy, dynamic master preserves the incredible range of the human voice percussion

### Vocaloid
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; manage the synthetic vocal character while preserving the electronic production; the genre blends virtual voices with dense arrangements
**EQ focus**: Synthetic vocal clarity (2-6 kHz), synth arrangement detail (1-4 kHz), bass punch (60-100 Hz), high-mid cut to tame digital harshness (-1.5 dB at 3.5 kHz), high-frequency management
**MCP command**: `master_audio(file, genre="vocaloid")`

**Characteristics**:
- Synthetic voices (Hatsune Miku, etc.) can be harsh in the upper frequencies; careful high-mid management essential
- Dense electronic/rock arrangements compete with the virtual vocal; clear separation needed
- wowaka/ryo-style: more rock, energetic; mellow producers: more pop, gentler
- The virtual vocal has different resonance characteristics than human voice; adapt EQ accordingly
- Bass and drums need punch and energy; J-Pop-level production density is common
- A polished, bright-but-controlled master manages the synthetic voice's unique qualities

### Throat Singing
**LUFS target**: -16 LUFS
**Dynamics**: Light compression; preserve the harmonic overtones that define the technique; throat singing creates multiple simultaneous pitches from one voice
**EQ focus**: Fundamental voice warmth (100-300 Hz), overtone clarity (1-6 kHz), harmonic detail preservation, minimal EQ intervention, room acoustics
**MCP command**: `master_audio(file, genre="throat-singing")`

**Characteristics**:
- Harmonic overtones are the genre's defining feature; they must be clear, distinct, and audible above the fundamental
- Tuvan (khoomei, sygyt, kargyraa) and Mongolian styles create different harmonic patterns; preserve the specific technique
- Huun-Huur-Tu-style: more ensemble, natural; solo performance: more exposed, wider dynamics
- The fundamental drone is deep and sustained; warm and ever-present
- Any processing that obscures the overtones destroys the music's purpose
- The most transparent mastering approach is essential; the human voice's acoustic phenomenon must be preserved

### Visual Kei
**LUFS target**: -14 LUFS
**Dynamics**: Moderate-to-heavy compression; dramatic, dynamic production ranging from ballads to extreme metal; the genre's theatricality demands power and emotional range
**EQ focus**: Vocal clarity across singing/screaming (2-5 kHz), guitar heaviness and melody (800 Hz-3 kHz), bass definition (60-200 Hz), keyboard layers (200-600 Hz), high-mid cut for guitar harshness
**MCP command**: `master_audio(file, genre="visual-kei")`

**Characteristics**:
- Dramatic dynamic shifts from quiet ballads to extreme heaviness; preserve the theatrical range
- Vocals range from sweet singing to harsh screaming; both need intelligibility
- X Japan-style: more symphonic, power metal-influenced; Dir en grey-style: more extreme, experimental
- Guitar work ranges from delicate arpeggios to crushing riffs; both need clarity
- Keyboard and orchestral layers add dramatic scale; present but balanced
- A polished, dynamic master suits the genre's theatrical, emotionally extreme character

### Klezmer
**LUFS target**: -14 LUFS
**Dynamics**: Moderate compression; preserve the emotional dynamics from joyful dance to mournful lament; the genre's wide emotional range depends on dynamic freedom
**EQ focus**: Clarinet warmth and expression (800 Hz-4 kHz), violin emotion (2-6 kHz), accordion body (800 Hz-2 kHz), bass definition (80-200 Hz), percussion detail (3-6 kHz)
**MCP command**: `master_audio(file, genre="klezmer")`

**Characteristics**:
- Clarinet is the genre's voice; its crying, laughing, wailing expressiveness must be preserved
- Violin adds melodic ornamentation; expressive and emotional
- Naftule Brandwein/Dave Tarras-style: more traditional; modern klezmer (Klezmatics): more fusion, experimental
- Accordion provides harmonic and rhythmic support; warm and present
- The genre moves between joy and sorrow rapidly; dynamic contrast is essential
- A warm, dynamic master preserves klezmer's emotional expressiveness

---

## Problem-Solving

### Problem: Track Won't Reach -14 LUFS

**Cause**: High dynamic range (classical, acoustic, lots of quiet parts)

**Symptoms**:
```
Track: acoustic-ballad.wav
Integrated LUFS: -18.5
True Peak: -3.2 dBTP
```

**Solution**:
```
fix_dynamic_track(album_slug, track_filename="acoustic-ballad.wav")
```
- Applies moderate compression
- Raises quiet parts
- Preserves natural feel

**Alternative**: Accept quieter LUFS (-16 to -18) if genre appropriate

### Problem: Track Sounds Harsh/Bright

**Cause**: Suno often generates bright vocals/highs

**Solution**:
```
master_audio(album_slug, cut_highmid=-3.0)
```
- Increase high-mid cut to -3 dB
- Reduces harshness at 2-4 kHz

### Problem: Bass Too Loud/Muddy

**Cause**: Suno can over-generate low end

**Solution**:
```
master_audio(album_slug, genre="hip-hop")
```
- Genre preset with low cut
- Clears mud below 60 Hz

**Check**: Some genres (hip-hop, EDM) need strong bass

### Problem: Album Sounds Inconsistent

**Cause**: Different tracks mastered separately

**Solution**:
1. Master entire album together (all files in one folder)
2. Check LUFS range: Should be <1 dB variation
3. Adjust outliers with adjusted targets

### Problem: Track Clips After Mastering

**Cause**: True peak limiter set wrong

**Solution**:
```
master_audio(album_slug, ceiling_db=-1.5)
```
- Targets -1.5 dBTP instead of -1.0
- More headroom for encoding

### Problem: Track Sounds Squashed/Lifeless

**Cause**: Over-compression trying to hit LUFS target

**Solution**:
```
master_audio(album_slug, target_lufs=-16.0)
```
- Masters to -16 instead of -14
- Preserves dynamics

---

## Loudness Myths

### Myth: Louder is Better
**Reality**: Streaming platforms normalize. Squashing dynamics for loudness hurts sound quality with no benefit.

### Myth: -14 LUFS is Too Quiet
**Reality**: Platforms turn it up. You preserve dynamics, platform handles level.

### Myth: Mastering Fixes Bad Mix
**Reality**: Mastering optimizes good audio. Can't rescue fundamentally flawed tracks.

### Myth: All Tracks Should Be Identical LUFS
**Reality**: Small variations (<1 dB) create natural album flow. Perfect matching sounds robotic.

### Myth: True Peak Can Exceed 0.0 dBTP
**Reality**: Will clip after MP3/AAC encoding. Always keep headroom.
