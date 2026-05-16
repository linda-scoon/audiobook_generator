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
  bible/       # character bibles, voice notes, pronunciation notes, style guides
  narration/   # prepared audio-drama scripts, e.g. chapter_001_audio_script.md
  output/      # generated MP3s and generation metadata
  logs/        # preparation and generation logs
```

`chapters/` files preserve original story text split by chapter. `narration/` files contain the same story content with audio tags such as `[NARRATOR]`, `[CHARACTER_NAME: emotional direction]`, and `[SFX: sound effect description]`.

## Root commands

All commands are intended to be run from the repository root:

```bash
./audio status [story]
./audio prepare [story] (--prepared | --unprepared | --auto) [--force]
./audio generate [story] [--force]
./audio build [story] (--prepared | --unprepared | --auto) [--yes] [--force]
```

If `[story]` is omitted, the command operates on every folder under `stories/`. Story selectors may be slugs or title-like strings; title-like input is slugified before lookup.

## Preparation modes

Preparation mode is explicit on commands that may prepare narration scripts:

- `--prepared`: inputs already contain audio-drama tags. The tool validates locally and does not call an AI preparation API.
- `--unprepared`: inputs are prose and need AI preparation after all local validation passes.
- `--auto`: the tool inspects files locally first. AI is called only for files that do not appear to contain enough valid audio-drama blocks.

The explicit mode requirement prevents accidental paid AI preparation calls. Before any AI call, the tool validates story resolution, input existence, supported extension, readability, non-empty content, output overwrite safety, and prepared/unprepared consistency.

## Build order

For each story/chapter, the workflow is:

1. Use `narration/chapter_###_audio_script.md` if it exists.
2. Otherwise prepare from `chapters/chapter_###.md`, `.txt`, or `.docx`.
3. Otherwise split a single manuscript from `source/` into clean chapter files, then prepare narration scripts.
4. Generate MP3s into `output/` only after narration scripts exist.

Existing chapter files, narration scripts, and MP3s are skipped unless `--force` is passed. `audio status` reports missing and stale artifacts and recommends the next command.

## Environment variables

AI preparation supports OpenAI or Anthropic:

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
AI_PREPARATION_PROVIDER=openai  # or anthropic
```

MP3 generation uses ElevenLabs:

```bash
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
```

API keys are only required when paid work is actually needed.
