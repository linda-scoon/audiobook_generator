#!/usr/bin/env bash
set -Eeuo pipefail

# run_audio.sh
#
# Safer one-command wrapper for audiobook_generator.
# Run from the repository root via the ./run_audio entrypoint, or invoke this
# script directly with: bash scripts/run_audio/run_audio.sh
#
# Why this wrapper runs `python audio` instead of `./audio`:
#   On Windows Git Bash, the ./audio shebang may resolve to a broken python3
#   Microsoft Store alias even when `python` works. This wrapper tests Python
#   candidates and then calls the repo entrypoint through the working Python.
#
# Cost-control defaults:
#   - Requires --story unless --all-stories is explicitly passed.
#   - Does NOT source .env; ./audio's Python CLI loads simple .env values itself.
#   - Runs voice auto-assign only when voice IDs are missing/blank and MP3s may be generated.
#   - Skips voice setup entirely for --prepare-only, so ElevenLabs is not needed.
#   - Keeps the built-in review pause unless you pass --yes.
#   - Shows status before running unless --no-status is passed.

MODE=""
STORY=""
CHAPTER=""
YES=0
FORCE=0
PREPARE_ONLY=0
SKIP_VOICE_SETUP=0
ALL_STORIES=0
SHOW_STATUS=1
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage:
  ./run_audio --mode prepared|unprepared|auto --story STORY_SLUG [options]
  ./run_audio --mode prepared|unprepared|auto --all-stories [options]

Required:
  --mode prepared|unprepared|auto
  --story STORY_SLUG       Process one story.
      OR
  --all-stories            Explicitly process every story under stories/.

Options:
  --chapter NUMBER         Process one chapter only, e.g. 1.
  --yes                    Skip the review pause where supported.
  --force                  Regenerate existing outputs. Can spend credits again.
  --prepare-only           Prepare narration scripts but do not generate MP3s.
  --skip-voice-setup       Skip voice auto-assign/validate checks.
  --no-status              Do not show ./audio status before running.
  --dry-run                Print what would run, but do not run setup/build.
  -h, --help               Show this help.

Recommended low-cost workflow for unprepared prose:
  ./run_audio --story the-alpha-of-ashbrook --mode unprepared --chapter 1 --prepare-only
  # Review stories/the-alpha-of-ashbrook/narration/chapter_001_audio_script.md
  ./run_audio --story the-alpha-of-ashbrook --mode prepared --chapter 1

If you see a Windows/Microsoft Store Python alias error, make sure `python --version`
works in this shell. This wrapper intentionally uses the working Python command it finds.
USAGE
}

die() {
  echo "Error: $*" >&2
  exit 1
}

require_value() {
  local option="$1"
  local value="${2:-}"
  if [[ -z "$value" || "$value" == --* ]]; then
    die "$option requires a value."
  fi
}

find_python() {
  local candidate
  for candidate in python3 python py; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

voice_config_state() {
  "$PYTHON_CMD" - <<'PY'
import json
from pathlib import Path

required = [
    "NARRATOR",
    "FMC",
    "MMC",
    "DEFAULT_FEMALE",
    "DEFAULT_MALE",
    "ADULT_FEMALE_1",
    "ADULT_FEMALE_2",
    "ADULT_MALE_1",
    "ADULT_MALE_2",
    "OLDER_FEMALE",
    "OLDER_MALE",
    "TEEN_FEMALE",
    "TEEN_MALE",
    "CHILD_FEMALE",
    "CHILD_MALE",
    "WOLF_OR_MONSTER",
]

path = Path("config/voice_roles.json")

if not path.exists():
    print("MISSING")
    raise SystemExit(0)

try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("INVALID")
    raise SystemExit(0)

if not isinstance(data, dict):
    print("INVALID")
    raise SystemExit(0)

missing = [role for role in required if role not in data]
blank = [role for role in required if not str(data.get(role, "")).strip()]

if missing or blank:
    print("MISSING_OR_BLANK")
else:
    print("READY")
PY
}

print_command() {
  printf ' %q' "$@"
  echo
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      require_value "$1" "${2:-}"
      MODE="$2"
      shift 2
      ;;
    --story)
      require_value "$1" "${2:-}"
      STORY="$2"
      shift 2
      ;;
    --chapter)
      require_value "$1" "${2:-}"
      CHAPTER="$2"
      shift 2
      ;;
    --yes)
      YES=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --prepare-only)
      PREPARE_ONLY=1
      shift
      ;;
    --skip-voice-setup)
      SKIP_VOICE_SETUP=1
      shift
      ;;
    --all-stories)
      ALL_STORIES=1
      shift
      ;;
    --no-status)
      SHOW_STATUS=0
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$MODE" ]]; then
  usage
  die "--mode is required."
fi

if [[ "$MODE" != "prepared" && "$MODE" != "unprepared" && "$MODE" != "auto" ]]; then
  die "--mode must be prepared, unprepared, or auto."
fi

if [[ -n "$STORY" && "$ALL_STORIES" -eq 1 ]]; then
  die "Use either --story or --all-stories, not both."
fi

if [[ -z "$STORY" && "$ALL_STORIES" -eq 0 ]]; then
  usage
  die "--story is required unless you explicitly pass --all-stories."
fi

if [[ -n "$CHAPTER" && ! "$CHAPTER" =~ ^[0-9]+$ ]]; then
  die "--chapter must be a positive number, e.g. --chapter 1."
fi

if [[ ! -f "./audio" ]]; then
  die "Could not find ./audio. Run this script from the repository root."
