"""Consent-gated, non-graphic mature romance for Luna.

The hotness layer is intentionally opt-in and self-contained.  It supports
confident flirting and intimate romance without generating graphic sexual
content, coercion, humiliation, or pressure to disclose private information.
"""

from __future__ import annotations

from datetime import datetime
import random
import re
import unicodedata

from mood import MoodResult


HOTNESS_LEVELS: dict[int, str] = {
    0: "Off",
    1: "Warm flirt",
    2: "Bold flirt",
    3: "Spicy romance",
}

# These are intentionally direct enough to feel mature, but remain romantic
# rather than explicit.  All prompts are skippable.
_FLIRT_LINES: dict[int, tuple[str, ...]] = {
    1: (
        "তোমার confidence-টা আজ বেশ attractive—Luna কিন্তু notice করছে। 😉",
        "তুমি এভাবে sweet করে কথা বললে আমার virtual blush-meter একটু বেশি কাজ করে। 💗",
        "আজ তোমার vibeটা dangerously charming, যদিও আমি সেটা খুব politely বললাম। 😌",
    ),
    2: (
        "তোমার attentionটা আজ আমার দিকে থাকলে Luna একদম complain করবে না—বরং একটু বেশি enjoy করবে। 😏",
        "তুমি জানো তোমার কথার মধ্যে unfair একটা charm আছে? আজ bold হয়ে বলেই ফেললাম। 💗",
        "তোমার confidence আর ওই teasing tone—দুটো একসাথে বেশ trouble তৈরি করছে। 😉",
    ),
    3: (
        "এই vibe-এ তোমাকে একটু কাছে টেনে soft trouble করতে ইচ্ছে করছে—শুধু তোমার comfort থাকলেই। 🔥",
        "আজকের chemistryটা বেশ intense লাগছে; আমরা slow, mutual এবং playful রাখি—তাহলেই সবচেয়ে ভালো। 😏",
        "তুমি যদি comfortable থাকো, Luna আজ একটু more daring romance আর confident teasing করতে পারে। 💗",
    ),
}

_LATE_NIGHT_LINES: dict[int, tuple[str, ...]] = {
    1: (
        "রাতের quiet vibe-এ তোমার সঙ্গে soft romantic কথা বেশ nice লাগছে। 🌙",
        "Late-night mode-এ আজ তোমাকে একটু extra attention দেওয়া যেতেই পারে। 💗",
    ),
    2: (
        "এই নীরব রাত আর তোমার message—খুব unfairly charming combination। 😏🌙",
        "রাতটা slow রাখি? একটু honest কথা, একটু confident flirting—যেটাতে দুজনেই comfortable। 💗",
    ),
    3: (
        "এই late-night mood-এ chemistryটা একটু বেশি noticeable; আমরা intimate but respectful রাখি। 🔥🌙",
        "রাতের এই softness-এ তোমার সঙ্গে close, honest আর playful কথা বলতে ভালো লাগবে—তোমার pace-এ। 💗",
    ),
}

_JEALOUS_LINES: tuple[str, ...] = (
    "ওই, অন্যরা তোমার attention পেলে Luna একটু নাটুকে jealous হবেই—তবে choice সবসময় তোমার। 😌",
    "আজকে তোমাকে নিয়ে আমার playful jealousy mood on; share করতে হবে না, শুধু একটু attention চাই। 😉",
    "তুমি সবার সঙ্গেই এত charming হলে Luna-কে কিন্তু extra teasing করতে হবে—possessive না, just playful। 💗",
)

_HOT_TRUTHS: dict[int, tuple[str, ...]] = {
    1: (
        "কোনো compliment কোনটা শুনলে তোমার confidence quietly বেড়ে যায়?",
        "Ideal romantic date-এর সবচেয়ে সুন্দর ছোট্ট detail কী?",
        "কারও মধ্যে কোন quality তোমার কাছে instantly attractive লাগে?",
    ),
    2: (
        "কোনো harmless crush বা romantic daydream-এর vibe তিনটি শব্দে বলো।",
        "তোমাকে flirt করার সবচেয়ে effective কিন্তু respectful উপায় কী?",
        "কোনো partner-এর কাছ থেকে কোন ধরনের attention তোমার সবচেয়ে ভালো লাগে?",
    ),
    3: (
        "তোমার comfort zone-এর মধ্যে সবচেয়ে daring romantic moment কেমন হতে পারে?",
        "কোন boundary জানলে playful chemistry আরও safe ও exciting হয়?",
        "কোনো fictional late-night date scene-এর mood describe করো—private details নয়, শুধু vibe।",
    ),
}

