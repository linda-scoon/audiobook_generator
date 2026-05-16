# audiobook_generator

Local story-audio production workspace for preparing prose into tagged audio-drama scripts and generating MP3 output from the repository root.

## Story folder layout

Stories live under `stories/` and are addressed by their real folder slug, for example `stories/silver-footfalls/` or `stories/dark-house-guest/`.

Each story folder uses this layout:

```text
stories/<story-slug>/
  story.json
  source/      # untouched full manuscript (.md, .txt, .docx)
  chapters/    # clean split chapter source files, e.g. chapter_001.md
  bible/       # character bibles, pronunciation notes, style guides
  narration/   # prepared audio-drama scripts, e.g. chapter_001_audio_script.md
  logs/        # preparation and generation logs

output/
  <story-slug>/  # generated MP3s and generation metadata for that story
```

`chapters/` files preserve original story text split by chapter. `narration/` files contain the same story content with audio tags such as `[NARRATOR]`, `[FMC]`, `[MMC: low, controlled]`, `[WOLF_OR_MONSTER]`, and `[SFX: sound effect description]`.

## Recommended one-command wrapper

If you want one command that checks status, fills missing reusable voice IDs when needed, validates voices, and then runs the build, use the wrapper script at `scripts/run_audio.sh`.

The wrapper is intended to reduce setup friction while still protecting against unnecessary API usage:

- It requires `--story` unless you explicitly pass `--all-stories`, so you do not accidentally process every story.
- It does not source `.env`; the `./audio` CLI loads simple `.env` values itself.
- It skips voice setup for `--prepare-only`, because no ElevenLabs MP3 generation is needed.
- It runs `voices auto-assign` only when required voice IDs are missing or blank.
- It validates only the selected story when `--story` is provided.
- It keeps the built-in review pause unless you pass `--yes`.
- It prints the exact commands it will run before it runs them.
- It calls the repo entrypoint through a tested Python command, which avoids Windows Git Bash `python3`/Microsoft Store alias problems.

### Wrapper command format

Run from the repository root:

```bash
bash scripts/run_audio.sh --mode prepared|unprepared|auto --story STORY_SLUG [options]
bash scripts/run_audio.sh --mode prepared|unprepared|auto --all-stories [options]
```

Required:

```text
--mode prepared|unprepared|auto
--story STORY_SLUG       Process one story.
    OR
--all-stories            Explicitly process every story under stories/.
```

Options:

```text
--chapter NUMBER         Process one chapter only, e.g. 1.
--yes                    Skip the review pause where supported.
--force                  Regenerate existing outputs. Can spend credits again.
--prepare-only           Prepare narration scripts but do not generate MP3s.
--skip-voice-setup       Skip voice auto-assign/validate checks.
--no-status              Do not show ./audio status before running.
--dry-run                Print what would run, but do not run setup/build.
-h, --help               Show wrapper help.
```

### Safest first run

Use `--dry-run` first if you want to see what the wrapper would do without making setup, AI, or ElevenLabs calls. This is also a quick way to confirm the wrapper found a working Python command:

```bash
bash scripts/run_audio.sh --story the-alpha-of-ashbrook --mode prepared --chapter 1 --dry-run
```

### Prepared narration scripts already exist

If `stories/<story-slug>/narration/chapter_001_audio_script.md` already exists and contains valid tags, use `--prepared`:

```bash
bash scripts/run_audio.sh --story the-alpha-of-ashbrook --mode prepared --chapter 1
```

This does not call the AI preparation API. It may call ElevenLabs TTS if the MP3 output is missing and you are not using `--prepare-only`.

### Prose needs AI preparation, but you want to review before MP3 generation

This is the recommended low-cost workflow for unprepared prose:

```bash
bash scripts/run_audio.sh --story the-alpha-of-ashbrook --mode unprepared --chapter 1 --prepare-only
```

Then review the generated narration script:

```text
stories/the-alpha-of-ashbrook/narration/chapter_001_audio_script.md
```

After review, generate the MP3 from the prepared script:

```bash
bash scripts/run_audio.sh --story the-alpha-of-ashbrook --mode prepared --chapter 1
```

### One-step prepare-and-generate

If you want one command to prepare prose and then continue into MP3 generation, pass `--yes`:

```bash
bash scripts/run_audio.sh --story the-alpha-of-ashbrook --mode unprepared --chapter 1 --yes
```

Use this carefully. `--yes` can skip the review pause after AI preparation and continue into ElevenLabs generation.

### Auto mode

`--auto` inspects files locally first. It only calls AI preparation for files that do not look like prepared audio-drama scripts:

```bash
bash scripts/run_audio.sh --story the-alpha-of-ashbrook --mode auto --chapter 1
```

Use `--auto` carefully on large stories. If you are unsure, combine it with `--prepare-only` first:

```bash
bash scripts/run_audio.sh --story the-alpha-of-ashbrook --mode auto --chapter 1 --prepare-only
```

### Process all stories intentionally

The wrapper will not process every story unless you explicitly pass `--all-stories`:

```bash
bash scripts/run_audio.sh --all-stories --mode prepared
```

For cost control, avoid `--all-stories` with `--unprepared`, `--auto`, `--yes`, or `--force` unless you really intend to process everything.

### Cost-control tips

