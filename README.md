# audiobook_generator

Local story-audio production workspace for preparing prose into tagged audio-drama scripts and generating MP3 output with ElevenLabs.

This README is the map of the repository: it explains what each command does in one sentence and points to the detailed README for that command. There is no operational detail here on purpose — that lives next to each script.

## Quick start

From the repository root:

```bash
./create_story "Silver Footfalls"     # scaffold a new story folder
./audio status                        # see what's missing for every story
./run_audio --story silver-footfalls --mode unprepared --chapter 1 --prepare-only
```

Then review the generated narration script and rerun without `--prepare-only` to produce the MP3.

## Repository layout

```text
.
├── audio                # root command → scripts/audio/audio_workflow.py
├── run_audio            # root command → scripts/run_audio/run_audio.sh
├── create_story         # root command → scripts/create_story_structure/create_story_structure.sh
├── config/              # voice_roles.json and other shared configuration
├── prompts/             # AI preparation prompt(s) read at runtime
├── stories/             # one folder per story, with source/chapters/narration/output
├── scripts/             # the actual implementation of each root command (one folder per script)
│   ├── audio/
│   ├── run_audio/
│   └── create_story_structure/
├── tests/               # pytest suite for the audio workflow
└── docs/                # longer-form design / spec documents
```

Stories live under `stories/<story-slug>/` and are addressed by slug. The detailed per-story folder layout is documented in [`scripts/audio/README.md`](scripts/audio/README.md).

## Commands callable from the repository root

Each command below is a thin entrypoint at the repository root that forwards to the real script under `scripts/`. See the linked README for full usage, options, and examples.

### `./audio`

The main audiobook workflow CLI. It exposes subcommands to check workflow status (`status`), prepare prose into tagged narration scripts (`prepare`), generate MP3s from prepared scripts via ElevenLabs (`generate`), do both end-to-end (`build`), and manage reusable voice-role assignments (`voices list|auto-assign|validate|preview`); preparation modes (`--prepared` / `--unprepared` / `--auto`) are explicit to prevent accidental paid AI calls.

Detailed docs: [`scripts/audio/README.md`](scripts/audio/README.md)

### `./run_audio`

A safer one-command bash wrapper around `./audio build` that prints what it will do, requires `--story` unless you explicitly pass `--all-stories`, runs voice auto-assign and validation only when needed, skips voice setup entirely for `--prepare-only`, and supports `--dry-run` so you can preview the planned commands before spending any AI or ElevenLabs credits.

Detailed docs: [`scripts/run_audio/README.md`](scripts/run_audio/README.md)

### `./create_story`

Scaffolds a new story production folder under `stories/<slug>/` with the standard `source/`, `chapters/`, `bible/`, `narration/`, and `logs/` subfolders, a starter `story.json`, and per-folder READMEs explaining what to put inside; it slugifies the title argument and refuses to overwrite an existing story folder.

Detailed docs: [`scripts/create_story_structure/README.md`](scripts/create_story_structure/README.md)

## Configuration

- `config/voice_roles.json` — maps reusable role labels (`NARRATOR`, `FMC`, `MMC`, etc.) to real ElevenLabs `voice_id` values. The `./audio voices auto-assign` command fills blank entries from your ElevenLabs account.
- `prompts/audio_script_preparation_prompt.md` — the system prompt the AI preparer sends together with chapter prose. Edit it to control how unprepared prose is converted into the required voice-role narration format.
- `.env` (optional, git-ignored) — `KEY=VALUE` lines loaded automatically by `./audio`. See the [audio CLI README](scripts/audio/README.md#environment-variables) for required keys (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, optional `ELEVENLABS_MODEL_ID`, optional `AI_PREPARATION_PROVIDER`).

## Documentation

Longer-form design and specification documents live in [`docs/`](docs/):

- [`docs/AI_Story_Pipeline_Spec.md`](docs/AI_Story_Pipeline_Spec.md) — working spec for the autonomous chapter-generation pipeline.

## Development

The audiobook CLI is plain Python with no third-party runtime dependencies; it talks to OpenAI / Anthropic / ElevenLabs directly via `urllib`. Tests use `pytest`:

```bash
pytest tests/
```

`tests/conftest.py` puts `scripts/audio/` on `sys.path` so the test modules can `import audio_workflow` and `from ai_script_preparer import ...` the same way the root `./audio` entrypoint does.

## License & usage

This is a personal production workspace. Generated narration scripts and MP3s under `stories/*/output/` are git-ignored; only source manuscripts, chapter splits, and tooling are versioned.
