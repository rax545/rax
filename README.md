# LUNA GF — Real AI Discord Companion

LUNA GF হলো Bangla + English mixed একটি **transparent AI companion role-play bot**—real human girlfriend সেজে নয়, কিন্তু warm, personal এবং mood-aware conversational experience দেওয়ার জন্য। এই version-এ Voice GF, AI Mood Detection, Couple Games, Daily Relationship Level এবং member-wise Personalized Nickname যোগ করা হয়েছে।

> “Real GF-এর মতো” এখানে natural conversation, affectionate tone, continuity এবং voice বোঝায়; deception, pressure বা real relationship-এর বদলি নয়।

## নতুন feature সংক্ষেপ

- **Voice GF:** `/gf_voice_join`, `/gf_voice_say`, `/gf_voice_mode`, `/gf_voice_leave` — Discord VC-তে কথা বলা। OpenAI-compatible TTS অথবা Docker-এর local `espeak-ng` fallback। Recording/transcription নেই।
- **AI Mood Detection:** `/gf_chat`-এর Bangla/English কথার tone দেখে joyful, sad, stressed, angry, romantic, tired বা neutral style বেছে নেয়। `/gf_mood`-এ দেখা যায়; diagnosis নয়।
- **Couple Games:** safe/skippable `/gf_truth_or_dare` এবং button-based `/gf_quiz` (`/gf_quiz_answer` text fallback)।
- **Daily Relationship Level:** `/gf_relationship` — friendship, affection, daily activity, stage ও streak; points capped এবং fictional progress meter।
- **Personalized Nickname:** `/gf_nickname`, `/gf_nickname_clear` — প্রত্যেক member-এর জন্য server-scoped আলাদা nickname।
- **Optional real AI replies:** `AI_API_KEY` দিলে OpenAI-compatible Chat Completions ব্যবহার করে truly open-ended, context-aware reply; key না থাকলেও improved local fallback common GF conversations বুঝে reply করে। `/gf_status`-এ active reply engine দেখা যাবে।
- **18+ Hotness System:** `/gf_age_confirm`, `/gf_hotness`, `/gf_hotmode`, `/gf_flirt`, `/gf_latenight`, `/gf_jealous`, `/gf_hot_truth_or_dare`, `/gf_couple_question` — explicit opt-in mature flirting, spicy-but-non-graphic compliments, playful jealousy এবং late-night romance। `/gf_boundary` ও `/gf_hot_stop` সঙ্গে সঙ্গে tone soft করে।
- Existing opt-in scheduled DMs, roasts, admin channel settings এবং SQLite persistence রাখা হয়েছে।

পূর্ণ final specification: **[PROJECT_SPEC.md](PROJECT_SPEC.md)**

## Setup

Requirements: Python 3.10+, Discord application/bot, and for voice either Docker or FFmpeg + espeak-ng. `PyNaCl` and `davey` are included for Discord voice encryption/transport.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

`.env`-এ কমপক্ষে সেট করো:

```env
DISCORD_TOKEN=your_discord_bot_token
GUILD_ID=your_test_server_id
```

`GUILD_ID` development-এ slash command instant sync করে; production-এ blank রাখলে global sync হবে। Optional real AI + high-quality voice:

```env
AI_API_KEY=
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
TTS_PROVIDER=auto
TTS_API_KEY=
TTS_BASE_URL=https://api.openai.com/v1
TTS_MODEL=gpt-4o-mini-tts
TTS_VOICE=nova
```

## Discord permissions

`bot` এবং `applications.commands` scopes ব্যবহার করো। View Channel, Send Messages, Embed Links, Read Message History, **Connect** এবং **Speak** যথেষ্ট; Administrator দরকার নেই। Scheduled member DMs চাইলে **Server Members Intent** enable করো। Message Content Intent দরকার নেই।

## Privacy / trust

- Scheduled DM কেবল `/gf_optin` করার পর; `/gf_optout` যেকোনো সময়।
- Voice command-triggered; bot audio record বা transcribe করে না।
- Raw chat SQLite-এ save হয় না; optional AI provider চালু থাকলে current message ও short in-memory context provider-এ যায়। `/gf_forget` context clear করে।
- `/gf_delete_data confirm:true` current server-এর profile, nickname, relationship, voice preference, hotness preference, opt-in ও DM log মুছে দেয়।
- 18+ mode self-confirmation + explicit hot-mode opt-in ছাড়া চালু হয় না। Content mature-romantic কিন্তু non-graphic; image request, sexual act, sexting বা coercion নেই।
- “stop”, “too much”, “not comfortable”, `থামো` বা `বিষয় বদলাও` বললে hot mode সঙ্গে সঙ্গে বন্ধ হয়ে soft tone হয়।
- Mood detector emotional diagnosis নয়। Game prompts safe এবং skip করা যায়।

## Render deployment

`render.yaml`/`Dockerfile` দিয়ে Background Worker হিসেবে deploy করা যায়। `DISCORD_TOKEN`, `AI_API_KEY`, `TTS_API_KEY` dashboard secret হিসেবে দাও। SQLite reset ঠেকাতে `/app/data`-তে persistent disk ব্যবহার করো।

## Existing/admin commands

`/gf_status`, `/gf_roast`, `/gf_setchannel`, `/gf_channel`, `/gf_post` আগের মতো আছে। Admin permission কেবল channel configuration/posting-এর জন্য ব্যবহৃত হয়।
