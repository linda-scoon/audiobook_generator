# Generated audio output

Generated MP3 files and generation metadata are grouped by story slug. Chapter files live directly inside each story folder, for example:

- `the-alpha-of-ashbrook/chapter_001.mp3`
- `the-alpha-of-ashbrook/chapter_001_metadata.json`
- `the-alpha-of-ashbrook/chapter_002.mp3`

The generator intentionally avoids per-chapter folders to keep the output tree shallow. Existing MP3s are not overwritten unless `--force` is passed.