- Prefer `--story` and `--chapter` while testing.
- Prefer `--prepare-only` before generating MP3s from newly prepared prose.
- Avoid `--yes` until you are comfortable with the generated narration format.
- Avoid `--force` unless you intentionally want to regenerate existing narration scripts or MP3s.
- Use `--dry-run` to inspect the planned commands before spending API credits.
- Use `--prepared` whenever narration scripts already contain valid speaker tags.

## Root commands

All commands are intended to be run from the repository root:

```bash
./audio status [story]
./audio prepare [story] (--prepared | --unprepared | --auto) [--chapter N] [--prepare-only] [--force]
./audio generate [story] [--chapter N] [--force]
./audio build [story] (--prepared | --unprepared | --auto) [--yes] [--chapter N] [--force]
./audio voices list
./audio voices auto-assign
./audio voices validate [story]
./audio voices preview --yes
```

If `[story]` is omitted, story commands operate on every folder under `stories/`. Story selectors may be slugs or title-like strings; title-like input is slugified before lookup.

## Reusable voice roles

The workflow uses reusable voice-role labels rather than one voice per fictional character. Narration scripts must use the supported role labels directly; character-name tags such as `[ELENA]` or `[ROMAN]` are intentionally not supported.

Voice IDs are stored in `config/voice_roles.json`:

```json
{
  "NARRATOR": "",
  "FMC": "",
  "MMC": "",
  "DEFAULT_FEMALE": "",
  "DEFAULT_MALE": "",
  "ADULT_FEMALE_1": "",
  "ADULT_FEMALE_2": "",
  "ADULT_MALE_1": "",
  "ADULT_MALE_2": "",
  "OLDER_FEMALE": "",
  "OLDER_MALE": "",
  "TEEN_FEMALE": "",
  "TEEN_MALE": "",
  "CHILD_FEMALE": "",
  "CHILD_MALE": "",
  "WOLF_OR_MONSTER": ""
}
```

Each value must be a real ElevenLabs `voice_id`. MP3 generation fails safely before calling ElevenLabs if a required role is missing, if any required voice ID is blank, or if a narration script contains an unknown speaker label.

Useful voice commands:

- `./audio voices list` calls the ElevenLabs List Voices API and prints available voice names and IDs. It does not spend generation credits.
- `./audio voices auto-assign` calls the ElevenLabs List Voices API, fills blank role IDs in `config/voice_roles.json`, and preserves existing saved IDs on later runs. It does not spend generation credits.
- `./audio voices validate` checks that all required roles exist, all required role IDs are non-empty, and narration scripts only use known role labels. It does not call generation.
- `./audio voices preview --yes` generates a short sample MP3 per role and spends ElevenLabs generation credits; without `--yes`, it stops with a warning.

## Preparation modes

Preparation mode is explicit on commands that may prepare narration scripts:

- `--prepared`: inputs already contain audio-drama tags. The tool validates locally and does not call an AI preparation API.
- `--unprepared`: inputs are prose and need AI preparation after all local validation passes.
- `--auto`: the tool inspects files locally first. AI is called only for files that do not appear to contain enough valid audio-drama blocks.

The explicit mode requirement prevents accidental paid AI preparation calls. Before any AI call, the tool validates story resolution, input existence, supported extension, readability, non-empty content, output overwrite safety, and prepared/unprepared consistency.

To prepare one unprepared chapter without generating MP3 audio:

```bash
./audio prepare <story> --chapter 1 --unprepared --prepare-only
```

This creates `stories/<story-slug>/narration/chapter_001_audio_script.md` and does not call ElevenLabs.

## Preparation prompt

The reusable prompt for converting normal prose into tagged narration scripts lives at:

```text
prompts/audio_script_preparation_prompt.md
```

The preparation module reads this file at runtime and sends that prompt plus the chapter text to the selected AI provider. If the prompt file is missing or empty, preparation stops with a clear error. Edit this file to control how unprepared prose is converted into the required voice-role narration format.

## Build order

For each story/chapter, the workflow is:

1. Use `narration/chapter_###_audio_script.md` if it exists.
2. Otherwise prepare from `chapters/chapter_###.md`, `.txt`, or `.docx`.
3. Otherwise split a single manuscript from `source/` into clean chapter files, then prepare narration scripts.
4. Generate MP3s into the repo-root `output/<story-slug>/` folder only after narration scripts exist and `config/voice_roles.json` contains non-blank IDs for all required roles. Chapter MP3s and metadata stay directly in that story-named folder; the workflow intentionally avoids per-chapter folders to keep the tree shallow.

Existing chapter files, narration scripts, and MP3s are skipped unless `--force` is passed. `audio status` reports missing and stale artifacts and recommends the next command.

## Environment variables

AI preparation supports OpenAI or Anthropic:

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
AI_PREPARATION_PROVIDER=openai  # or anthropic
```

MP3 generation and voice management use ElevenLabs:

```bash
ELEVENLABS_API_KEY=...
ELEVENLABS_MODEL_ID=eleven_multilingual_v2  # optional
```

You can export those values in your shell or put them in a repo-root `.env` file. The CLI automatically loads simple `KEY=VALUE` lines from `.env` at startup, without overwriting variables that are already exported in your shell. `.env` is ignored by git so local API keys are not committed.

`ELEVENLABS_VOICE_ID` is not used. Voice IDs are resolved by role from `config/voice_roles.json`.

API keys are only required when paid work, AI preparation, or ElevenLabs account lookup is actually needed. Status, local validation, and voice-role JSON checks do not spend generation credits.
