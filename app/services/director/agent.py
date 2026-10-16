from typing import List, Dict, Any, Optional
import json
import re
import logging

from app.core.openrouter import openrouter
from app.services.director.prompts import DIRECTOR_SYSTEM_PROMPT
from app.config import settings

logger = logging.getLogger("auri.director")


class DirectorAgent:
    """Агент-режиссёр: ТЗ + транскрипт + кадры → JSON Timeline Blueprint."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.DEFAULT_LLM_MODEL

    async def create_timeline(
        self,
        user_brief: str,
        transcript: Dict[str, Any],
        frame_descriptions: List[Dict[str, Any]],
        source_id: str = "main",
    ) -> Dict[str, Any]:
        words = transcript.get("words") or []
        if not words and "segments" in transcript:
            words = []
            for seg in transcript["segments"]:
                words.append({
                    "start": seg.get("start", 0),
                    "end": seg.get("end", 0),
                    "word": seg.get("text", ""),
                })

        compact_words = [
            {"start": round(w.get("start", 0), 2), "end": round(w.get("end", 0), 2), "word": w.get("word", w.get("text", ""))}
            for w in words[:800]
        ]

        frames_text = "\n".join(
            f"[{f['timestamp']:.2f}s] {f['description']}"
            for f in frame_descriptions
        )

        user_content = f"""
### ТЕХНИЧЕСКОЕ ЗАДАНИЕ ПОЛЬЗОВАТЕЛЯ
{user_brief}

### ТРАНСКРИПТ (word-level, секунды)
{json.dumps(compact_words, ensure_ascii=False)}

### ОПИСАНИЯ КЛЮЧЕВЫХ КАДРОВ
{frames_text}

### SOURCE_ID
{source_id}

Создай монтажный план строго в JSON по схеме из системного промпта.
"""

        messages = [
            {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        logger.info(f"Director calling model={self.model}")
        raw = await openrouter.chat(
            messages=messages,
            model=self.model,
            temperature=0.25,
            response_format={"type": "json_object"},
            max_tokens=4096,
        )

        plan = self._parse_json(raw)

        if "clips" not in plan or not plan["clips"]:
            raise ValueError("Director вернул план без клипов")

        for clip in plan["clips"]:
            clip.setdefault("source_id", source_id)
            clip.setdefault("speed", 1.0)
            clip.setdefault("transition", "cut")
            clip["start"] = float(clip["start"])
            clip["end"] = float(clip["end"])
            if clip["end"] <= clip["start"]:
                clip["end"] = clip["start"] + 1.0

        return plan

    def _parse_json(self, raw: str) -> Dict[str, Any]:
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                return json.loads(match.group(0))
            raise ValueError(f"Не удалось распарсить JSON от Director:\n{raw[:500]}")
