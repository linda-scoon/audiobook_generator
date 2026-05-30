# `./run_audio` — Safer one-command audio build wrapper

A bash wrapper around `./audio build` that adds cost-control defaults: it checks status, fills missing reusable voice IDs only when needed, validates voices, prints the exact commands it will run, and then runs the build. The underlying script is `run_audio.sh`; the repository-root `./run_audio` entrypoint forwards to it.

For the underlying CLI it drives, see [`../audio/README.md`](../audio/README.md). For the top-level overview, see [`../../README.md`](../../README.md).

## Why this wrapper exists

It is intended to reduce setup friction while still protecting against unnecessary API usage:

- It requires `--story` unless you explicitly pass `--all-stories`, so you do not accidentally process every story.
- It does not source `.env`; the `./audio` CLI loads simple `.env` values itself.
- It skips voice setup for `--prepare-only`, because no ElevenLabs MP3 generation is needed.
- It runs `voices auto-assign` only when required voice IDs are missing or blank.
- It validates only the selected story when `--story` is provided.
- It keeps the built-in review pause unless you pass `--yes`.
- It prints the exact commands it will run before it runs them.
- It calls the repo entrypoint through a tested Python command, which avoids Windows Git Bash `python3`/Microsoft Store alias problems.

## Command format

Run from the repository root:

```bash
./run_audio --mode prepared|unprepared|auto --story STORY_SLUG [options]
./run_audio --mode prepared|unprepared|auto --all-stories [options]
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

## Safest first run

Use `--dry-run` first if you want to see what the wrapper would do without making setup, AI, or ElevenLabs calls. This is also a quick way to confirm the wrapper found a working Python command:

```bash
./run_audio --story the-alpha-of-ashbrook --mode prepared --chapter 1 --dry-run
```

## Prepared narration scripts already exist

If `stories/<story-slug>/narration/chapter_001_audio_script.md` already exists and contains valid tags, use `--mode prepared`:

```bash
./run_audio --story the-alpha-of-ashbrook --mode prepared --chapter 1
```

This does not call the AI preparation API. It may call ElevenLabs TTS if the MP3 output is missing and you are not using `--prepare-only`.

## Prose needs AI preparation, but you want to review before MP3 generation

This is the recommended low-cost workflow for unprepared prose:

```bash
./run_audio --story the-alpha-of-ashbrook --mode unprepared --chapter 1 --prepare-only
```

Then review the generated narration script:

```text
stories/the-alpha-of-ashbrook/narration/chapter_001_audio_script.md
```

After review, generate the MP3 from the prepared script:

```bash
./run_audio --story the-alpha-of-ashbrook --mode prepared --chapter 1
```

## One-step prepare-and-generate

If you want one command to prepare prose and then continue into MP3 generation, pass `--yes`:

```bash
./run_audio --story the-alpha-of-ashbrook --mode unprepared --chapter 1 --yes
```

Use this carefully. `--yes` can skip the review pause after AI preparation and continue into ElevenLabs generation.

## Auto mode

`--mode auto` inspects files locally first. It only calls AI preparation for files that do not look like prepared audio-drama scripts:

```bash
./run_audio --story the-alpha-of-ashbrook --mode auto --chapter 1
```

Use `--mode auto` carefully on large stories. If you are unsure, combine it with `--prepare-only` first:

```bash
./run_audio --story the-alpha-of-ashbrook --mode auto --chapter 1 --prepare-only
```

## Process all stories intentionally

The wrapper will not process every story unless you explicitly pass `--all-stories`:

```bash
./run_audio --all-stories --mode prepared
```

For cost control, avoid `--all-stories` with `--mode unprepared`, `--mode auto`, `--yes`, or `--force` unless you really intend to process everything.

## Cost-control tips

- Prefer `--story` and `--chapter` while testing.
- Prefer `--prepare-only` before generating MP3s from newly prepared prose.
- Avoid `--yes` until you are comfortable with the generated narration format.
- Avoid `--force` unless you intentionally want to regenerate existing narration scripts or MP3s.
- Use `--dry-run` to inspect the planned commands before spending API credits.
- Use `--mode prepared` whenever narration scripts already contain valid speaker tags.
