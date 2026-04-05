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
