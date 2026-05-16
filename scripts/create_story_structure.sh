#!/usr/bin/env bash
set -euo pipefail

# create_story_structure.sh
#
# Creates a self-contained story production folder for the story-audio-generator repo.
#
# Usage:
#   bash scripts/create_story_structure.sh "Silver Footfalls"
#   bash scripts/create_story_structure.sh silver-footfalls
#
# Output:
#   stories/silver-footfalls/
#     story.json
#     source/
#     chapters/
#     bible/
#     narration/
#     logs/
#   output/<story-slug>/

if [ "$#" -lt 1 ]; then
  echo "Error: Please provide a story title or slug."
  echo "Usage: bash scripts/create_story_structure.sh \"Story Title\""
  exit 1
fi

RAW_NAME="$*"

# Convert the supplied title into a safe lowercase slug:
# "Silver Footfalls!" -> "silver-footfalls"
slugify() {
  echo "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g' \
    | sed -E 's/^-+|-+$//g'
}

STORY_SLUG="$(slugify "$RAW_NAME")"

if [ -z "$STORY_SLUG" ]; then
  echo "Error: Could not create a valid folder slug from: $RAW_NAME"
  exit 1
fi

REPO_ROOT="$(pwd)"
STORIES_DIR="$REPO_ROOT/stories"
STORY_DIR="$STORIES_DIR/$STORY_SLUG"

if [ -e "$STORY_DIR" ]; then
  echo "Error: Story folder already exists:"
  echo "$STORY_DIR"
  exit 1
fi

mkdir -p "$STORY_DIR/source"
mkdir -p "$STORY_DIR/chapters"
mkdir -p "$STORY_DIR/bible"
mkdir -p "$STORY_DIR/narration"
mkdir -p "$STORY_DIR/logs"
mkdir -p "$REPO_ROOT/output/$STORY_SLUG"

cat > "$STORY_DIR/story.json" <<EOF
{
  "slug": "$STORY_SLUG",
  "title": "$RAW_NAME",
  "status": "draft",
  "commercialUse": true,
  "sourceManuscript": "source/$STORY_SLUG.docx",
  "chapterPattern": "chapter_###",
  "defaultNarrator": "",
  "voiceProfile": "default",
  "notes": "Place the source manuscript in source/. Place chapter files in chapters/. Place story planning files in bible/."
}
EOF

cat > "$STORY_DIR/bible/README.md" <<EOF
# $RAW_NAME Bible

Put story-specific planning documents here.

Suggested files to add manually:
- characters.docx
- world.docx
- style-guide.docx
- plot-outline.docx
- voice-notes.docx
- pronunciation-guide.md
- content-warnings.md
- continuity-notes.md

This folder is for source/planning material only. The generator does not create story content.
EOF

cat > "$STORY_DIR/source/README.md" <<EOF
# Source manuscript

Put the full story manuscript here.

Expected default source file:
$STORY_SLUG.docx

Accepted source formats:
- .docx
- .txt
- .md
EOF

cat > "$STORY_DIR/chapters/README.md" <<EOF
# Chapter files

Optional folder for chapter-level source files.

Recommended naming:
- chapter_001.docx
- chapter_002.docx
- chapter_003.docx

If chapter files exist, the generator should prefer them over the full manuscript in source/.
EOF

cat > "$STORY_DIR/narration/README.md" <<EOF
# Narration scripts

Prepared audio-drama scripts go here.

Recommended naming:
- chapter_001_audio_script.md
- chapter_002_audio_script.md
- chapter_003_audio_script.md

If a narration script exists, the generator should use it instead of preparing one from the source/chapter document.
EOF

if [ ! -e "$REPO_ROOT/output/README.md" ]; then
  cat > "$REPO_ROOT/output/README.md" <<EOF
# Generated audio output

Generated MP3 files and metadata are grouped by story slug. The generator writes chapter files directly inside each story-named output folder instead of creating per-chapter folders.

Recommended naming:
- $STORY_SLUG/chapter_001.mp3
- $STORY_SLUG/chapter_001_metadata.json
- $STORY_SLUG/chapter_002.mp3
- $STORY_SLUG/chapter_002_metadata.json

The generator should not overwrite existing MP3s unless --force is passed.
EOF
fi

cat > "$STORY_DIR/logs/README.md" <<EOF
# Logs

Generation logs go here.

Recommended files:
- preparation.log
- generation.log
- errors.log
EOF

echo "Created story structure:"
echo "$STORY_DIR"
echo
echo "Next steps:"
echo "1. Put your source manuscript in: stories/$STORY_SLUG/source/$STORY_SLUG.docx"
echo "2. Add character/style/plot files to: stories/$STORY_SLUG/bible/"
echo "3. Generated audio will be written to: output/$STORY_SLUG/"
echo "4. From repo root, run:"
echo "   audio status $STORY_SLUG"
