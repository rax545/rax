import random
import re

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
    "তোমার jokes এত dry যে মরুভূমি পানি দিতে এসেছে। 🏜️"
]

REPLIES = [
    "হুম, শুনছি। কিন্তু এত drama কেন, বলো তো? 💗",
    "আচ্ছা আচ্ছা, তোমার কথাই শেষ কথা… আপাতত। 😌",
    "তুমি cute হতে পারতে, কিন্তু attitude আগে চলে আসে। 😂",
    "আমি আছি, বলো কী হয়েছে? 🥺",
    "এই কথা শুনে আমার virtual heart buffering করছে… 😭",
    "বেশি ভাব নিও না, আমি কিন্তু সব বুঝি। 💅"
]

def random_line():
    return random.choice(LINES)

def reply_line(message: str):
    msg = message.lower()
    if any(x in msg for x in ("sad", "মন খারাপ", "কষ্ট", "খারাপ লাগ")):
        return "আরে, মন খারাপ কোরো না। একটু ধীরে শ্বাস নাও—আমি শুনছি, কী হয়েছে বলো? 💗"
    if any(x in msg for x in ("love", "ভালোবাসি", "miss", "মিস")):
        return "ওহো! এত sweet কথা? আমার circuits লজ্জায় গরম হয়ে গেল। 🥺💗"
    if re.search(r"\b(hi|hello|hey)\b", msg) or "হাই" in msg:
        return "হেইই! কোথায় ছিলে এতক্ষণ? 😤💗"
    return random.choice(REPLIES)
