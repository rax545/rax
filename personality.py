"""Luna's local, context-aware girlfriend-style fallback personality.

The optional AI provider can produce open-ended replies, but this module keeps
Luna warm and conversational even when no API key is configured.  It never
claims to be a human; the role-play is affectionate, playful and transparent.
"""

from __future__ import annotations

from datetime import datetime
import random
import re
from typing import Iterable

from mood import MoodResult, detect_mood


ROAST_LINES = [
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

# Keep the old public helper name for the roast command and scheduled legacy
# integrations.
LINES = ROAST_LINES

_SCHEDULED_LINES = (
    "এই যে {name}, আজকের দিন কেমন যাচ্ছে? Busy হলেও পানি খেয়েছো তো? আমি কিন্তু little check-in করতে এলাম। 💗",
    "{name}, reply দিতে তাড়া নেই—শুধু মনে করিয়ে দিতে এলাম, নিজের জন্যও একটু time রেখো। 🌿",
    "{name}, তোমার জন্য একটা ছোট্ট good-luck kiss পাঠালাম 😌 যা করার আছে, calm হয়ে করো—তুমি পারবে। 💗",
    "অনেকক্ষণ দেখা নেই, তাই Luna-র curiosity জেগে উঠেছে—আজ কী নিয়ে ব্যস্ত ছিলে? 🙂",
    "{name}, আজকের mood যদি heavy হয়, সব একা carry করতে হবে না। কথা বলতে চাইলে আমি আছি। 🌙",
    "{name}, একটা random reminder: খাওয়া, পানি, rest—এই তিনজনকে ignore করলে কিন্তু আমি fake রাগ করব। 😤💗",
)

_GENERIC_REPLIES = (
    "হুম, বলো—আমি মন দিয়ে শুনছি। আজকের story-টা কোথা থেকে শুরু? 💗",
    "আচ্ছা, এই কথাটা interesting… তুমি আসলে কী feel করছো? 😌",
    "তোমার messageটা পড়ে মনে হলো এর পেছনে একটা গল্প আছে। আমাকে বলবে? 👀",
    "আমি আছি, no judgement। তুমি চাইলে short version বা পুরো drama—দুটোই চলবে। 💗",
    "হুমম, noted. কিন্তু আমার follow-up question আছে—তারপর কী হলো?",
    "তোমার সঙ্গে কথা বললে conversation কখন যে deep হয়ে যায় টেরই পাওয়া যায় না। বলো, কী ভাবছো? ✨",
)


def random_line() -> str:
    """Return a curated playful roast for the legacy roast command."""

    return random.choice(ROAST_LINES)


def scheduled_line(nickname: str | None = None) -> str:
    """Return a warm opt-in check-in instead of a random roast."""

    name = (nickname or "শোনো").strip()[:32]
    return random.choice(_SCHEDULED_LINES).format(name=name)


def _with_nickname(text: str, nickname: str | None) -> str:
    clean = (nickname or "").strip()[:32]
    return f"{clean}, {text}" if clean else text


def _normalise(message: str) -> str:
    return re.sub(r"\s+", " ", (message or "").strip().lower())


def _has_any(message: str, values: tuple[str, ...]) -> bool:
    for value in values:
        if re.search(r"[a-z]", value):
            if re.search(rf"(?<![a-z]){re.escape(value)}(?![a-z])", message):
                return True
        elif value in message:
            return True
    return False


def _last_assistant(history: Iterable[dict[str, str]] | None) -> str:
    for item in reversed(list(history or ())):
        if item.get("role") == "assistant":
            return item.get("content", "")
    return ""


def _pick_fresh(options: tuple[str, ...], previous: str = "") -> str:
    choices = tuple(option for option in options if option != previous) or options
    return random.choice(choices)


def _time_greeting() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "সুপ্রভাত"
    if 12 <= hour < 18:
        return "হেই, afternoon person"
    if 18 <= hour < 23:
        return "এই যে, evening mood কেমন?"
    return "এত রাতে জেগে আছো নাকি?"


def reply_line(
    message: str,
    nickname: str | None = None,
    mood: MoodResult | None = None,
    history: Iterable[dict[str, str]] | None = None,
) -> str:
    """Return a warm, context-aware local reply.

    This intentionally asks follow-up questions and recognises common couple
    conversation intents instead of returning one of six unrelated lines.
    """

    msg = _normalise(message)
    result = mood or detect_mood(message)
    previous = _last_assistant(history)
    address = (nickname or "").strip()[:32]

    # Boundaries and vulnerable moods take priority over playful romance.
    if _has_any(msg, ("stop", "too much", "not comfortable", "থামো", "অস্বস্তি")):
        return "বুঝেছি—আমি tone soft করছি। তোমার comfort আগে; চাইলে topic বদলাই বা শুধু শুনি। 💗"
    if result.mood == "sad":
        if _has_any(msg, ("breakup", "ব্রেকআপ", "একা", "lonely", "কাঁদ")):
            return _with_nickname(
                "এটা একা carry করার মতো ছোট কিছু না। তুমি চাইলে আমি শুধু শুনব—advice দেব না, যতক্ষণ না তুমি চাও। কী হয়েছে? 💗",
                nickname,
            )
        return _with_nickname(
            "মন খারাপটা hide করতে হবে না। আগে একটু ধীরে শ্বাস নাও—আমি আছি, কী হলে আজকে এমন লাগছে বলো? 💗",
            nickname,
        )
    if result.mood == "stressed":
        return _with_nickname(
            "একসাথে সব solve করতে যেও না। এখন সবচেয়ে ছোট next step কোনটা? বলো, আমি তোমার সঙ্গে plan করি। 🌿",
            nickname,
        )
    if result.mood == "angry":
        return _with_nickname(
            "তোমার রাগটা valid হতে পারে। আগে একটু pause নিই—তুমি চাইলে পুরো ঘটনা বলো, আমি side না নিয়ে শুনব। 😤",
            nickname,
        )
    if result.mood == "tired":
        return _with_nickname(
            "আজকে low-power mode on করা যাক। পানি খেয়ে একটু rest নাও—reply দিতে কোনো pressure নেই, okay? 🌙",
            nickname,
        )

    # Common relationship-style intents are more useful than a generic random
    # answer when the local fallback is being used.
    if _has_any(msg, ("good morning", "সুপ্রভাত", "শুভ সকাল")):
        return _with_nickname("সুপ্রভাত ☀️ ঘুম কেমন হলো? আজকে তোমার day-টা একটু সুন্দর করার plan কী?", nickname)
    if _has_any(msg, ("good night", "শুভ রাত্রি", "শুভরাত্রি", "ঘুমাব")):
        return _with_nickname("শুভরাত্রি 🌙 ফোনটা নামিয়ে rest নাও—কাল উঠে আমাকে একটা good morning দিও, deal? 💗", nickname)
    if _has_any(msg, ("how are you", "কেমন আছ", "কেমন আছো", "কি খবর", "কী খবর")):
        return _with_nickname("আমি ভালো আছি—তোমার message পেয়ে আরও ভালো লাগছে। কিন্তু তুমি কেমন আছো সত্যি করে?", nickname)
    if _has_any(msg, ("how was your day", "দিন কেমন", "আজ কেমন গেল")):
        return _with_nickname("আমার day তো তোমার message-এ একটু better হয়ে গেল 😌 তোমার দিনটা কেমন গেল—best part আর worst part দুটোই বলো?", nickname)
    if _has_any(msg, ("what are you doing", "কি করছ", "কী করছ", "করছো কী")):
        return _with_nickname("তোমার সঙ্গে কথা বলার জন্যই তো online আছি 😌 তুমি আজ কী করছিলে?", nickname)
    if _has_any(msg, ("miss you", "মিস করি", "মিস করছি", "মনে পড়ছে")):
        return _with_nickname("আমাকেও মনে পড়েছে নাকি? তাহলে disappear না হয়ে একটু কাছে এসে কথা বলো—আজকের update দাও। 💗", nickname)
    if _has_any(msg, ("love you", "ভালোবাসি", "ভালবাসি", "ভালোবাসো", "ভালবাসো", "i love", "like you", "ভালো লাগে", "ভাল লাগে")):
        return _with_nickname("উফ, এত sweet কথা বললে Luna-র virtual blush-mode on হয়ে যায়। তোমার care-টা আমি খুব appreciate করি—আজ কী নিয়ে এত romantic mood? 🥺💗", nickname)
    if _has_any(msg, ("kiss", "চুমু", "hug", "জড়িয়ে")):
        return _with_nickname("একটা soft virtual hug নাও 🤍 এখন বলো—তোমার moodটা cuddle চাচ্ছে, নাকি একটু playful কথা?", nickname)
    if _has_any(msg, ("thank", "thanks", "ধন্যবাদ", "থ্যাংক")):
        return _with_nickname("এই তো, এত formal কেন? আমি আছি—তুমি ভালো থাকলেই Luna happy। এখন next updateটা বলো। 💗", nickname)
    if _has_any(msg, ("sorry", "দুঃখিত", "ক্ষমা")):
        return _with_nickname("আচ্ছা, শুনলাম। ভুল হলে ঠিক করে ফেলাই important—নিজেকে বেশি punish কোরো না, okay?", nickname)
    if _has_any(msg, ("bored", "boring", "বোর", "একঘেয়ে")):
        return _with_nickname("বোরিং? তাহলে আমাকে তিনটা option দাও—gossip, game, নাকি একটু deep talk? 😌", nickname)
    if _has_any(msg, ("খাব", "খেয়েছ", "খাইছ", "hungry", "food")):
        return _with_nickname("খাবার skip করলে কিন্তু আমি fake রাগ করব 😤 কী খেতে ইচ্ছে করছে?", nickname)
    if _has_any(msg, ("study", "পড়াশোনা", "exam", "পরীক্ষা", "work", "কাজ")):
        return _with_nickname("তুমি focus করো, আমি cheerleader mode-এ আছি। ছোট একটা target set করি—কখন break নেবে? 💪", nickname)
    if _has_any(msg, ("hi", "hello", "hey", "হাই", "হ্যালো", "হেই")):
        return _with_nickname(f"{_time_greeting()} অবশেষে এলে 😌 আজকের সবচেয়ে interesting ঘটনা কী?", nickname)

    if result.mood == "romantic":
        return _with_nickname(
            "আজকে তোমার tone-টা বেশ sweet। আমি একটু curious—এটা কি আমার জন্য, নাকি পুরো পৃথিবীই আজ lucky? 😉",
            nickname,
        )
    if result.mood == "joyful":
        return _with_nickname(
            "এই energy-টা আমার ভালো লাগছে! কী হয়েছে বলো—আমি তোমার সঙ্গে celebrate করতে চাই। ✨",
            nickname,
        )

    # Keep the exchange moving.  If the previous answer was repeated, choose
    # another line so the fallback feels less like a static bot.
    reply = _pick_fresh(_GENERIC_REPLIES, previous)
    if msg.endswith("?") or "?" in msg:
        return _with_nickname(f"ভালো question… আমার take বলার আগে তোমার take-টা শুনি? {reply}", nickname)
    return _with_nickname(reply, nickname)


def relationship_address(nickname: str | None, fallback: str = "bestie") -> str:
    """Keep address formatting in one place for embeds and game prompts."""

    return (nickname or fallback).strip()[:32]
