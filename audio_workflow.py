"""Repository-root audiobook production workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree

from ai_script_preparer import AIScriptPreparer, PreparationError

SUPPORTED_TEXT_EXTENSIONS = (".md", ".txt", ".docx")
CHAPTER_RE = re.compile(r"^chapter_(\d{3})\.(md|txt|docx)$", re.IGNORECASE)
NARRATION_RE = re.compile(r"^chapter_(\d{3})_audio_script\.md$", re.IGNORECASE)
REQUIRED_VOICE_ROLES = (
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
)
VOICE_ROLE_SET = set(REQUIRED_VOICE_ROLES)
ROLE_LABEL_RE = re.compile(r"^[A-Z][A-Z0-9_]*(?:\s*:[^\]]+)?$")
HEADER_RE = re.compile(r"^\[(SFX\s*:[^\]]+|[A-Z][A-Z0-9_]*(?:\s*:[^\]]+)?)\]\s*$")
SPEAKER_HEADER_RE = re.compile(r"^\[([A-Z][A-Z0-9_]*)(?:\s*:[^\]]+)?\]\s*$")
CHAPTER_HEADING_RE = re.compile(r"(?im)^\s*(chapter\s+(?:\d+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)|prologue|epilogue)\b.*$")


class WorkflowError(RuntimeError):
    """Raised for user-fixable workflow errors."""


@dataclass(frozen=True)
class Story:
    slug: str
    path: Path


@dataclass(frozen=True)
class ChapterSource:
    number: int
    path: Path


@dataclass(frozen=True)
class ScriptDetection:
    prepared: bool
    labelled_blocks: int
    speakable_blocks: int


@dataclass
class ChapterStatus:
    number: int
    source: Path | None
    narration: Path
    mp3: Path
    preparation_metadata: Path
    generation_metadata: Path
    source_state: str
    chapter_state: str
    narration_state: str
    mp3_state: str
    metadata_state: str
    next_command: str


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp_name = handle.name
    os.replace(temp_name, path)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temp_name = handle.name
    os.replace(temp_name, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_story_dirs(story: Story) -> None:
    for name in ("source", "chapters", "bible", "narration", "output", "logs"):
        directory = story.path / name
        directory.mkdir(parents=True, exist_ok=True)
    readmes = {
        "bible/README.md": "# Story bible\n\nPut character bibles, voice notes, pronunciation notes, and style guides here.\n",
        "source/README.md": "# Source manuscript\n\nPut the untouched full manuscript here. Supported formats: .md, .txt, .docx.\n",
        "chapters/README.md": "# Chapter files\n\nPut clean split source chapters here as chapter_001.md, chapter_002.md, etc.\n",
        "narration/README.md": "# Narration scripts\n\nPrepared audio-drama scripts belong here as chapter_001_audio_script.md.\n",
        "output/README.md": "# Generated audio output\n\nGenerated MP3 files and generation metadata belong here.\n",
        "logs/README.md": "# Logs\n\nPreparation and generation logs belong here.\n",
    }
    for relative, content in readmes.items():
        path = story.path / relative
        if not path.exists():
            atomic_write_text(path, content)


def resolve_stories(repo_root: Path, selector: str | None) -> list[Story]:
    stories_dir = repo_root / "stories"
    if not stories_dir.exists():
        raise WorkflowError("No story folders found under stories/. Create a story first, then rerun audio status.")
    folders = sorted(path for path in stories_dir.iterdir() if path.is_dir())
    if not folders:
        raise WorkflowError("No story folders found under stories/. Create a story first, then rerun audio status.")
    if selector is None:
        return [Story(path.name, path) for path in folders]
    wanted = slugify(selector)
    exact = [path for path in folders if path.name == selector or path.name == wanted]
    if len(exact) == 1:
        return [Story(exact[0].name, exact[0])]
    if len(exact) > 1:
        raise WorkflowError(f"Ambiguous story name: {selector}. Please use the exact story slug.")
    partial = [path for path in folders if wanted and wanted in path.name]
    if len(partial) == 1:
        return [Story(partial[0].name, partial[0])]
    if len(partial) > 1:
        matches = "\n".join(f"- {path.name}" for path in partial)
        raise WorkflowError(f"Ambiguous story name: {selector}. Matches:\n{matches}\nPlease use the exact story slug.")
    available = "\n".join(f"- {path.name}" for path in folders)
    raise WorkflowError(
        f"Story not found: {selector}\n\nLooked for: stories/{wanted}/\n\nAvailable stories:\n{available}\n\n"
        "If this is a new story, create it first with scripts/create_story_structure.sh."
    )


def read_story_text(path: Path) -> str:
    if path.suffix.lower() not in SUPPORTED_TEXT_EXTENSIONS:
        raise WorkflowError(f"Unsupported source file type: {path}. Supported file types: .md, .txt, .docx.")
    if path.suffix.lower() == ".docx":
        return read_docx(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise WorkflowError(f"Could not read {path} as UTF-8 text. Please save it as UTF-8 and try again.") from exc
    if not text.strip():
        raise WorkflowError(f"Cannot use empty source file: {path}")
    return text


def read_docx(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise WorkflowError(
            f"Could not read DOCX source file: {path}. The file may be corrupt, password-protected, or not a valid .docx file."
        ) from exc
    root = ElementTree.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
        if text.strip():
            paragraphs.append(text)
    result = "\n\n".join(paragraphs)
    if not result.strip():
        raise WorkflowError(f"Cannot use empty DOCX source file: {path}")
    return result



def voice_roles_path(repo_root: Path | None = None) -> Path:
    return (repo_root or Path.cwd()) / "config" / "voice_roles.json"


def default_voice_roles() -> dict[str, str]:
    return {role: "" for role in REQUIRED_VOICE_ROLES}


def load_voice_roles(repo_root: Path | None = None) -> dict[str, str]:
    path = voice_roles_path(repo_root)
    if not path.exists():
        raise WorkflowError(
            f"Voice role configuration is missing: {path}\n"
            "Create it with required reusable role labels, or run: audio voices auto-assign"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"Voice role configuration is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise WorkflowError(f"Voice role configuration must be a JSON object: {path}")
    return {str(key): str(value).strip() for key, value in data.items()}


def save_voice_roles(roles: dict[str, str], repo_root: Path | None = None) -> None:
    ordered = {role: roles.get(role, "") for role in REQUIRED_VOICE_ROLES}
    extra = {key: roles[key] for key in sorted(roles) if key not in ordered}
    atomic_write_text(voice_roles_path(repo_root), json.dumps({**ordered, **extra}, indent=2) + "\n")


def normalize_role_label(label: str) -> str:
    inner = label.strip()[1:-1].strip() if label.strip().startswith("[") and label.strip().endswith("]") else label.strip()
    return inner.split(":", 1)[0].strip().upper()


def is_sfx_label(label: str) -> bool:
    return label.strip().upper().startswith("[SFX")


def validate_voice_roles_config(roles: dict[str, str], require_non_empty: bool = True) -> None:
    missing = [role for role in REQUIRED_VOICE_ROLES if role not in roles]
    if missing:
        raise WorkflowError("config/voice_roles.json is missing required role(s): " + ", ".join(missing))
    if require_non_empty:
        blank = [role for role in REQUIRED_VOICE_ROLES if not roles.get(role, "").strip()]
        if blank:
            raise WorkflowError(
                "config/voice_roles.json has blank ElevenLabs voice ID(s): "
                + ", ".join(blank)
                + "\nFill them manually from `audio voices list` or run `audio voices auto-assign`."
            )


def unknown_speaker_labels_from_text(text: str) -> list[tuple[int, str]]:
    unknown: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not (stripped.startswith("[") and stripped.endswith("]")):
            continue
        inner = stripped[1:-1].strip()
        if inner.upper().startswith("SFX:"):
            continue
        if not ROLE_LABEL_RE.match(inner):
            continue
        role = inner.split(":", 1)[0].strip().upper()
        if role not in VOICE_ROLE_SET:
            unknown.append((line_number, stripped))
    return unknown


def unknown_speaker_labels(path: Path) -> list[tuple[int, str]]:
    return unknown_speaker_labels_from_text(read_story_text(path))


def validate_script_voice_labels(path: Path) -> None:
    unknown = unknown_speaker_labels(path)
    if unknown:
        examples = "\n".join(f"- {path}:{line}: {label}" for line, label in unknown[:10])
        raise WorkflowError(
            "Narration script contains unknown speaker role label(s). Use reusable voice-role labels only; "
            "character-name voice mapping is not supported.\n"
            f"{examples}"
        )


def detect_prepared_script(text: str, minimum_blocks: int = 2) -> ScriptDetection:
    labelled = 0
    speakable = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not HEADER_RE.match(stripped):
            continue
        if is_sfx_label(stripped):
            labelled += 1
            continue
        role = normalize_role_label(stripped)
        if role in VOICE_ROLE_SET:
            labelled += 1
            speakable += 1
    return ScriptDetection(prepared=labelled >= minimum_blocks and speakable >= 1, labelled_blocks=labelled, speakable_blocks=speakable)


def validate_prepared_script(path: Path) -> ScriptDetection:
    text = read_story_text(path)
    detection = detect_prepared_script(text, minimum_blocks=1)
    validate_script_voice_labels(path)
    if detection.labelled_blocks < 1 or detection.speakable_blocks < 1:
        raise WorkflowError(
            "Prepared narration script appears invalid.\n\n"
            f"File: {path}\n\n"
            "Expected labelled blocks such as [NARRATOR], [FMC], [MMC: emotional direction], "
            f"or [SFX: sound effect description]. Found {detection.labelled_blocks} valid labelled blocks."
        )
    return detection


def narration_path(story: Story, number: int) -> Path:
    return story.path / "narration" / f"chapter_{number:03d}_audio_script.md"


def preparation_metadata_path(story: Story, number: int) -> Path:
    return story.path / "narration" / f"chapter_{number:03d}_preparation_metadata.json"


def mp3_path(story: Story, number: int) -> Path:
    return story.path / "output" / f"chapter_{number:03d}.mp3"


def generation_metadata_path(story: Story, number: int) -> Path:
    return story.path / "output" / f"chapter_{number:03d}_metadata.json"


def chapter_sources(story: Story) -> list[ChapterSource]:
    chapters_dir = story.path / "chapters"
    grouped: dict[int, list[Path]] = {}
    if chapters_dir.exists():
        for path in sorted(chapters_dir.iterdir()):
            match = CHAPTER_RE.match(path.name)
            if match:
                grouped.setdefault(int(match.group(1)), []).append(path)
    priority = {".md": 0, ".txt": 1, ".docx": 2}
    sources = []
    for number, paths in sorted(grouped.items()):
        paths.sort(key=lambda item: priority[item.suffix.lower()])
        sources.append(ChapterSource(number, paths[0]))
    return sources


def narration_numbers(story: Story) -> list[int]:
    folder = story.path / "narration"
    numbers = []
    if folder.exists():
        for path in folder.iterdir():
            match = NARRATION_RE.match(path.name)
            if match:
                numbers.append(int(match.group(1)))
    return sorted(set(numbers))


def is_content_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name.lower() == "readme.md" or path.name.lower().endswith("_metadata.json"):
        return False
    return path.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS


def source_manuscripts(story: Story) -> list[Path]:
    folder = story.path / "source"
    if not folder.exists():
        return []
    return sorted(path for path in folder.iterdir() if is_content_file(path))


def discover_chapter_numbers(story: Story) -> list[int]:
    numbers = set(narration_numbers(story))
    numbers.update(source.number for source in chapter_sources(story))
    if not numbers and source_manuscripts(story):
        numbers.add(1)
    return sorted(numbers)


def split_source_if_needed(story: Story, force: bool = False) -> list[ChapterSource]:
    existing = chapter_sources(story)
    if existing and not force:
        return existing
    manuscripts = source_manuscripts(story)
    if not manuscripts:
        return existing
    if len(manuscripts) > 1:
        names = "\n".join(f"- {path.relative_to(story.path)}" for path in manuscripts)
        raise WorkflowError(f"Multiple source manuscripts found in {story.path / 'source'}; cannot choose automatically:\n{names}")
    manuscript = manuscripts[0]
    text = read_story_text(manuscript)
    parts = split_chapters(text)
    created = []
    for index, chapter_text in enumerate(parts, start=1):
        target = story.path / "chapters" / f"chapter_{index:03d}.md"
        if target.exists() and not force:
            continue
        atomic_write_text(target, chapter_text.strip() + "\n")
        metadata = {
            "created_at": now_iso(),
            "source_path": str(manuscript.relative_to(story.path)),
            "source_sha256": sha256_file(manuscript),
            "chapter_path": str(target.relative_to(story.path)),
            "chapter_sha256": sha256_file(target),
        }
        atomic_write_text(story.path / "chapters" / f"chapter_{index:03d}_metadata.json", json.dumps(metadata, indent=2) + "\n")
        created.append(ChapterSource(index, target))
    return chapter_sources(story) or created


def split_chapters(text: str) -> list[str]:
    matches = list(CHAPTER_HEADING_RE.finditer(text))
    if len(matches) <= 1:
        return [text]
    parts = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        parts.append(text[start:end].strip())
    return [part for part in parts if part]


def stale_against_metadata(output: Path, metadata_path: Path, source: Path | None, source_key: str, output_key: str) -> bool:
    if not output.exists():
        return False
    if not metadata_path.exists():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return True
    if source and source.exists() and metadata.get(source_key) != sha256_file(source):
        return True
    if metadata.get(output_key) and metadata.get(output_key) != sha256_file(output):
        return True
    return False


def source_for_number(story: Story, number: int) -> Path | None:
    for source in chapter_sources(story):
        if source.number == number:
            return source.path
    manuscripts = source_manuscripts(story)
    if number == 1 and len(manuscripts) == 1:
        return manuscripts[0]
    return None


def status_for_story(story: Story) -> list[ChapterStatus]:
    ensure_story_dirs(story)
    numbers = discover_chapter_numbers(story)
    if not numbers:
        numbers = [1]
    statuses = []
    for number in numbers:
        source = source_for_number(story, number)
        narration = narration_path(story, number)
        mp3 = mp3_path(story, number)
        prep_meta = preparation_metadata_path(story, number)
        gen_meta = generation_metadata_path(story, number)
        source_state = "exists" if source and source.exists() else "missing"
        chapter_state = "exists" if any(cs.number == number for cs in chapter_sources(story)) else "missing"
        if narration.exists():
            narration_state = "stale" if stale_against_metadata(narration, prep_meta, source, "source_sha256", "script_sha256") else "exists"
        else:
            narration_state = "missing"
        if mp3.exists():
            mp3_state = "stale" if stale_against_metadata(mp3, gen_meta, narration if narration.exists() else None, "script_sha256", "mp3_sha256") else "exists"
        else:
            mp3_state = "missing"
        metadata_state = "exists" if prep_meta.exists() or gen_meta.exists() else "missing"
        if narration_state == "missing":
            next_command = f"audio prepare {story.slug} --auto"
        elif narration_state == "stale":
            next_command = f"audio prepare {story.slug} --auto --force"
        elif mp3_state == "missing":
            next_command = f"audio generate {story.slug}"
        elif mp3_state == "stale":
            next_command = f"audio generate {story.slug} --force"
        else:
            next_command = "up to date"
        statuses.append(ChapterStatus(number, source, narration, mp3, prep_meta, gen_meta, source_state, chapter_state, narration_state, mp3_state, metadata_state, next_command))
    return statuses


def require_mode(mode: str | None, command: str) -> str:
    if mode not in {"prepared", "unprepared", "auto"}:
        raise WorkflowError(
            f"Preparation mode required for audio {command}. Choose one of --prepared, --unprepared, or --auto.\n\n"
            "--prepared: input files already contain audio-drama tags; no AI preparation API will be called.\n"
            "--unprepared: input files are prose and require AI preparation after validation.\n"
            "--auto: inspect files locally first; AI is called only if files appear unprepared."
        )
    return mode


def prepare_story(story: Story, mode: str, force: bool = False, chapter: int | None = None) -> bool:
    ensure_story_dirs(story)
    split_source_if_needed(story, force=force)
    sources = chapter_sources(story)
    if chapter is not None:
        sources = [source for source in sources if source.number == chapter]
    if not sources:
        if chapter is not None:
            raise WorkflowError(f"Chapter {chapter:03d} was not found for {story.slug}. Add chapters/chapter_{chapter:03d}.md or source material first.")
        raise WorkflowError(f"No chapter files or source manuscript found for {story.slug}. Add files to chapters/ or source/.")
    used_ai = False
    for source in sources:
        target = narration_path(story, source.number)
        meta_path = preparation_metadata_path(story, source.number)
        if target.exists() and not force:
            print(f"skip {story.slug} chapter_{source.number:03d}: narration already exists")
            continue
        text = read_story_text(source.path)
        detection = detect_prepared_script(text)
        if mode == "prepared":
            if not detection.prepared:
                raise WorkflowError(
                    f"Input was marked --prepared, but {source.path} does not appear to contain valid audio-drama blocks. "
                    "Use --unprepared if this is prose, or --auto to let the tool decide."
                )
            script = text.strip() + "\n"
            provider = "none"
            model = "none"
        elif mode == "unprepared":
            if detection.prepared and not force:
                raise WorkflowError(
                    f"Input was marked --unprepared, but {source.path} already appears prepared. "
                    "No API call was made. Use --prepared, --auto, or --force --unprepared if intentional."
                )
            result = AIScriptPreparer().prepare(text)
            script = result.script.strip() + "\n"
            provider = result.provider
            model = result.model
            used_ai = True
        else:
            if detection.prepared:
                script = text.strip() + "\n"
                provider = "none"
                model = "auto-detected-prepared"
            else:
                result = AIScriptPreparer().prepare(text)
                script = result.script.strip() + "\n"
                provider = result.provider
                model = result.model
                used_ai = True
        output_detection = detect_prepared_script(script)
        unknown_labels = unknown_speaker_labels_from_text(script)
        if unknown_labels:
            examples = "\n".join(f"- prepared output line {line}: {label}" for line, label in unknown_labels[:10])
            raise WorkflowError(
                f"Prepared output for {story.slug} chapter_{source.number:03d} uses unknown voice-role labels. "
                "Use reusable role labels only, not character names.\n"
                f"{examples}"
            )
        if not output_detection.prepared:
            log = story.path / "logs" / f"chapter_{source.number:03d}_preparation_error.log"
            atomic_write_text(log, script)
            raise WorkflowError(
                f"Prepared output for {story.slug} chapter_{source.number:03d} is not a valid audio-drama script. "
                f"Raw output saved to {log}."
            )
        atomic_write_text(target, script)
        metadata = {
            "created_at": now_iso(),
            "mode": mode,
            "provider": provider,
            "model": model,
            "source_path": str(source.path.relative_to(story.path)),
            "source_sha256": sha256_file(source.path),
            "script_path": str(target.relative_to(story.path)),
            "script_sha256": sha256_file(target),
            "labelled_blocks": output_detection.labelled_blocks,
            "speakable_blocks": output_detection.speakable_blocks,
        }
        atomic_write_text(meta_path, json.dumps(metadata, indent=2) + "\n")
        atomic_write_text(story.path / "logs" / f"chapter_{source.number:03d}_preparation.log", json.dumps(metadata, indent=2) + "\n")
        print(f"prepared {story.slug} chapter_{source.number:03d}: {target}")
    return used_ai


def parse_script_blocks(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, list[str]]] = []
    current_label: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if HEADER_RE.match(stripped):
            if current_label is not None:
                blocks.append((current_label, current_lines))
            current_label = stripped
            current_lines = []
        elif current_label is not None:
            current_lines.append(line)
    if current_label is not None:
        blocks.append((current_label, current_lines))
    return [(label, "\n".join(lines).strip()) for label, lines in blocks if "\n".join(lines).strip()]


def generate_story(story: Story, force: bool = False, chapter: int | None = None) -> None:
    ensure_story_dirs(story)
    numbers = narration_numbers(story)
    if chapter is not None:
        numbers = [number for number in numbers if number == chapter]
    if not numbers:
        if chapter is not None:
            raise WorkflowError(f"Cannot generate audio for {story.slug} chapter_{chapter:03d} because its prepared narration script was not found.")
        raise WorkflowError(
            f"Cannot generate audio for {story.slug} because no prepared narration scripts were found in {story.path / 'narration'}.\n"
            f"Run: audio prepare {story.slug} --auto"
        )
    pending: list[int] = []
    for number in numbers:
        script = narration_path(story, number)
        target = mp3_path(story, number)
        if target.exists() and not force:
            print(f"skip {story.slug} chapter_{number:03d}: MP3 already exists")
            continue
        validate_prepared_script(script)
        pending.append(number)
    if not pending:
        return
    roles = load_voice_roles()
    validate_voice_roles_config(roles, require_non_empty=True)
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise WorkflowError("Cannot generate MP3 because ELEVENLABS_API_KEY is not set.")
    for number in pending:
        script = narration_path(story, number)
        target = mp3_path(story, number)
        text = read_story_text(script)
        blocks = parse_script_blocks(text)
        speakable = [(normalize_role_label(label), body) for label, body in blocks if not is_sfx_label(label) and body.strip()]
        if not speakable:
            raise WorkflowError(f"No speakable narration blocks found in {script}.")
        audio = bytearray()
        used_voice_ids: dict[str, str] = {}
        for role, body in speakable:
            voice_id = roles.get(role, "").strip()
            if not voice_id:
                raise WorkflowError(f"Role {role} has no ElevenLabs voice ID in config/voice_roles.json. No generation request was sent.")
            used_voice_ids[role] = voice_id
            audio.extend(elevenlabs_tts(body, api_key, voice_id))
        atomic_write_bytes(target, bytes(audio))
        meta = {
            "created_at": now_iso(),
            "script_path": str(script.relative_to(story.path)),
            "script_sha256": sha256_file(script),
            "mp3_path": str(target.relative_to(story.path)),
            "mp3_sha256": sha256_file(target),
            "voice_roles": used_voice_ids,
            "speakable_blocks": len(speakable),
        }
        atomic_write_text(generation_metadata_path(story, number), json.dumps(meta, indent=2) + "\n")
        atomic_write_text(story.path / "logs" / f"chapter_{number:03d}_generation.log", json.dumps(meta, indent=2) + "\n")
        print(f"generated {story.slug} chapter_{number:03d}: {target}")


def elevenlabs_tts(text: str, api_key: str, voice_id: str) -> bytes:
    if not voice_id or not voice_id.strip():
        raise WorkflowError("Refusing to call ElevenLabs Text-to-Speech with a blank voice_id.")
    payload = {
        "text": text,
        "model_id": os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    request = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise WorkflowError(f"ElevenLabs returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise WorkflowError(f"Could not reach ElevenLabs: {exc.reason}") from exc



def elevenlabs_list_voices(api_key: str) -> list[dict]:
    request = urllib.request.Request(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise WorkflowError(f"ElevenLabs returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise WorkflowError(f"Could not reach ElevenLabs: {exc.reason}") from exc
    voices = data.get("voices", [])
    if not isinstance(voices, list):
        raise WorkflowError("ElevenLabs List Voices response did not contain a voices list.")
    return [voice for voice in voices if isinstance(voice, dict)]


def require_elevenlabs_api_key() -> str:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise WorkflowError("ELEVENLABS_API_KEY is required for this ElevenLabs voice command.")
    return api_key


def voice_search_text(voice: dict) -> str:
    labels = voice.get("labels") if isinstance(voice.get("labels"), dict) else {}
    values = [str(voice.get("name", "")), str(voice.get("category", "")), str(voice.get("description", ""))]
    values.extend(str(value) for value in labels.values())
    return " ".join(values).lower()


def choose_voice_for_role(role: str, voices: list[dict]) -> str:
    if not voices:
        raise WorkflowError("ElevenLabs returned no available voices for this account.")
    role_terms = {
        "NARRATOR": ["narrat", "story", "warm"],
        "FMC": ["female", "young", "warm"],
        "MMC": ["male", "deep", "warm"],
        "DEFAULT_FEMALE": ["female"],
        "DEFAULT_MALE": ["male"],
        "ADULT_FEMALE_1": ["female", "adult"],
        "ADULT_FEMALE_2": ["female", "middle"],
        "ADULT_MALE_1": ["male", "adult"],
        "ADULT_MALE_2": ["male", "middle"],
        "OLDER_FEMALE": ["female", "old"],
        "OLDER_MALE": ["male", "old"],
        "TEEN_FEMALE": ["female", "young"],
        "TEEN_MALE": ["male", "young"],
        "CHILD_FEMALE": ["female", "child"],
        "CHILD_MALE": ["male", "child"],
        "WOLF_OR_MONSTER": ["monster", "creature", "deep", "gravel"],
    }
    terms = role_terms.get(role, [])
    scored: list[tuple[int, str]] = []
    for voice in voices:
        voice_id = str(voice.get("voice_id", "")).strip()
        if not voice_id:
            continue
        text = voice_search_text(voice)
        score = sum(1 for term in terms if term in text)
        wants_female = role == "FMC" or "FEMALE" in role
        wants_male = role == "MMC" or ("MALE" in role and "FEMALE" not in role)
        if wants_female:
            score += 1 if "female" in text else 0
        elif wants_male:
            score += 1 if "male" in text and "female" not in text else 0
        scored.append((score, voice_id))
    if not scored:
        raise WorkflowError("ElevenLabs voices did not include usable voice_id values.")
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def print_voice_list() -> None:
    voices = elevenlabs_list_voices(require_elevenlabs_api_key())
    for voice in voices:
        print(f"{voice.get('name', '(unnamed)')}\t{voice.get('voice_id', '')}")


def auto_assign_voice_roles(repo_root: Path) -> None:
    voices = elevenlabs_list_voices(require_elevenlabs_api_key())
    try:
        roles = load_voice_roles(repo_root)
    except WorkflowError:
        roles = default_voice_roles()
    validate_voice_roles_config({**default_voice_roles(), **roles}, require_non_empty=False)
    changed = False
    for role in REQUIRED_VOICE_ROLES:
        if roles.get(role, "").strip():
            continue
        roles[role] = choose_voice_for_role(role, voices)
        changed = True
    save_voice_roles(roles, repo_root)
    if changed:
        print(f"Saved ElevenLabs voice role assignments to {voice_roles_path(repo_root)}")
    else:
        print(f"All required voice roles already had saved IDs in {voice_roles_path(repo_root)}")


def validate_voices_workflow(repo_root: Path, stories: Iterable[Story]) -> None:
    roles = load_voice_roles(repo_root)
    validate_voice_roles_config(roles, require_non_empty=True)
    for story in stories:
        for number in narration_numbers(story):
            validate_prepared_script(narration_path(story, number))
    print("Voice roles and narration labels are valid.")


def preview_voice_roles(repo_root: Path, yes: bool = False) -> None:
    if not yes:
        raise WorkflowError(
            "Voice preview spends ElevenLabs generation credits. Re-run with: audio voices preview --yes"
        )
    roles = load_voice_roles(repo_root)
    validate_voice_roles_config(roles, require_non_empty=True)
    api_key = require_elevenlabs_api_key()
    preview_dir = repo_root / "config" / "voice_previews"
    for role in REQUIRED_VOICE_ROLES:
        sample = f"{role.replace('_', ' ').title()} voice preview."
        audio = elevenlabs_tts(sample, api_key, roles[role])
        atomic_write_bytes(preview_dir / f"{role}.mp3", audio)
    print(f"Saved voice previews to {preview_dir}")


def print_status(stories: Iterable[Story]) -> None:
    for story in stories:
        print(f"\nStory: {story.slug}")
        for status in status_for_story(story):
            source = status.source.relative_to(story.path) if status.source else "-"
            print(
                f"  chapter_{status.number:03d} | source: {status.source_state} ({source}) | "
                f"chapters: {status.chapter_state} | narration: {status.narration_state} | "
                f"mp3: {status.mp3_state} | metadata: {status.metadata_state} | next: {status.next_command}"
            )


def build_story(story: Story, mode: str, yes: bool = False, force: bool = False, chapter: int | None = None) -> None:
    used_ai = prepare_story(story, mode, force=force, chapter=chapter)
    if used_ai and not yes:
        print(
            f"AI preparation completed for {story.slug}. Review scripts in {story.path / 'narration'} before generating audio.\n"
            f"Next command: audio generate {story.slug}\n"
            f"To continue without review next time: audio build {story.slug} --{mode} --yes"
        )
        return
    generate_story(story, force=force, chapter=chapter)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="audio", description="Prepare and generate story audio from the repository root.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "prepare", "generate", "build"):
        sub = subparsers.add_parser(command)
        sub.add_argument("story", nargs="?", help="Story slug, title, or folder name. Omit to operate on all stories.")
        if command in {"prepare", "build"}:
            modes = sub.add_mutually_exclusive_group()
            modes.add_argument("--prepared", action="store_true", help="Inputs already contain audio-drama tags; no AI preparation call.")
            modes.add_argument("--unprepared", action="store_true", help="Inputs are prose and require AI preparation.")
            modes.add_argument("--auto", action="store_true", help="Inspect locally; call AI only for prose inputs.")
            sub.add_argument("--prepare-only", action="store_true", help="Prepare narration scripts only; never generate MP3 audio.")
        if command in {"prepare", "generate", "build"}:
            sub.add_argument("--force", action="store_true", help="Regenerate existing derived files.")
            sub.add_argument("--chapter", type=int, help="Limit work to one chapter number, e.g. --chapter 1.")
        if command == "build":
            sub.add_argument("--yes", action="store_true", help="Skip the review stop after AI preparation.")

    voices = subparsers.add_parser("voices", help="Manage reusable ElevenLabs voice-role assignments.")
    voice_subparsers = voices.add_subparsers(dest="voices_command", required=True)
    voice_subparsers.add_parser("list", help="List available ElevenLabs voice names and IDs without generating audio.")
    voice_subparsers.add_parser("auto-assign", help="Fill blank reusable role IDs from ElevenLabs List Voices without generating audio.")
    validate = voice_subparsers.add_parser("validate", help="Validate voice_roles.json and narration speaker labels without generating audio.")
    validate.add_argument("story", nargs="?", help="Optional story slug/title/folder to validate. Omit for all stories.")
    preview = voice_subparsers.add_parser("preview", help="Generate short paid preview MP3s for each reusable role.")
    preview.add_argument("--yes", action="store_true", help="Confirm that preview generation spends ElevenLabs credits.")
    return parser

def selected_mode(args: argparse.Namespace) -> str | None:
    if getattr(args, "prepared", False):
        return "prepared"
    if getattr(args, "unprepared", False):
        return "unprepared"
    if getattr(args, "auto", False):
        return "auto"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    repo_root = Path.cwd()
    try:
        if args.command == "voices":
            if args.voices_command == "list":
                print_voice_list()
            elif args.voices_command == "auto-assign":
                auto_assign_voice_roles(repo_root)
            elif args.voices_command == "validate":
                stories = resolve_stories(repo_root, args.story)
                validate_voices_workflow(repo_root, stories)
            elif args.voices_command == "preview":
                preview_voice_roles(repo_root, yes=args.yes)
            return 0

        stories = resolve_stories(repo_root, args.story)
        if args.command == "status":
            print_status(stories)
        elif args.command == "prepare":
            mode = require_mode(selected_mode(args), "prepare")
            for story in stories:
                prepare_story(story, mode, force=args.force, chapter=args.chapter)
        elif args.command == "generate":
            for story in stories:
                generate_story(story, force=args.force, chapter=args.chapter)
        elif args.command == "build":
            if getattr(args, "prepare_only", False):
                mode = require_mode(selected_mode(args), "build")
                for story in stories:
                    prepare_story(story, mode, force=args.force, chapter=args.chapter)
            else:
                mode = require_mode(selected_mode(args), "build")
                for story in stories:
                    build_story(story, mode, yes=args.yes, force=args.force, chapter=args.chapter)
        return 0
    except (WorkflowError, PreparationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
