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
