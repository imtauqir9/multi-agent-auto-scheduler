"""
Local LLM client — talks to Ollama's HTTP API only.

There are deliberately NO hosted-LLM SDKs in this project. Every call below
hits http://localhost:11434, so all inference stays on the user's machine
(Qwen3 served by Ollama / LM Studio).
"""
from __future__ import annotations

import json
import logging
import re

import httpx

from config import settings

log = logging.getLogger("llm")


class LocalLLMError(RuntimeError):
    """Raised when the local Ollama server cannot be reached or errors out."""


class LocalLLM:
    """Thin wrapper around the Ollama /api/generate and /api/chat endpoints."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = settings.llm_timeout_seconds

    # ------------------------------------------------------------------ #
    def is_available(self) -> bool:
        """Return True if the local Ollama server responds to /api/tags."""
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:  # noqa: BLE001 - any failure means "not available"
            return False

    # ------------------------------------------------------------------ #
    def generate(self, prompt: str, system: str | None = None,
                 temperature: float = 0.4, think: bool = False) -> str:
        """
        Single-shot completion. Returns the model's text answer.

        `think=False` disables Qwen3's chain-of-thought for these short utility
        tasks (blurbs, classification, commentary) using the model's native
        `/no_think` soft switch — a large latency win with no quality loss.
        """
        if not think:
            prompt = f"{prompt} /no_think"
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        try:
            r = httpx.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
            r.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failure path
            raise LocalLLMError(f"Ollama request failed: {exc}") from exc
        text = r.json().get("response", "").strip()
        return self._strip_think(text)

    # ------------------------------------------------------------------ #
    def classify(self, prompt: str, labels: list[str], system: str | None = None) -> str:
        """
        Force the model to choose exactly one label from `labels`.
        Falls back to the first label if parsing fails.
        """
        sys = system or (
            "You are a precise classifier. Reply with ONLY one of the allowed "
            "labels, nothing else."
        )
        full = f"{prompt}\n\nAllowed labels: {', '.join(labels)}\nAnswer with one label:"
        raw = self.generate(full, system=sys, temperature=0.0).lower()
        for label in labels:
            if label.lower() in raw:
                return label
        return labels[0]

    # ------------------------------------------------------------------ #
    def json_object(self, prompt: str, system: str | None = None) -> dict:
        """Ask the model for JSON and parse the first JSON object found."""
        sys = system or "Respond with valid minified JSON only. No prose, no markdown."
        raw = self.generate(prompt, system=sys, temperature=0.1)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise LocalLLMError(f"Model did not return JSON: {raw[:200]}")
        return json.loads(match.group(0))

    # ------------------------------------------------------------------ #
    @staticmethod
    def _strip_think(text: str) -> str:
        """Qwen3 emits <think>...</think> reasoning; drop it for clean output."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# Module-level singleton used everywhere.
llm = LocalLLM()
