"""Luna's local fallback personality and mood-aware response copy."""

from __future__ import annotations

import random

from mood import MoodResult, detect_mood


LINES = [
    "তোমার confidence দেখে Wi-Fi-ও connect হতে লজ্জা পায়। 😭",
    "এই যে Mr. Busy, online আছো—কিন্তু brain কি maintenance-এ? 😂",
    "তোমার reply speed দেখে কচ্ছপও নিজেকে fast ভাবে। 🐢",
    "আজকে এত চুপ কেন? Keyboard-এর সাথে breakup হয়েছে নাকি? 💅",
    "তুমি legendary… তবে কোন category-তে সেটা এখনো গবেষণাধীন। 🤣",
    "একটু পানি খাও, এত attitude-এ তো গলা শুকিয়ে যাবে। 💗",
    "তোমার plan শুনে Google Maps-ও বলে: destination not found. 😭",
    "নিজেকে main character ভাবো, কিন্তু scene-এ ঢুকতে দেরি করো কেন? 🎬",
    "ঘুমাও একটু, পৃথিবী তোমার notification ছাড়াও চলবে। 🌙",
    "তোমার jokes এত dry যে মরুভূমি পানি দিতে এসেছে। 🏜️",
]

REPLIES = [
    "হুম, শুনছি। কিন্তু এত drama কেন, বলো তো? 💗",
    "আচ্ছা আচ্ছা, তোমার কথাই শেষ কথা… আপাতত। 😌",
    "তুমি cute হতে পারতে, কিন্তু attitude আগে চলে আসে। 😂",
    "আমি আছি, বলো কী হয়েছে? 🥺",
    "এই কথা শুনে আমার virtual heart buffering করছে… 😭",
    "বেশি ভাব নিও না, আমি কিন্তু সব বুঝি। 💅",
]


def random_line() -> str:
    return random.choice(LINES)


def _with_nickname(text: str, nickname: str | None) -> str:
    clean = (nickname or "").strip()
    return f"{clean}, {text}" if clean else text


def reply_line(message: str, nickname: str | None = None, mood: MoodResult | None = None) -> str:
    """Return a local fallback that reacts to the user's conversational mood."""

    msg = (message or "").lower()
    result = mood or detect_mood(message)
    name = nickname

    if result.mood == "sad":
        return _with_nickname(
            "আরে, একা একা carry কোরো না। একটু ধীরে শ্বাস নাও—আমি judgement ছাড়া শুনছি, কী হয়েছে বলো? 💗",
            name,
        )
    if result.mood == "stressed":
        return _with_nickname(
            "চাপটা একবারে সব solve করতে হবে না। এক গ্লাস পানি খেয়ে সবচেয়ে ছোট next step-টা বলো, আমি তোমার সঙ্গে ভাবছি। 🌿",
            name,
        )
    if result.mood == "angry":
        return _with_nickname(
            "উফ, রাগটা সত্যিই heavy শোনাচ্ছে। আগে একটু pause নিই—তুমি চাইলে পুরো ঘটনা বলো, আমি side না নিয়ে শুনব। 😤",
            name,
        )
    if result.mood == "tired":
        return _with_nickname(
            "আজকে low-power mode on করা যাক। পানি খাও, একটু rest নাও—reply দিতে কোনো pressure নেই। 🌙",
            name,
        )
    if result.mood == "romantic":
        return _with_nickname(
            "ওহো, আজকে এত sweet কেন? তোমার virtual companion হিসেবে আমি officially blush-mode-এ গেলাম। 🥺💗",
            name,
        )
    if result.mood == "joyful":
        return _with_nickname(
            "এই energy-টা দারুণ! কী নিয়ে এত খুশি—আমাকেও storyটা বলো, celebrate করি। ✨",
            name,
        )

    if any(x in msg for x in ("hi", "hello", "hey")) or "হাই" in msg:
        return _with_nickname("হেইই! কোথায় ছিলে এতক্ষণ? 😤💗", name)
    return _with_nickname(random.choice(REPLIES), name)


def relationship_address(nickname: str | None, fallback: str = "bestie") -> str:
    """Keep address formatting in one place for embeds and game prompts."""

    return (nickname or fallback).strip()[:32]
