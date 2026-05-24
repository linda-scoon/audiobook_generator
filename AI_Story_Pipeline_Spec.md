# AI Story Pipeline — Build Spec

*Working specification for the autonomous chapter-generation system*

*Setup phase complete. Pilot story: The Alpha of Ashbrook.*

## About this document

This is the live build spec for the autonomous story pipeline. It is updated as decisions are made. All decisions apply to every story in the catalog — the setup is generalised. Per-story content (skeletons, bibles, chapters) lives in each story's folder.

This document supersedes any contradicting guidance in earlier files.

---

## 1. End-to-end workflow

Canonical sequence for every story. Each step has a clearly defined input and output. Deterministic work stays in scripts; AI work focuses on content.

### Step 1 — Skeleton generation and approval
- AI is prompted with the master catalog blurb, the story's concept, and any user-provided event list.
- AI produces a draft 200-chapter skeleton (see Section 3).
- User reviews and approves or requests revisions.
- Approved skeleton is locked. It becomes the input for everything that follows.

*This is the only mandatory human checkpoint per story. No per-chapter human review during normal operation.*

### Step 2 — Folder structure creation
- A script creates the empty folder structure.
- No AI tokens are spent. Deterministic file system work.

### Step 3a — File creation (deterministic)
- The approved skeleton includes a `files_to_create` section listing every file path needed for this story.
- A script reads `files_to_create` and creates each file as an empty placeholder.
- No AI tokens are spent.

### Step 3b — File population (AI)
- AI is prompted with the approved skeleton + master catalog + any user source material.
- AI populates every file from 3a with the correct content (static bible, character bibles, locations.md, etc.).
- User reviews populated files. This is the second and final human checkpoint before automated chapter writing begins.

### Step 4 — Weekly chapter generation (automated)
- GitHub Action runs on schedule (proposed weekly).
- Action calls the chapter-generation API for the next chapter.
- AI reads: skeleton entry for this chapter, all bibles, locations.md, no_go_list, heat_progression, voice_samples, previous chapter summaries.
- AI produces: chapter prose (.md), audio-tagged narration script, chapter metadata (.meta.json), chapter summary, updated evolving character bibles.
- Self-check step flags potential issues to a flags file.

### Step 5 — Audio generation (automated)
- ElevenLabs API generates MP3 from the audio-tagged narration script.
- MP3 stored in agreed storage (Cloudflare R2 / S3 — TBD).
- MP3 URL written back to the chapter's `.meta.json`.

### Step 6 — Publish (automated)
- GitHub Action pushes chapter + metadata + audio URL to the website.
- Website reads `.meta.json` to render heat-level warnings, age gates, and audio embed.

---

## 2. Initial folder structure (per story) — DECIDED

Whenever a new story is created, the following structure must be initialised.

### Top-level files
- `story.json` — story metadata
- `README.md` — story overview

