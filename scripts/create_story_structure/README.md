# `./create_story` — Story folder scaffolder

Creates a self-contained story production folder under `stories/<story-slug>/` with the standard subfolders (`source/`, `chapters/`, `bible/`, `narration/`, `logs/`), a starter `story.json`, and per-folder READMEs that describe what to put inside. The underlying script is `create_story_structure.sh`; the repository-root `./create_story` entrypoint forwards to it.

For the audiobook CLI that consumes these folders, see [`../audio/README.md`](../audio/README.md). For the top-level overview, see [`../../README.md`](../../README.md).

## Usage

Run from the repository root:

```bash
./create_story "Story Title"
./create_story story-slug
```

The argument is slugified before use: `"Silver Footfalls!"` becomes `silver-footfalls`. If the resulting story folder already exists, the script stops with an error rather than overwriting anything.

## What it creates

```text
stories/<story-slug>/
  story.json                # starter metadata: slug, title, status, defaults
  source/        + README.md
  chapters/      + README.md
  bible/         + README.md
  narration/     + README.md
  logs/          + README.md
output/<story-slug>/        # only created if missing
output/README.md            # only created if missing
```

The script never writes story content. It only creates the directory layout and per-folder READMEs so the rest of the workflow (`./audio prepare`, `./audio generate`, `./audio build`) has a known place to read from and write to.

## Next steps after running

1. Put your source manuscript in `stories/<story-slug>/source/<story-slug>.docx` (or `.txt` / `.md`).
2. Add character / style / plot files to `stories/<story-slug>/bible/`.
3. From the repository root, run `./audio status <story-slug>` to see what is missing.
