"""LLM Provider Adapter for Gemini and Groq with Structured Output and Caching."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from src.common.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMResponse:
    """Wrapper holding LLM response text, parsed schema, and execution metadata."""

    def __init__(
        self,
        raw_text: str,
        parsed: Any,
        model_name: str,
        provider: str,
        temperature: float,
        prompt_hash: str,
        cached: bool,
    ) -> None:
        self.raw_text = raw_text
        self.parsed = parsed
        self.model_name = model_name
        self.provider = provider
        self.temperature = temperature
        self.prompt_hash = prompt_hash
        self.cached = cached
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_metadata_dict(self) -> dict[str, Any]:
        """Returns metadata required for evaluation recording."""
        return {
            "model_name": self.model_name,
            "provider": self.provider,
            "temperature": self.temperature,
            "prompt_hash": self.prompt_hash,
            "cached": self.cached,
            "timestamp": self.timestamp,
        }


def _extract_json_block(text: str) -> str:
    """Extracts raw JSON string from markdown code fences or raw string."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove opening ```json or ```
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove closing ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


class LLMClient:
    """Thin adapter class supporting Gemini and Groq with structured Pydantic output."""

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        cache_dir: Path | None = None,
        enable_cache: bool | None = None,
    ) -> None:
        self.provider = provider or settings.llm_provider
        self.api_key = api_key or (
            settings.gemini_api_key if self.provider == "gemini" else settings.groq_api_key
        )
        self.model = model or (
            settings.gemini_model if self.provider == "gemini" else settings.groq_model
        )
        self.cache_dir = cache_dir or settings.eval_cache_dir
        self.enable_cache = enable_cache if enable_cache is not None else settings.enable_llm_cache

        if self.enable_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, prompt_hash: str) -> Path:
        return self.cache_dir / f"{prompt_hash}.json"

    def generate_structured(
        self,
        prompt: str,
        system_instruction: str,
        schema: type[T],
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Sends prompt to the configured LLM and validates output against Pydantic schema."""
        combined_payload = f"SYSTEM: {system_instruction}\nPROMPT: {prompt}"
        prompt_hash = hashlib.sha256(combined_payload.encode("utf-8")).hexdigest()

        # 1. Check disk cache
        if self.enable_cache:
            cache_file = self._get_cache_path(prompt_hash)
            if cache_file.exists():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cached_data = json.load(f)
                    raw_text = cached_data["raw_text"]
                    parsed = schema.model_validate_json(raw_text)
                    return LLMResponse(
                        raw_text=raw_text,
                        parsed=parsed,
                        model_name=self.model,
                        provider=self.provider,
                        temperature=temperature,
                        prompt_hash=prompt_hash,
                        cached=True,
                    )
                except Exception:
                    pass  # Corrupt cache entry, refetch

        # 2. Call provider
        if self.provider == "gemini":
            raw_text = self._call_gemini(prompt, system_instruction, schema, temperature)
        elif self.provider == "groq":
            raw_text = self._call_groq(prompt, system_instruction, schema, temperature)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

        # 3. Clean & Validate
        clean_json_str = _extract_json_block(raw_text)
        try:
            parsed = schema.model_validate_json(clean_json_str)
        except Exception as e:
            raise ValueError(
                f"Failed to validate LLM output against {schema.__name__}: {e}\nRaw output: {raw_text}"
            ) from e

        # 4. Save to cache
        if self.enable_cache:
            cache_file = self._get_cache_path(prompt_hash)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "raw_text": clean_json_str,
                        "model": self.model,
                        "provider": self.provider,
                        "temperature": temperature,
                        "prompt_hash": prompt_hash,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    f,
                    indent=2,
                )

        return LLMResponse(
            raw_text=clean_json_str,
            parsed=parsed,
            model_name=self.model,
            provider=self.provider,
            temperature=temperature,
            prompt_hash=prompt_hash,
            cached=False,
        )

    def _call_gemini(
        self, prompt: str, system_instruction: str, schema: type[T], temperature: float
    ) -> str:
        """Invokes official Google GenAI SDK with structured JSON schema."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
        )

        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        return response.text or "{}"

    def _call_groq(
        self, prompt: str, system_instruction: str, schema: type[T], temperature: float
    ) -> str:
        """Invokes official Groq SDK with JSON mode."""
        from groq import Groq

        client = Groq(api_key=self.api_key)
        # Instruct schema in system prompt
        schema_json = json.dumps(schema.model_json_schema())
        enhanced_system = (
            f"{system_instruction}\n"
            f"You MUST respond ONLY with valid JSON conforming to this schema:\n{schema_json}"
        )

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": enhanced_system},
                {"role": "user", "content": prompt},
            ],
            model=self.model,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return chat_completion.choices[0].message.content or "{}"