fi

if [[ ! -d "./stories" ]]; then
  die "Could not find ./stories. Run this script from the repository root."
fi

PYTHON_CMD="$(find_python)" || die "Python 3.9+ was not found. In Git Bash, try: python --version. If that works, re-run this script from the same shell."
AUDIO_CMD=("$PYTHON_CMD" "audio")

echo
echo "Audio wrapper plan"
echo "=================="
echo "Python:        $PYTHON_CMD"
echo "Mode:          $MODE"
if [[ -n "$STORY" ]]; then
  echo "Story:         $STORY"
else
  echo "Story:         ALL STORIES"
fi
if [[ -n "$CHAPTER" ]]; then
  echo "Chapter:       $CHAPTER"
else
  echo "Chapter:       all available chapters"
fi
echo "Prepare only:  $([[ "$PREPARE_ONLY" -eq 1 ]] && echo yes || echo no)"
echo "Skip review:   $([[ "$YES" -eq 1 ]] && echo yes || echo no)"
echo "Force:         $([[ "$FORCE" -eq 1 ]] && echo yes || echo no)"
echo

echo "Cost notes"
echo "----------"
case "$MODE" in
  prepared)
    echo "- --prepared does not call the AI preparation API."
    ;;
  unprepared)
    echo "- --unprepared may call your AI preparation provider for chapters that need narration scripts."
    ;;
  auto)
    echo "- --auto inspects files locally first, but may call AI for files that do not look prepared."
    ;;
esac

if [[ "$PREPARE_ONLY" -eq 1 ]]; then
  echo "- --prepare-only is set, so this wrapper will not generate MP3s."
  echo "- Voice setup is skipped because ElevenLabs TTS is not needed for prepare-only."
else
  echo "- MP3 generation may call ElevenLabs TTS for missing outputs."
fi

if [[ "$YES" -eq 1 ]]; then
  echo "- --yes is set, so the review pause after AI preparation may be skipped."
else
  echo "- --yes is not set, so the built-in review pause remains enabled when AI preparation is used."
fi

if [[ "$FORCE" -eq 1 ]]; then
  echo "- WARNING: --force is set. Existing derived outputs may be regenerated, which can spend credits again."
fi

if [[ -z "$STORY" ]]; then
  echo "- WARNING: --all-stories is set. This can process many chapters."
fi

echo

if [[ "$SHOW_STATUS" -eq 1 ]]; then
  STATUS_CMD=("${AUDIO_CMD[@]}" "status")
  if [[ -n "$STORY" ]]; then
    STATUS_CMD+=("$STORY")
  fi

  echo "Status command:"
  print_command "${STATUS_CMD[@]}"
  echo

  if [[ "$DRY_RUN" -eq 0 ]]; then
    "${STATUS_CMD[@]}"
    echo
  fi
fi

if [[ "$PREPARE_ONLY" -eq 0 && "$SKIP_VOICE_SETUP" -eq 0 ]]; then
  echo "Checking voice-role setup..."

  VOICE_STATE="$(voice_config_state)"

  case "$VOICE_STATE" in
    READY)
      echo "Voice roles already have IDs. Skipping auto-assign."
      ;;
    MISSING|MISSING_OR_BLANK)
      echo "Voice roles are missing or blank."
      echo "Running voice auto-assign once."
      echo "This calls ElevenLabs List Voices, but does not generate MP3 audio."

      VOICE_ASSIGN_CMD=("${AUDIO_CMD[@]}" "voices" "auto-assign")
      echo "Voice setup command:"
      print_command "${VOICE_ASSIGN_CMD[@]}"
      echo

      if [[ "$DRY_RUN" -eq 0 ]]; then
        "${VOICE_ASSIGN_CMD[@]}"
      fi
      ;;
    INVALID)
      die "config/voice_roles.json is invalid JSON or not a JSON object. Fix it before auto-assigning voices."
      ;;
    *)
      die "Unexpected voice config state: $VOICE_STATE"
      ;;
  esac

  VALIDATE_CMD=("${AUDIO_CMD[@]}" "voices" "validate")
  if [[ -n "$STORY" ]]; then
    VALIDATE_CMD+=("$STORY")
  fi

  echo
  echo "Validating voices and narration labels..."
  echo "Voice validation command:"
  print_command "${VALIDATE_CMD[@]}"
  echo

  if [[ "$DRY_RUN" -eq 0 ]]; then
    "${VALIDATE_CMD[@]}"
  fi

  echo
elif [[ "$PREPARE_ONLY" -eq 1 ]]; then
  echo "Skipping voice setup because --prepare-only is set."
  echo
elif [[ "$SKIP_VOICE_SETUP" -eq 1 ]]; then
  echo "Skipping voice setup because --skip-voice-setup is set."
  echo
fi

CMD=("${AUDIO_CMD[@]}" "build")

if [[ -n "$STORY" ]]; then
  CMD+=("$STORY")
fi

CMD+=("--$MODE")

if [[ -n "$CHAPTER" ]]; then
  CMD+=("--chapter" "$CHAPTER")
fi

if [[ "$YES" -eq 1 ]]; then
  CMD+=("--yes")
fi

if [[ "$FORCE" -eq 1 ]]; then
  CMD+=("--force")
fi

if [[ "$PREPARE_ONLY" -eq 1 ]]; then
  CMD+=("--prepare-only")
fi

echo "Build command:"
print_command "${CMD[@]}"
echo

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry run complete. No setup or build command was run."
  exit 0
fi

"${CMD[@]}"

echo
echo "Done."
