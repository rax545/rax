"""Small, privacy-friendly mood classifier used by Luna.

The classifier deliberately works locally by default.  It does not try to
 diagnose a mental-health condition; it only chooses a conversational style
 for the next reply.  An optional hosted chat model may use the result as
 context, but the raw message is never persisted by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class MoodResult:
    """The conversational mood inferred from one message."""

    mood: str
    confidence: float
    signals: tuple[str, ...] = ()

    @property
    def emoji(self) -> str:
        return {
            "joyful": "😊",
            "sad": "🥺",
            "stressed": "🌿",
            "angry": "😤",
            "romantic": "💗",
            "tired": "🌙",
            "neutral": "🙂",
        }.get(self.mood, "🙂")

    @property
    def response_style(self) -> str:
        return {
            "joyful": "playful, celebratory and energetic",
            "sad": "gentle, validating and supportive; avoid teasing",
            "stressed": "calm, concise and reassuring",
            "angry": "patient, non-judgmental and de-escalating",
            "romantic": "warm and affectionate while staying grounded",
            "tired": "soft, caring and low-pressure",
            "neutral": "warm, lightly playful and conversational",
        }.get(self.mood, "warm and conversational")


# Bengali and English phrases are intentionally short and explainable.  This
# is a style signal, not a clinical assessment.
_KEYWORDS: dict[str, tuple[str, ...]] = {
    "romantic": (
        "ভালোবাসি",
        "ভালবাসি",
        "ভালোবাসো",
        "ভালবাসো",
        "ভালোবাসা",
        "ভালবাসা",
        "love",
        "lovely",
        "miss you",
        "মিস করি",
        "মিস করছি",
        "প্রিয়",
        "প্রেম",
        "kiss",
        "কিউট",
        "cute",
        "sweet",
        "ভালো লাগে",
        "ভাল লাগে",
        "like you",
        "adore",
        "crush",
        "attracted",
    ),
    "sad": (
        "মন খারাপ",
        "মনটা খারাপ",
        "কষ্ট",
        "খারাপ লাগছে",
        "খারাপ লাগা",
        "কাঁদছি",
        "কান্না",
        "একা লাগছে",
        "দুঃখ",
        "sad",
        "cry",
        "hurt",
        "lonely",
        "depressed",
        "নিরাশ",
        "bad day",
        "rough day",
        "terrible day",
        "খারাপ দিন",
        "দিনটা খারাপ",
    ),
    "stressed": (
        "চাপ",
        "টেনশন",
        "দুশ্চিন্তা",
        "উদ্বিগ্ন",
        "পরীক্ষা",
        "ডেডলাইন",
        "ব্যস্ত",
        "stress",
        "stressed",
        "anxious",
        "worried",
        "deadline",
        "overwhelmed",
    ),
    "angry": (
        "রাগ",
        "রেগে",
        "ক্ষুব্ধ",
        "বিরক্ত",
        "সহ্য হচ্ছে না",
        "রাগান্বিত",
        "angry",
        "mad",
        "annoyed",
        "furious",
        "hate",
    ),
    "tired": (
        "ক্লান্ত",
        "ঘুম পাচ্ছে",
        "ঘুমাব",
        "ঘুমাতে চাই",
        "অবসন্ন",
        "tired",
        "sleepy",
        "exhausted",
        "need sleep",
    ),
    "joyful": (
        "খুশি",
        "আনন্দ",
        "দারুণ",
        "মজা",
        "জিতেছি",
        "সফল",
        "হাসি",
        "happy",
        "great",
        "awesome",
        "yay",
        "win",
        "won",
        "excited",
        "হাহা",
        "haha",
    ),
}

# Longer phrases are checked first so that a phrase such as "মন খারাপ" is
# not accidentally interpreted as a generic occurrence of "খারাপ" later.
_SORTED_KEYWORDS = {
    mood: tuple(sorted(words, key=len, reverse=True))
    for mood, words in _KEYWORDS.items()
}


def _normalise(message: str) -> str:
    message = unicodedata.normalize("NFKC", message or "").strip().lower()
    return re.sub(r"\s+", " ", message)


def detect_mood(message: str) -> MoodResult:
    """Infer a reply style from *message* without storing its contents.

    The result is deterministic, inexpensive, and intentionally conservative:
    when no useful signal is present Luna remains neutral rather than guessing
    a user's emotional state.
    """

    text = _normalise(message)
    if not text:
        return MoodResult("neutral", 0.0, ())

    scores: dict[str, float] = {mood: 0.0 for mood in _KEYWORDS}
    signals: dict[str, list[str]] = {mood: [] for mood in _KEYWORDS}

    for mood, words in _SORTED_KEYWORDS.items():
        for word in words:
            # Bengali does not have word boundaries, so substring matching is
            # more useful there.  English is still protected from matching a
            # fragment inside an unrelated word.
            if re.search(r"[a-z]", word):
                found = bool(re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", text))
            else:
                found = word in text
            if found:
                scores[mood] += 1.0 + min(len(word) / 24.0, 0.75)
                signals[mood].append(word)

    # Punctuation and casing are weak signals only.  They help distinguish
    # excitement or frustration, but never override explicit words.
    exclamations = text.count("!")
    question_marks = text.count("?")
    latin_letters = [char for char in message if "a" <= char.lower() <= "z"]
    if latin_letters and sum(char.isupper() for char in latin_letters) / len(latin_letters) > 0.7:
        scores["angry"] += 0.45
        signals["angry"].append("uppercase emphasis")
    if exclamations >= 2:
        scores["joyful"] += 0.35
        signals["joyful"].append("excited punctuation")
    if question_marks >= 3:
        scores["stressed"] += 0.15
        signals["stressed"].append("repeated questions")

    best_mood = max(scores, key=scores.get)
    best_score = scores[best_mood]
    if best_score <= 0:
        return MoodResult("neutral", 0.25, ())

    # Confidence is a communication hint, not a probability claim.
    total = sum(score for score in scores.values())
    confidence = min(0.98, max(0.35, best_score / max(total, 1.0)))
    return MoodResult(best_mood, round(confidence, 2), tuple(signals[best_mood][:4]))


def mood_label(mood: str, confidence: float | None = None) -> str:
    """Return a human-readable label for status messages."""

    result = MoodResult(mood if mood in _KEYWORDS or mood == "neutral" else "neutral", confidence or 0.0)
    confidence_text = f" ({round(result.confidence * 100)}%)" if confidence is not None else ""
    return f"{result.emoji} {result.mood.title()}{confidence_text}"
