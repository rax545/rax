"""Discord voice playback with pluggable TTS providers."""

from __future__ import annotations

import asyncio
from pathlib import Path
import os
import shutil
import time
import uuid
from typing import Any

import discord


class VoiceUnavailable(RuntimeError):
    """Raised when the voice channel or TTS setup cannot speak."""


class _OpenAITTS:
    def __init__(self, api_key: str, base_url: str, model: str, voice: str, timeout: float) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.voice = voice
        self.timeout = max(3.0, timeout)

    @property
    def endpoint(self) -> str:
        if self.base_url.endswith("/audio/speech"):
            return self.base_url
        return f"{self.base_url}/audio/speech"

    async def synthesize(self, text: str, destination: Path) -> None:
        import aiohttp

        payload: dict[str, Any] = {
            "model": self.model,
            "input": text,
            "voice": self.voice,
            "response_format": "mp3",
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.endpoint, json=payload, headers=headers) as response:
                if response.status >= 400:
                    detail = (await response.text())[:200]
                    raise VoiceUnavailable(f"TTS provider returned HTTP {response.status}: {detail}")
                destination.write_bytes(await response.read())


class _EspeakTTS:
    def __init__(self, command: str, voice: str, timeout: float) -> None:
        self.command = command
        self.voice = voice
        self.timeout = max(3.0, timeout)

    async def synthesize(self, text: str, destination: Path) -> None:
        process = await asyncio.create_subprocess_exec(
            self.command,
            "-v",
            self.voice,
            "-w",
            str(destination),
            text,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise VoiceUnavailable("Local TTS timed out")
        if process.returncode != 0 or not destination.exists() or destination.stat().st_size == 0:
            detail = stderr.decode(errors="replace")[-200:] if stderr else ""
            raise VoiceUnavailable(f"Local TTS failed: {detail}")


class VoiceService:
    """Turn text into short audio clips and play them in a Discord VC."""

    def __init__(
        self,
        *,
        provider: str = "auto",
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini-tts",
        voice: str = "nova",
        ffmpeg_path: str = "ffmpeg",
        local_command: str = "espeak-ng",
        local_voice: str = "en",
        timeout_seconds: float = 30.0,
        cache_dir: str = "data/voice_cache",
    ) -> None:
        self.provider = (provider or "auto").lower()
        self.api_key = (api_key or "").strip()
        self.base_url = base_url
        self.model = model
        self.voice = voice
        self.ffmpeg_path = ffmpeg_path
        self.local_command = local_command
        self.local_voice = local_voice
        self.timeout_seconds = max(3.0, float(timeout_seconds))
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._synthesis_lock = asyncio.Lock()

    @classmethod
    def from_env(cls) -> "VoiceService":
        return cls(
            provider=os.getenv("TTS_PROVIDER", "auto"),
            api_key=os.getenv("TTS_API_KEY") or os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=(
                os.getenv("TTS_BASE_URL")
                or os.getenv("AI_BASE_URL")
                or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            ),
            model=os.getenv("TTS_MODEL", "gpt-4o-mini-tts"),
            voice=os.getenv("TTS_VOICE", "nova"),
            ffmpeg_path=os.getenv("FFMPEG_PATH", "ffmpeg"),
            local_command=os.getenv("LOCAL_TTS_COMMAND", "espeak-ng"),
            local_voice=os.getenv("LOCAL_TTS_VOICE", "en"),
            timeout_seconds=float(os.getenv("TTS_TIMEOUT_SECONDS", "30")),
            cache_dir=os.getenv("VOICE_CACHE_DIR", "data/voice_cache"),
        )

    @property
    def external_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def local_configured(self) -> bool:
        return bool(shutil.which(self.local_command))

    @property
    def ffmpeg_configured(self) -> bool:
        return bool(shutil.which(self.ffmpeg_path) or Path(self.ffmpeg_path).exists())

    @property
    def status(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "external_configured": self.external_configured,
            "local_configured": self.local_configured,
            "ffmpeg_configured": self.ffmpeg_configured,
            "model": self.model,
            "voice": self.voice,
        }

    def _providers(self) -> list[Any]:
        if self.provider in {"none", "off", "disabled"}:
            return []
        providers: list[Any] = []
        if self.provider in {"auto", "openai", "api", "external"} and self.api_key:
            providers.append(
                _OpenAITTS(
                    self.api_key,
                    self.base_url,
                    self.model,
                    self.voice,
                    self.timeout_seconds,
                )
            )
        if self.provider in {"auto", "local", "espeak", "espeak-ng"} and self.local_configured:
            providers.append(_EspeakTTS(self.local_command, self.local_voice, self.timeout_seconds))
        return providers

    async def _synthesize(self, text: str) -> Path:
        providers = self._providers()
        if not providers:
            raise VoiceUnavailable(
                "No TTS provider is configured. Set TTS_API_KEY or install local espeak-ng."
            )
        last_error: Exception | None = None
        for provider in providers:
            suffix = ".mp3" if isinstance(provider, _OpenAITTS) else ".wav"
            path = self.cache_dir / f"luna-{int(time.time() * 1000)}-{uuid.uuid4().hex}{suffix}"
            try:
                await provider.synthesize(text, path)
                return path
            except Exception as exc:
                last_error = exc
                path.unlink(missing_ok=True)
        raise VoiceUnavailable(str(last_error or "TTS provider failed"))

    async def speak(self, voice_client: discord.VoiceClient, text: str) -> None:
        """Synthesize and play one clip, replacing an older clip if needed."""

        if not voice_client or not voice_client.is_connected():
            raise VoiceUnavailable("Luna is not connected to a voice channel")
        clean_text = " ".join((text or "").split())
        if not clean_text:
            raise VoiceUnavailable("There is nothing to say")
        if len(clean_text) > 700:
            clean_text = clean_text[:697] + "..."

        async with self._synthesis_lock:
            audio_path = await self._synthesize(clean_text)
            if voice_client.is_playing():
                voice_client.stop()
            try:
                source = discord.FFmpegPCMAudio(
                    str(audio_path),
                    executable=self.ffmpeg_path,
                    options="-vn",
                )
                loop = asyncio.get_running_loop()

                def after_playback(error: Exception | None) -> None:
                    if error:
                        # Playback errors are logged by the Discord client; the
                        # temporary file still must be removed.
                        pass
                    try:
                        loop.call_soon_threadsafe(audio_path.unlink, True)
                    except Exception:
                        audio_path.unlink(missing_ok=True)

                voice_client.play(source, after=after_playback)
            except Exception as exc:
                audio_path.unlink(missing_ok=True)
                raise VoiceUnavailable(f"Audio playback unavailable: {exc}") from exc
