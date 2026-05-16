"""AI-backed conversion of prose into prepared audio-drama scripts.

The module intentionally keeps provider-specific HTTP details behind a small
interface so callers can validate inputs before making paid API calls and so new
providers can be added without changing the CLI workflow.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


class PreparationError(RuntimeError):
    """Raised when AI script preparation cannot be completed."""


SUPPORTED_PROVIDERS = {"openai", "anthropic"}


PROMPT_PATH = Path("prompts/audio_script_preparation_prompt.md")


def load_preparation_prompt(prompt_path: Path | None = None) -> str:
    path = prompt_path or PROMPT_PATH
    if not path.exists():
        raise PreparationError(
            f"Audio script preparation prompt is missing: {path}. "
            "Create prompts/audio_script_preparation_prompt.md before preparing unprepared prose."
        )
    prompt = path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise PreparationError(f"Audio script preparation prompt is empty: {path}")
    return prompt



@dataclass(frozen=True)
class AIPreparationResult:
    """Prepared script text and provider metadata."""

    script: str
    provider: str
    model: str


class AIScriptPreparer:
    """Prepare normal prose as an audio-drama script using a configured provider."""

    def __init__(self, provider: str | None = None, prompt_path: Path | None = None) -> None:
        self.provider = resolve_provider(provider)
        self.system_prompt = load_preparation_prompt(prompt_path)

    def prepare(self, prose: str) -> AIPreparationResult:
        """Return an audio-drama script for prose.

        Callers are expected to validate file existence, readability, output
        safety, and prepared/unprepared mode before invoking this method.
        """
        if not prose or not prose.strip():
            raise PreparationError("Cannot prepare an empty story text.")
        if self.provider == "openai":
            return self._prepare_openai(prose)
        if self.provider == "anthropic":
            return self._prepare_anthropic(prose)
        raise PreparationError(f"Unsupported AI preparation provider: {self.provider}")

    def _prepare_openai(self, prose: str) -> AIPreparationResult:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise PreparationError("OPENAI_API_KEY is required when AI_PREPARATION_PROVIDER=openai.")
        model = os.environ.get("OPENAI_PREPARATION_MODEL", "gpt-4o-mini")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prose},
            ],
            "temperature": 0.2,
        }
        data = _post_json(
            "https://api.openai.com/v1/chat/completions",
            payload,
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            script = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise PreparationError("OpenAI response did not contain prepared script text.") from exc
        return AIPreparationResult(script=script.strip(), provider="openai", model=model)

    def _prepare_anthropic(self, prose: str) -> AIPreparationResult:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise PreparationError("ANTHROPIC_API_KEY is required when AI_PREPARATION_PROVIDER=anthropic.")
        model = os.environ.get("ANTHROPIC_PREPARATION_MODEL", "claude-3-5-haiku-latest")
        payload = {
            "model": model,
            "max_tokens": 8192,
            "temperature": 0.2,
            "system": self.system_prompt,
            "messages": [{"role": "user", "content": prose}],
        }
        data = _post_json(
            "https://api.anthropic.com/v1/messages",
            payload,
            {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
        try:
            parts = data["content"]
            script = "".join(part.get("text", "") for part in parts if part.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise PreparationError("Anthropic response did not contain prepared script text.") from exc
        if not script.strip():
            raise PreparationError("Anthropic response did not contain prepared script text.")
        return AIPreparationResult(script=script.strip(), provider="anthropic", model=model)


def resolve_provider(provider: str | None = None) -> str:
    """Resolve and validate the configured AI preparation provider."""
    selected = (provider or os.environ.get("AI_PREPARATION_PROVIDER") or "").strip().lower()
    if selected:
        if selected not in SUPPORTED_PROVIDERS:
            raise PreparationError(
                f"Invalid AI_PREPARATION_PROVIDER: {selected}. Supported values: openai, anthropic."
            )
        _require_provider_key(selected)
        return selected
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise PreparationError(
        "Cannot prepare unprepared prose because no AI preparation API key is available. "
        "Set OPENAI_API_KEY or ANTHROPIC_API_KEY. Optionally set "
        "AI_PREPARATION_PROVIDER=openai or AI_PREPARATION_PROVIDER=anthropic."
    )


def _require_provider_key(provider: str) -> None:
    if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise PreparationError("AI_PREPARATION_PROVIDER=openai requires OPENAI_API_KEY.")
    if provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise PreparationError("AI_PREPARATION_PROVIDER=anthropic requires ANTHROPIC_API_KEY.")


def _post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise PreparationError(f"AI preparation provider returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise PreparationError(f"Could not reach AI preparation provider: {exc.reason}") from exc
