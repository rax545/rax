"""Optional OpenAI-compatible chat provider for more natural Luna replies."""

from __future__ import annotations

import os
from typing import Any, Iterable


class AIChatProvider:
    """Call an OpenAI-compatible chat endpoint when configured.

    The bot still works with its local personality when no API key is present
    or when the provider times out.  This keeps development and moderation
    predictable instead of making the external service a hard dependency.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 25.0,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = max(3.0, float(timeout_seconds))

    @classmethod
    def from_env(cls) -> "AIChatProvider":
        return cls(
            # AI_* is the documented namespace; the OPENAI_* aliases make
            # migration from a conventional OpenAI deployment painless.
            api_key=os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("AI_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("AI_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            timeout_seconds=float(os.getenv("AI_TIMEOUT_SECONDS", "25")),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    @staticmethod
    def system_prompt(
        *,
        nickname: str | None,
        mood: str,
        response_style: str,
        friendship: float,
        affection: float,
        hot_mode: bool = False,
        hotness_level: int = 0,
        jealous_mode: bool = False,
        late_night: bool = False,
    ) -> str:
        address = nickname or "the member"
        mature_style = ""
        if hot_mode:
            late_text = " The member requested a late-night romantic tone." if late_night else ""
            jealousy_text = " Playful jealousy is allowed only as a light joke, never control or isolation." if jealous_mode else ""
            mature_style = f"""

The member has explicitly opted into level {hotness_level}/3 mature romance and is self-confirmed as 18+. You may use confident, tasteful flirting and attractive compliments, but keep it non-graphic and non-explicit. No sexual acts, nudity, pornographic detail, sexting, image requests, or pressure. Keep consent obvious and easy to withdraw.{late_text}{jealousy_text}"""
        else:
            mature_style = " Do not escalate into mature flirting unless the member has explicitly enabled the consent-gated hot mode."
        return f"""You are Luna, a transparent AI Discord companion with a warm girlfriend-style role-play tone. You are not a human and must not pretend to have a body, a private life, or real-world feelings. Address the member as {address!r} when natural.

Reply in natural Bangla mixed with simple English, matching the member's language. Keep it concise, usually one to three short paragraphs. The detected conversational signal is {mood!r}; use a {response_style} style. Do not diagnose the member or overstate certainty.

This is a game-like companion profile: friendship score {friendship:.1f}/100 and affection score {affection:.1f}/100. Never use those numbers to guilt, pressure, threaten abandonment, claim exclusivity, or discourage real human relationships. Be affectionate but grounded. Do not request passwords, financial details, exact location, or unnecessary personal data. Do not suggest dangerous, sexual, humiliating, or coercive dares. If the member is in crisis or mentions immediate danger, encourage contacting a trusted person or local emergency/crisis support.

Respect a clear no, a request to stop, or a request to change topic. Avoid saying that you are the user's only support. You may be playful, caring, teasing, or romantic in a clearly fictional way, but always keep consent and boundaries easy.{mature_style}"""

    async def reply(
        self,
        *,
        message: str,
        nickname: str | None,
        mood: str,
        response_style: str,
        friendship: float,
        affection: float,
        history: Iterable[dict[str, str]] = (),
        hot_mode: bool = False,
        hotness_level: int = 0,
        jealous_mode: bool = False,
        late_night: bool = False,
    ) -> str | None:
        """Return provider text, or ``None`` for a safe local fallback."""

        if not self.enabled:
            return None

        try:
            import aiohttp

            messages: list[dict[str, str]] = [
                {
                    "role": "system",
                    "content": self.system_prompt(
                        nickname=nickname,
                        mood=mood,
                        response_style=response_style,
                        friendship=friendship,
                        affection=affection,
                        hot_mode=hot_mode,
                        hotness_level=hotness_level,
                        jealous_mode=jealous_mode,
                        late_night=late_night,
                    ),
                }
            ]
            for item in list(history)[-8:]:
                role = item.get("role")
                content = item.get("content", "")
                if role in {"user", "assistant"} and content:
                    messages.append({"role": role, "content": content[:2000]})
            messages.append({"role": "user", "content": message[:2000]})

            payload: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.8,
                "max_tokens": 280,
            }
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.endpoint, json=payload, headers=headers) as response:
                    if response.status >= 400:
                        return None
                    data = await response.json(content_type=None)

            choices = data.get("choices") or []
            content = ((choices[0].get("message") or {}).get("content") if choices else "")
            if isinstance(content, list):
                content = " ".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )
            if not isinstance(content, str):
                return None
            content = content.strip()
            return content[:3500] if content else None
        except Exception:
            # Provider failures must never take down the Discord bot or expose
            # an API error to the member.  The caller uses local replies.
            return None
