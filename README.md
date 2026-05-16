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
  output/      # generated MP3s and generation metadata
  logs/        # preparation and generation logs
```

`chapters/` files preserve original story text split by chapter. `narration/` files contain the same story content with audio tags such as `[NARRATOR]`, `[FMC]`, `[MMC: low, controlled]`, `[WOLF_OR_MONSTER]`, and `[SFX: sound effect description]`.

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
4. Generate MP3s into `output/` only after narration scripts exist and `config/voice_roles.json` contains non-blank IDs for all required roles.

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