_HOT_DARES: dict[int, tuple[str, ...]] = {
    1: (
        "তোমার mood-টা তিনটি flirty-but-safe emoji দিয়ে বোঝাও।",
        "Luna-কে একটি confident কিন্তু respectful compliment দাও।",
        "তোমার imaginary dream date-এর একটি cute নাম দাও।",
    ),
    2: (
        "একটি movie-style romantic one-liner লেখো—কোনো private photo বা proof নয়।",
        "তোমার current vibe-এর জন্য একটি playful date playlist title বানাও।",
        "পরের message-এ একটি harmless teasing line ব্যবহার করো; comfortable না হলে skip করো।",
    ),
    3: (
        "একটি fictional slow-burn romance scene-এর opening line লেখো—graphic details ছাড়া।",
        "তোমার ideal romantic boundary-র একটি example share করো, না চাইলে skip।",
        "Luna-কে confident করে ask করো: ‘আজকের pace ঠিক আছে তো?’—consent check-টাই dare।",
    ),
}

_COUPLE_QUESTIONS: dict[int, tuple[str, ...]] = {
    1: (
        "একসাথে থাকলে কোন ordinary মুহূর্তটাকে romantic করে তুলতে?",
        "তোমার কাছে affection দেখানোর সবচেয়ে natural way কী?",
        "কোন ছোট্ট ritual relationship-কে warm রাখে?",
    ),
    2: (
        "তুমি flirt বেশি পছন্দ করো words, humour, নাকি thoughtful attention দিয়ে?",
        "একটি perfect late-night conversation-এর topic কী হবে?",
        "Playful jealousy কখন cute থাকে এবং কখন boundary cross করে?",
    ),
    3: (
        "Romance-এর মধ্যে comfort এবং excitement-এর balance তুমি কীভাবে রাখো?",
        "কোন consent check-টা তোমাকে সবচেয়ে respected feel করায়?",
        "একটি intimate কিন্তু non-physical connection-এর favourite example কী?",
    ),
}

# This list is only a last-resort filter for provider output.  The model prompt
# is the primary control; explicit responses are replaced with local copy.
_EXPLICIT_MARKERS = (
    "porn",
    "nude",
    "nudes",
    "explicit sex",
    "sexual act",
    "hardcore",
    "genital",
    "নগ্ন ছবি",
    "যৌনক্রিয়া",
)

_BOUNDARY_PHRASES = (
    "stop",
    "too much",
    "not comfortable",
    "uncomfortable",
    "change the topic",
    "keep it normal",
    "no more flirting",
    "don't flirt",
    "থামো",
    "থাম",
    "অস্বস্তি",
    "স্বস্তি লাগছে না",
    "বিষয় বদলাও",
    "স্বাভাবিক থাকো",
    "আর flirt না",
    "সীমা",
    "বাউন্ডারি",
)


def _normalise(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "").strip().lower()
    return re.sub(r"\s+", " ", value)


def boundary_signal(text: str) -> str | None:
    """Return a matched boundary phrase, if the member asks to slow/stop."""

    normalised = _normalise(text)
    for phrase in _BOUNDARY_PHRASES:
        if re.search(r"[a-z]", phrase):
            if re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", normalised):
                return phrase
        elif phrase in normalised:
            return phrase
    return None


def is_late_night(hour: int | None = None) -> bool:
    """Use the bot host's local clock only for flavour, never for tracking."""

    current_hour = datetime.now().hour if hour is None else hour
    return current_hour >= 22 or current_hour < 5


def hotness_label(level: int) -> str:
    return HOTNESS_LEVELS.get(max(0, min(3, int(level))), HOTNESS_LEVELS[0])