### Folders
- `bible/`
  - `characters/` (empty folder, populated by Step 3a from skeleton's `files_to_create`)
- `prompts/`
  - `chapter_generation_prompt.md`
- `chapters/` — **NOT YET IN SCRIPT — needs to be added**
  - `README.md`
- `narration/`
  - `README.md`
- `logs/` — **RESERVED FOR ELEVENLABS LOGS. Chapter recaps do NOT go here.**
  - `README.md`
- `summaries/` — chapter recaps live here (see Section 4) — **NOT YET IN SCRIPT**
  - `README.md`
- `output/`
  - `README.md`
- `source/`
  - `README.md`

### Action item for Claude Code

**Update `scripts/create_story_structure.sh` to:**
1. Create a `chapters/` folder with a `README.md` inside.
2. Create a `summaries/` folder with a `README.md` inside.
3. Confirm `logs/` remains reserved for ElevenLabs script logs and does not receive chapter recaps.

---

## 3. The plot skeleton — DECIDED (anatomy locked, per-story content pending)

Every story requires a locked 200-chapter skeleton before automated generation begins. The skeleton is the single source of truth for what happens, where, and when across the entire arc.

### What the skeleton must contain
- **Acts** — typically 4 acts of ~50 chapters.
- **Major events** — each tagged with target chapter range, dependencies, what it opens, what it closes, hard close-by deadline.
- **Open thread register** — every thread the skeleton opens has a mandatory close-by chapter.
- **World-event beats** — recurring background events independent of romance (Council sessions, news cycles, seasonal markers).
- **Romance milestones** — first private conversation, first commitment, first kiss, bond-share decision, etc.
- **Heat progression markers** — when each heat tier first appears.
- **Locations** — complete list of every location any chapter will use (this becomes `locations.md`). See Section 5.
- **Character list** — every named character with their role. Drives `files_to_create`.
- **`files_to_create`** — explicit list of every file path the script must create in Step 3a.

### Three-track structure
Every chapter must advance at least one of: romance, plot, world. The skeleton tags each event by track. Prevents the AI from collapsing 200 chapters into pure romance-on-repeat.

### Origin of the skeleton
- Story 1 (Alpha of Ashbrook): user provides event list. AI proposes chapter ranges. User approves.
- Stories 2–10: AI drafts skeleton from master catalog + bible. User reviews and approves.

---

## 4. Bibles, summaries, and chapter metadata — DECIDED

### Bible structure
- `bible/static.md` — consolidated static bible. World rules, permanent character facts. The AI MUST NEVER contradict this file. Read-only after Step 3b.
- `bible/world-building.md` — setting deep-dive (geography, politics, culture). Read-only after Step 3b.
- `bible/style-guide.md` — prose voice, tone, POV style. Read-only.
- `bible/pronunciation-guide.md` — phonetic notes for ElevenLabs. Read-only.
- `bible/heat_progression.md` — explicit ladder of what each chapter range allows. Read-only.
- `bible/no_go_list.md` — extracted from static bible into its own file because it is referenced every chapter. Read-only.
- `bible/voice_samples.md` — 3–5 locked paragraphs of example prose per POV character for voice consistency. Read-only.
- `bible/locations.md` — complete locked world map. Read-only (see Section 5).
- `bible/plot_skeleton.md` — the 200-chapter event spine. Read-only after approval.
- `bible/characters/<slug>/static.md` — permanent character facts.
- `bible/characters/<slug>/evolving.md` — current state. **UPDATED EVERY CHAPTER** by the chapter-generation AI.

### Why split static vs evolving per character
Static facts (eye color, height, family of origin) never change. Evolving facts (current location, current emotional state, current relationships, beliefs about other characters) change as the story progresses. Splitting means the chapter-generation AI only loads and updates the evolving file for characters who appear in this chapter. Cheaper, cleaner, less drift.

### Summaries folder
- `summaries/chapter_001_summary.md` — one file per chapter, written by the chapter-generation AI after the chapter is finalised.
- `summaries/master_summary.md` — rolling compressed summary of all older chapters per the master catalog system. Created at the second batch boundary.
- Filename is just chapter number. No dates in filenames. Creation timestamp lives inside the file as frontmatter (`created_at: YYYY-MM-DD`).

### Chapter metadata file
Every chapter has a companion metadata JSON file:

```
chapters/chapter_001.md
chapters/chapter_001.meta.json
```

Metadata contains: `heat_level`, `content_warnings`, `age_restriction`, `spice_tag`, `word_count`, `release_date`, `audio_url`, `generation_timestamp`.

Website reads this JSON to decide age gates and content warnings. GitHub Action reads this JSON for publish. Audio pipeline writes `audio_url` back to this JSON when MP3 is ready.

---

## 5. Locations — DECIDED

Locations are static. The AI cannot invent new ones during chapter generation. This solves the LLM teleportation problem (observed failure mode: AI-written characters skip between distant places without acknowledging travel during active movement scenes).

### How locations.md is built
- Every location any chapter will use is listed in the approved skeleton.
- During Step 3b, the file-population AI writes `bible/locations.md` from the skeleton's locations section.
- Each location entry includes adjacencies and approximate travel times in plain English prose (not JSON, not coordinates).
- After Step 3b, the file is **READ-ONLY** for the automated pipeline. The chapter-generation AI never writes to it.

### Why no coordinates, no node-graph
Coordinate tracking makes the teleport problem worse — LLMs are bad at spatial reasoning and will produce confident wrong numbers. Prose adjacency is denser, easier for the AI to absorb, and easier for a human to edit. Same information, simpler format.

### Why locations are STATIC, not extensible
If the AI is allowed to add new locations, it will, and it will invent fake side streets to get characters where the plot wants them. By locking the location set at story start, the AI is structurally prevented from this.

If a future chapter genuinely needs a new location, the human edits `locations.md` manually. That is the only path.

### The 3-step writing workflow (positive instructions only)

**Before writing any scene, the chapter-generation AI follows these three steps in order:**

1. Read `bible/locations.md` in full.
2. Choose scene locations from this file. For each location used, identify it by name and note adjacencies and travel times.
3. Write the scene using only these chosen locations. When characters move, use the adjacency notes to keep distances and routes consistent.

*Phrased positively. LLMs follow positive instructions reliably; prohibitive rules fail ~10% of the time and silently break.*

---

## 6. Chapter-generation skill design — DECIDED

The chapter-generation prompt is the brain of the weekly pipeline. Designed to keep rules separate from prose generation, so rule-language does not leak into the chapter.

### Two-phase generation
- **Phase 1 (planning):** AI reads all rules, bibles, locations.md, skeleton entry. Outputs a SHORT plan — locations chosen, characters present, POV, beat sequence. No prose.
- **Phase 2 (writing):** AI receives the plan as input. Rules are NOT in context. AI writes prose only.
- This prevents the LLM tendency to over-explain rules in fiction output.

### Why LLMs over-explain rules in their output
Three reasons: (1) training data bias toward tutorial-style explanation — LLMs are trained heavily on instructional content and the pattern of 'explain what you're doing while you do it' leaks into fiction; (2) rules sitting in context have non-zero token probability during prose generation; (3) LLMs cannot fully separate 'instructions to follow' from 'content to write about'. Mitigation is the two-phase pattern above plus self-check enforcement at the end.

### Anti-leakage rules in the writing phase
- "Do not reference rules, files, locations.md, bibles, or any system inputs in the chapter prose. Write fiction only."
- Self-check step at end of generation scans for meta-language ("adjacency", "locations.md", "the rule", "per the bible") and flags any occurrence.

### Inputs to the chapter-generation skill (every run)
- `master_catalog.md` (project-level)
- This story's `bible/static.md`, `world-building.md`, `style-guide.md`, `pronunciation-guide.md`
- This story's `bible/heat_progression.md`
- This story's `bible/no_go_list.md`
- This story's `bible/voice_samples.md`
- This story's `bible/locations.md`
- This story's `bible/plot_skeleton.md` (full file)
- All `bible/characters/<slug>/static.md` and `evolving.md` files
- This story's `summaries/master_summary.md` (if exists)
- Last 1–2 `summaries/chapter_NNN_summary.md` files for immediate continuity

### Outputs of the chapter-generation skill (every run)
- `chapters/chapter_NNN.md` — the prose
- `chapters/chapter_NNN.meta.json` — the metadata
- `narration/chapter_NNN_audio_script.md` — audio-tagged version using existing audio_script_preparation_prompt
- `summaries/chapter_NNN_summary.md` — the recap
- Updated `bible/characters/<slug>/evolving.md` for every character who appeared
- `flags/chapter_NNN_flags.json` — self-check output (empty if clean)

---

## 7. Heat progression and content tagging — DECIDED

### Heat rule (Story 1 default; configurable per story)
- Chapters 1–150: medium heat. Allowed: fingering, kissing, breast suckling, hand jobs, clothed friction to climax. No penetration on page.
- Chapters 151–200: fully explicit. Open door. Everything allowed within the story's no-go list.

### Content tagging
- Heat level, content warnings, and age restriction are written by the chapter-generation AI into `chapters/chapter_NNN.meta.json`.
- GitHub Action does NOT read chapter prose to determine tags. It reads the `.meta.json` file the AI produced.
- Website reads the same `.meta.json` to render warnings and gates.

---

## 8. Decision log

Running log of decisions. Each entry: what was decided, why it matters.

**D1 — Naming convention**
Roman is called "Alpha" universally. The word "senator" is dropped from the world. American political flavour comes from surrounding vocabulary (constituents, op-eds, the press pool, the opposition bloc, town hall, his record on human affairs) rather than from the title. Applies to all stories: characters use world-native titles; prose voice can deploy real-world political register where useful.

**D2 — Heat rule**
Chapters 1–150 medium heat (fingering, kissing, breast suckling, hand jobs, clothed friction to climax). Chapters 151–200 fully explicit, open door. Spice chapters tagged in JSON metadata.

**D3 — Tagging is the AI's job, not the script's**
Heat-level tags, age-restriction flags, content warnings live in `chapters/chapter_NNN.meta.json`, written by the chapter-generation AI. GitHub Actions only moves files; it does not read chapter content.

**D4 — Bible split**
One consolidated static bible (`bible/static.md`). Evolving bible split per character (`bible/characters/<slug>/evolving.md`). Evolving bibles update every chapter.

**D5 — Plot skeleton required per story**
Every story requires a locked 200-chapter skeleton before automated generation begins. Story 1 from user's event list. Stories 2–10 AI-drafted then user-approved.

**D6 — Human review policy**
No per-chapter human review during normal operation. Pre-launch skeleton approval is the human checkpoint per story. Approval gate can be added to the website later if quality falls below acceptable.

**D7 — Three-step process**
Skeleton approval → folder creation (script) → file creation (script reads skeleton's `files_to_create`) → file population (AI). Step 3 is split into 3a (deterministic, no tokens) and 3b (AI populates files).

**D8 — Folder rename**
Chapter recaps live in `summaries/`, not `logs/`. The `logs/` folder is reserved for ElevenLabs script logs. Avoids modifying existing ElevenLabs scripts.

**D9 — Chapter recap filename**
`chapter_NNN_summary.md` — chapter number only, no date in filename. Creation timestamp lives inside the file as frontmatter.

**D10 — Locations are static and read-only**
`bible/locations.md` is generated once during Step 3b from the approved skeleton's locations section. Read-only thereafter. The chapter-generation AI cannot add locations. New locations require human editing.

**D11 — No coordinates, no node-graph**
Locations use prose adjacency, not JSON or coordinates. LLMs are bad at spatial reasoning; coordinates make the teleport problem worse. Prose adjacency is denser and easier to absorb.

**D12 — Positive instructions over prohibitions**
All skill rules phrased as actions to take, not actions to avoid. LLMs follow positive instructions reliably; prohibitive rules fail ~10% of the time. Where prohibitions are unavoidable (no meta-language in prose), they are paired with self-check enforcement at the end of generation.

**D13 — Two-phase generation**
Chapter generation splits into planning phase (reads rules, outputs short plan) and writing phase (writes prose with plan as input, rules NOT in context). Prevents rule-language leakage into fiction.

**D14 — Skeleton lists files_to_create**
The approved skeleton includes an explicit `files_to_create` section listing every character bible path needed. The file creation script reads this section deterministically. No AI tokens are spent on file creation itself.

**D15 — Motion problem only; memory problem deferred**
The location strategy specifically addresses LLM teleportation during active movement scenes (character walking past landmark A, then suddenly at distant landmark C, then back at A). Memory failures between chapters (forgetting which room characters ended in) are not addressed by tooling — not observed in practice and the cost of guarding outweighs the benefit.

---

## 9. Open questions

- Where do generated MP3 files get stored (Cloudflare R2 / S3 / other)?
- Which LLM API does the pipeline call (Anthropic / OpenAI / both)?
- What is the website stack (for the publish step)?
- Release cadence — confirm Fridays, confirm timezone.
- Self-check failure protocol — if `flags/chapter_NNN_flags.json` is non-empty, does the chapter still publish, or does it queue for human review?

---

## 10. Current repository state (snapshot)

Reference snapshot of the repo at the time of writing — used as context for the next phase (Claude Code prompts).

### Top-level files
```
.gitignore
README.md
ai_script_preparer.py
audio
audio_workflow.py
config/voice_roles.json
```

### Existing prompts
```
prompts/audio_script_preparation_prompt.md
```

### Existing scripts
```
scripts/create_story_structure.sh
scripts/run_audio.sh
```

### Stories folder
```
stories/master_catalog.md
stories/the-alpha-of-ashbrook/  — 9 chapters drafted, bible present, narration scripts present
stories/the-wolfless-princess/ — bible present, no chapters yet
```

### Tests
```
tests/test_audio_workflow.py
```

### Gap analysis — what's missing for the new pipeline
- `scripts/create_story_structure.sh` needs updating: add `chapters/`, add `summaries/`, ensure `logs/` stays reserved for ElevenLabs.
- New script needed: `scripts/populate_story_files.py` — runs after skeleton approval, reads `files_to_create`, creates empty placeholders.
- New prompts needed: `prompts/skeleton_generation_prompt.md`, `prompts/file_population_prompt.md`, `prompts/chapter_generation_prompt.md`, `prompts/self_check_prompt.md`.
- New folder needed inside each story: `summaries/`.
- Existing 9 chapters of Story 1 need migrating into the new structure (write `summaries/chapter_NNN_summary.md` for each, back-populate character evolving bibles).

---

## 11. Next steps

1. Write all required prompts (skeleton, file population, chapter generation, self-check) — next session.
2. Write the Claude Code prompt to: update `create_story_structure.sh`, write `populate_story_files.py`, and migrate Story 1 chapters 1–9 into the new structure.
3. Run the full pipeline manually on Story 1 (Alpha of Ashbrook) as the pilot — skeleton, populate, generate chapter 10.
4. Once pilot is stable, build the GitHub Action for the weekly cadence.
5. Once GitHub Action is stable, integrate ElevenLabs and website push.
6. Once Story 1 end-to-end is working, roll out to Stories 2–10.
