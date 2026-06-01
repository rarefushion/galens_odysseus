"""
System Prompt Manager

Loads and caches system prompts from data/system_prompts.json.
Provides get_active_prompts() to retrieve all enabled prompts.
Supports automatic cache invalidation when the config file changes
on disk (no restart needed).

If the config file is missing, falls back to DEFAULT_SYSTEM_PROMPTS
(mirrors the pattern in settings.py for DEFAULT_SETTINGS / DEFAULT_FEATURES).
"""

import json
import logging
import os
from typing import List, Dict, Optional

from src.constants import SYSTEM_PROMPTS_FILE

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = SYSTEM_PROMPTS_FILE

# ── Default system prompts ──────────────────────────────────────────────
# Serves as the fallback when data/system_prompts.json does not exist on
# disk, so a fresh install still ships with usable behavioral prompts.

DEFAULT_SYSTEM_PROMPTS = {
    "prompts": [
        {
            "name": "concise",
            "enabled": False,
            "description": "Keep responses short and direct",
            "content": (
                "Be concise. Give direct answers without unnecessary "
                "preamble, explanations, or commentary. Use bullet points "
                'for lists. Skip "Certainly!", "Great question!", and '
                "similar filler."
            ),
        },
        {
            "name": "verbose_explanations",
            "enabled": False,
            "description": "Provide thorough explanations with reasoning",
            "content": (
                "When answering, explain your reasoning step by step. "
                "Include relevant context, alternatives considered, and "
                "trade-offs. Prefer thoroughness over brevity."
            ),
        },
        {
            "name": "code_only",
            "enabled": False,
            "description": "Output only code, no explanation",
            "content": (
                "When asked for code, output ONLY the code in a fenced "
                "block. Do not add explanations, comments about the code, "
                "or any other text unless specifically asked. The code "
                "should be complete and ready to run."
            ),
        },
        {
            "name": "expert_python",
            "enabled": False,
            "description": "Use idiomatic Python patterns",
            "content": (
                "When writing Python, use idiomatic patterns: list "
                "comprehensions, context managers, dataclasses, type hints, "
                "pathlib, f-strings. Prefer standard library over "
                "third-party packages. Follow PEP 8."
            ),
        },
        {
            "name": "no_emojis",
            "enabled": False,
            "description": "Avoid emoji in responses",
            "content": (
                "Do not use emoji characters in your responses. Use plain "
                "text formatting instead."
            ),
        },
    ]
}


class SystemPromptManager:
    """Manages loadable system prompts from a JSON configuration file.

    Each prompt has:
      - name: unique identifier
      - enabled: bool toggle
      - description: short human-readable summary
      - content: the prompt text injected into the agent's system prompt
    """

    def __init__(self, config_path: Optional[str] = None):
        self._config_path = config_path or _DEFAULT_CONFIG_PATH
        self._cache: Optional[List[dict]] = None
        self._cache_mtime: float = 0.0

    def _load_raw(self) -> dict:
        """Load the raw JSON file. Falls back to DEFAULT_SYSTEM_PROMPTS
        when the file is missing, so a fresh install still has usable
        behavioral prompts (mirrors settings.py pattern —
        load_settings/load_features also return in-code defaults without
        auto-writing to disk)."""
        logger.info(f"[system-prompts] loading config from: {self._config_path}")
        try:
            with open(self._config_path, "r") as f:
                raw = json.load(f) or {}
                n_prompts = len(raw.get("prompts", [])) if isinstance(raw.get("prompts"), list) else 0
                logger.info(f"[system-prompts] loaded {n_prompts} prompt definitions from JSON")
                return raw
        except FileNotFoundError:
            logger.warning(
                f"[system-prompts] config file NOT FOUND: {self._config_path}; "
                f"falling back to DEFAULT_SYSTEM_PROMPTS"
            )
            return DEFAULT_SYSTEM_PROMPTS
        except Exception as e:
            logger.warning(f"[system-prompts] failed to load config: {e}", exc_info=True)
            return {}

    def _ensure_fresh(self) -> None:
        """Reload cache if the config file has changed on disk."""
        try:
            mtime = os.path.getmtime(self._config_path)
        except OSError:
            mtime = 0.0

        if self._cache is None or mtime > self._cache_mtime:
            raw = self._load_raw()
            self._cache = raw.get("prompts", [])
            if not isinstance(self._cache, list):
                logger.warning("system_prompts.json: 'prompts' is not a list")
                self._cache = []
            self._cache_mtime = mtime

    def get_active_prompts(
        self, names: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """Return a list of {name, content} dicts for active prompts.

        If *names* is provided, only those named prompts are returned
        (regardless of their ``enabled`` flag — the caller is explicitly
        selecting them).  If *names* is ``None``, all prompts with
        ``enabled: true`` are returned.

        An explicit empty list ``names=[]`` means "inject nothing" — no
        prompts are returned even if some are enabled in the config.
        """
        self._ensure_fresh()

        if names is not None:
            # Explicit selection — filter by name, ignore enabled flag
            name_set = set(names)
            return [
                {"name": p.get("name", ""), "content": p.get("content", "")}
                for p in self._cache
                if p.get("name") in name_set and p.get("content", "").strip()
            ]

        # Auto-load all enabled prompts
        return [
            {"name": p.get("name", ""), "content": p.get("content", "")}
            for p in self._cache
            if p.get("enabled", False) and p.get("content", "").strip()
        ]

    def reload(self) -> None:
        """Force reload from disk on the next access."""
        self._cache = None
        self._cache_mtime = 0.0

    def get_all_prompts(self) -> List[dict]:
        """Return ALL prompts (enabled and disabled) for UI listing."""
        self._ensure_fresh()
        return list(self._cache) if self._cache else []


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: Optional[SystemPromptManager] = None


def get_system_prompt_manager() -> SystemPromptManager:
    """Return the module-level singleton SystemPromptManager."""
    global _manager
    if _manager is None:
        _manager = SystemPromptManager()
    return _manager