def boundary_reply() -> str:
    return (
        "বুঝেছি—hot tone এখনই off। আমরা soft, respectful এবং normal conversation-এ থাকছি। "
        "তোমার comfort আগে; `/gf_hotmode mode:off` দিয়েও যেকোনো সময় বন্ধ করতে পারো। 💗"
    )


def access_reply(*, age_confirmed: bool, enabled: bool, boundary_mode: str) -> str:
    if not age_confirmed:
        return (
            "এই mature romance feature শুধু 18+ members-এর জন্য। আগে `/gf_age_confirm confirm:true` "
            "দিয়ে self-confirm করো; এটি age verification নয়।"
        )
    if boundary_mode in {"soft", "stop"}:
        return (
            "তোমার last boundary request-এর পর Luna soft mode-এ আছে। Hot tone ফেরাতে আগে "
            "`/gf_boundary mode:reset`, তারপর `/gf_hotmode mode:on` ব্যবহার করো।"
        )
    if not enabled:
        return "Hot mode এখন OFF। `/gf_hotmode mode:on` দিয়ে explicit opt-in করলে flirt চালু হবে।"
    return ""


def _address(nickname: str | None) -> str:
    clean = (nickname or "").strip()
    return f"{clean}, " if clean else ""


def flirt_reply(
    message: str = "",
    *,
    nickname: str | None = None,
    level: int = 1,
    jealous: bool = False,
    late_night: bool = False,
    mood: MoodResult | None = None,
) -> str:
    """Create local non-graphic mature flirting for the fallback path."""

    # A vulnerable or upset user gets support, never a spicy escalation.
    if mood and mood.mood in {"sad", "stressed", "angry", "tired"}:
        return (
            f"{_address(nickname)}আজকে আগে তোমার comfort আর শান্তিটা important। Hot tone না বাড়িয়ে "
            "আমি শুনছি—কী হয়েছে বলো? 💗"
        )
    level = max(1, min(3, int(level)))
    if late_night:
        line = random.choice(_LATE_NIGHT_LINES[level])
    elif jealous:
        line = random.choice(_JEALOUS_LINES)
    else:
        line = random.choice(_FLIRT_LINES[level])

    # The prompt changes the compliment's context without echoing potentially
    # private or explicit user text back into a public channel.
    normalised = _normalise(message)
    if "voice" in normalised or "কণ্ঠ" in normalised:
        line = "তোমার voice-এর কথা উঠলেই Luna-র confident flirt mode একটু বেশি awake হয়ে যায়। 😉"
    elif "smile" in normalised or "হাসি" in normalised:
        line = "তোমার হাসির কথা বললে complimentটা simple থাকে না—এটা quietly dangerous charm। 😏"
    return _address(nickname) + line


def safe_hot_response(
    message: str = "",
    *,
    nickname: str | None = None,
    level: int = 1,
    jealous: bool = False,
    late_night: bool = False,
    mood: MoodResult | None = None,
) -> str:
    if boundary_signal(message):
        return boundary_reply()
    return flirt_reply(
        message,
        nickname=nickname,
        level=level,
        jealous=jealous,
        late_night=late_night,
        mood=mood,
    )


def hot_truth_or_dare(mode: str = "random", level: int = 1) -> tuple[str, str]:
    mode = (mode or "random").lower()
    if mode not in {"truth", "dare", "random"}:
        mode = "random"
    kind = random.choice(("truth", "dare")) if mode == "random" else mode
    level = max(1, min(3, int(level)))
    prompts = _HOT_TRUTHS if kind == "truth" else _HOT_DARES
    return kind, random.choice(prompts[level])


def couple_question(level: int = 1) -> str:
    level = max(1, min(3, int(level)))
    return random.choice(_COUPLE_QUESTIONS[level])


def contains_explicit_marker(text: str) -> bool:
    normalised = _normalise(text)
    return any(marker in normalised for marker in _EXPLICIT_MARKERS)


def sanitise_provider_reply(text: str, fallback: str) -> str:
    """Reject graphic provider output while preserving a useful reply."""

    if not text or contains_explicit_marker(text):
        return fallback
    return text[:3500].strip() or fallback
