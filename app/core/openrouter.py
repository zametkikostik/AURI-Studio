from openai import AsyncOpenAI, OpenAI
from app.config import settings
from typing import List, Dict, Any, Optional
import base64
from pathlib import Path
import logging

logger = logging.getLogger("auri.openrouter")


class OpenRouterClient:
    """
    Единая точка доступа ко всем моделям через OpenRouter.
    Полностью совместим с OpenAI SDK.
    Работает на Windows / Linux / Android (Termux).
    """

    def __init__(self):
        if not settings.OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY не задан! Укажите его в .env")

        self.client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY or "dummy",
            base_url=settings.OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://github.com/auri-studio/auri",
                "X-Title": "AURI Studio",
            },
            timeout=180.0,
        )
        self.sync_client = OpenAI(
            api_key=settings.OPENROUTER_API_KEY or "dummy",
            base_url=settings.OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://github.com/auri-studio/auri",
                "X-Title": "AURI Studio",
            },
            timeout=180.0,
        )

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        response_format: Optional[Dict] = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        model = model or settings.DEFAULT_LLM_MODEL

        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        if response_format:
            params["response_format"] = response_format

        response = await self.client.chat.completions.create(**params)
        return response.choices[0].message.content or ""

    async def vision_describe(
        self,
        image_path: str | Path,
        prompt: str = (
            "Опиши подробно, что происходит на этом кадре. "
            "Укажи объекты, действия, эмоции, текст на экране, атмосферу. "
            "Отвечай на русском, 2-4 предложения."
        ),
        model: Optional[str] = None,
    ) -> str:
        model = model or settings.DEFAULT_VISION_MODEL
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        suffix = image_path.suffix.lower()
        mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(suffix, "image/jpeg")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            }
        ]
        return await self.chat(messages, model=model, temperature=0.2, max_tokens=600)

    async def transcribe(
        self,
        audio_path: str | Path,
        model: Optional[str] = None,
        language: str = "ru",
    ) -> Dict[str, Any]:
        model = model or settings.DEFAULT_WHISPER_MODEL
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio not found: {audio_path}")

        with open(audio_path, "rb") as f:
            transcript = await self.client.audio.transcriptions.create(
                model=model,
                file=f,
                response_format="verbose_json",
                language=language,
                timestamp_granularities=["word", "segment"],
            )

        if hasattr(transcript, "model_dump"):
            return transcript.model_dump()
        return dict(transcript)


openrouter = OpenRouterClient()
