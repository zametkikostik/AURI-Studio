from openai import AsyncOpenAI, OpenAI
from app.config import settings
from typing import List, Dict, Any, Optional
import base64
from pathlib import Path
import logging
import json

logger = logging.getLogger("auri.openrouter")

_runtime_api_key: Optional[str] = None


def get_api_key() -> str:
    if _runtime_api_key:
        return _runtime_api_key
    return settings.OPENROUTER_API_KEY or ""


def set_api_key(key: str) -> None:
    global _runtime_api_key
    key = (key or "").strip()
    _runtime_api_key = key if key else None
    try:
        path = Path(settings.STORAGE_ROOT) / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        data["openrouter_api_key"] = key
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not persist API key: {e}")
    openrouter.reset_clients()


def load_persisted_key() -> None:
    global _runtime_api_key
    try:
        path = Path(settings.STORAGE_ROOT) / "settings.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            key = (data.get("openrouter_api_key") or "").strip()
            if key:
                _runtime_api_key = key
                logger.info("Loaded OpenRouter API key from settings.json")
    except Exception as e:
        logger.warning(f"Could not load persisted API key: {e}")


class OpenRouterClient:
    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self._sync_client: Optional[OpenAI] = None

    def reset_clients(self) -> None:
        self._client = None
        self._sync_client = None

    def _ensure_key(self) -> str:
        key = get_api_key()
        if not key:
            raise RuntimeError(
                "OpenRouter API key не задан. "
                "Вставьте ключ в веб-интерфейсе (Настройки) или в .env (OPENROUTER_API_KEY)."
            )
        return key

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            key = self._ensure_key()
            self._client = AsyncOpenAI(
                api_key=key,
                base_url=settings.OPENROUTER_BASE_URL,
                default_headers={
                    "HTTP-Referer": "https://github.com/zametkikostik/AURI-Studio",
                    "X-Title": "AURI Studio",
                },
                timeout=180.0,
            )
        return self._client

    @property
    def sync_client(self) -> OpenAI:
        if self._sync_client is None:
            key = self._ensure_key()
            self._sync_client = OpenAI(
                api_key=key,
                base_url=settings.OPENROUTER_BASE_URL,
                default_headers={
                    "HTTP-Referer": "https://github.com/zametkikostik/AURI-Studio",
                    "X-Title": "AURI Studio",
                },
                timeout=180.0,
            )
        return self._sync_client

    @property
    def is_configured(self) -> bool:
        return bool(get_api_key())

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
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(suffix, "image/jpeg")
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }]
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
