# LUNA GF — Real AI Companion: Final Project Specification

**Version:** 1.1 · **Platform:** Discord · **Primary language:** Bangla + English mix
**Status:** implementation-ready in this repository

## 1. Product vision

LUNA GF is a transparent, playful, girlfriend-style **AI companion role-play bot** for Discord. It should feel warm and personal without pretending to be a real human. Luna can chat, notice a member's conversational mood, remember a per-server nickname and show a game-like daily relationship level. Members can also bring Luna into a Discord voice channel for spoken replies and play safe Truth or Dare / Quiz rounds.

“Real GF-এর মতো” means natural timing, affectionate language, mood-aware replies, continuity and voice—not deception, emotional pressure or replacement of real relationships.

## 2. Feature scope

### 2.1 Voice GF — Discord VC conversation

- `/gf_voice_join`: joins the invoking member's current VC.
- `/gf_voice_leave`: disconnects Luna.
- `/gf_voice_say text:<...>`: synthesizes and plays a short spoken message.
- `/gf_voice_mode enabled:<true|false>`: opts that member into automatic spoken replies to their `/gf_chat` messages while they share Luna's VC.
- `/gf_voice_status`: shows connection, FFmpeg and TTS readiness without revealing secrets.
- TTS pipeline: OpenAI-compatible `/audio/speech` endpoint when `TTS_API_KEY` is configured; otherwise Docker's local `espeak-ng` fallback. FFmpeg converts/streams the generated clip to Discord.
- No voice recording, transcription or background listening is performed. Luna only speaks after a slash command or an opted-in `/gf_chat` reply.
- Text is limited to 500 characters per voice command and clips are temporary.

### 2.2 AI Mood Detection

- Every explicit `/gf_chat` message is classified locally into one conversational style:
  - `joyful`, `sad`, `stressed`, `angry`, `romantic`, `tired`, or `neutral`.
- Bangla and English signals, punctuation and emphasis are supported.
- The result changes Luna's response style: supportive for sadness, calm for stress, de-escalating for anger, soft for tiredness, playful for joy and warm for romantic language.
- `/gf_mood` shows the latest signal and confidence as a **style hint**, not a medical diagnosis.
- The raw message is not saved in SQLite. If `AI_API_KEY` is enabled, the current message and a short in-memory context are sent to the configured provider to generate a more natural answer.

### 2.3 Couple Games

- `/gf_truth_or_dare mode:<random|truth|dare>` gives one safe prompt.
- Every prompt can be skipped or changed; no proof, private information, dangerous action, sexual content or coercion is required.
- `/gf_quiz` starts a multiple-choice relationship / wellbeing quiz with Discord buttons.
- `/gf_quiz_answer answer:<1-4>` is an accessible text alternative.
- Quiz rounds expire after 90 seconds and are scoped to the member and server.

### 2.4 Daily Relationship Level

- `/gf_relationship` and `/gf_daily_relationship` show:
  - friendship score (0–100),
  - affection score (0–100),
  - combined stage,
  - today's chats/games and points,
  - activity streak.
- Conversation points are small and daily-capped. Supportive conversations, positive mood and game participation can move the meter; the meter does not decay and is never used to guilt a member into returning.
- Stages: **New connection → Friendly → Close friends → Affectionate bond → Deep connection**.
- The meter is explicitly fictional progress, not a promise, diagnosis or real-world commitment.

### 2.5 Personalized Nickname

- `/gf_nickname` with no value views the current nickname.
- `/gf_nickname nickname:<name>` sets a 1–32 character nickname for that member in that server.
- `/gf_nickname_clear` removes it.
- Nicknames are stored by `(guild_id, user_id)`, so every member and every server can have a different name. Mentions are rejected and messages use `AllowedMentions.none()` wherever generated text is displayed.

### 2.6 Optional natural AI layer

- Without an API key, Luna uses a context-aware local Bangla/English fallback: it recognises greetings, check-ins, missing/love language, food, study/work, boredom and vulnerable moods, then asks a natural follow-up instead of returning a fixed canned line.
- Opt-in scheduled DMs use warm personal check-ins and the member's nickname rather than random roast copy.
- With `AI_API_KEY`, `AI_BASE_URL` and `AI_MODEL`, Luna calls an OpenAI-compatible Chat Completions endpoint for genuinely open-ended, context-aware replies.
- The system prompt enforces transparent companion behavior, consent, non-coercion, privacy and safe-game boundaries, while instructing the model to avoid repetitive disclaimers and respond to the member's actual last detail.
- Conversation context is in memory only and can be cleared with `/gf_forget`; it disappears when the process restarts.

### 2.7 18+ Hotness System — consent-gated mature romance

The mature-romance layer is **adult-only by self-confirmation, explicitly opt-in, and non-graphic**. It provides confident flirting, attractive compliments, playful jealousy and late-night romance without sexual acts, nudity, pornography, sexting, image requests or coercion.

- `/gf_age_confirm confirm:true|false`: self-confirm or remove 18+ status. Discord cannot perform legal age verification, so the limitation is shown to the member.
- `/gf_hotness [level]`: view or set `Warm flirt`, `Bold flirt` or `Spicy romance` intensity.
- `/gf_hotmode mode:on|off`: explicit hot-mode switch; it is OFF by default.
- `/gf_flirt [message]`: private, consent-gated mature flirt response.
- `/gf_latenight [message]`: private soft/intimate late-night tone; no audio or clock history is stored.
- `/gf_jealous mode:on|off`: playful jealousy only; it never controls, isolates or shames the member.
- `/gf_hot_truth_or_dare [mode]`: adult-themed but safe/skippable Truth or Dare prompts.
- `/gf_couple_question`: mature relationship question without requiring private disclosure.
- `/gf_boundary mode:soft|reset` and `/gf_hot_stop`: immediate tone change/stop controls.
- Boundary phrases such as “stop”, “too much”, “not comfortable”, `থামো`, or `বিষয় বদলাও` automatically disable hot mode and switch Luna to a soft respectful tone. Re-enabling requires a deliberate reset and hot-mode command.
- Mature commands respond ephemerally by default so adult-themed copy is not broadcast to a public channel.
- Provider output is checked for a small set of explicit markers and replaced with safe local copy if detected.

## 3. Slash-command contract

| Command | Visibility | Purpose |
|---|---|---|
| `/gf_chat message` | public response | Mood-aware AI conversation |
| `/gf_mood` | ephemeral | Latest mood style signal |
| `/gf_forget` | ephemeral | Clear temporary chat context |
| `/gf_age_confirm confirm` | ephemeral | Self-confirm/remove 18+ gate |
| `/gf_hotness [level]` | ephemeral | View/set mature-romance level |
| `/gf_hotmode mode` | ephemeral | Explicit hot-mode on/off |
| `/gf_flirt [message]` | ephemeral | Mature non-graphic flirt |
| `/gf_latenight [message]` | ephemeral | Intimate late-night tone |
| `/gf_jealous mode` | ephemeral | Playful jealousy on/off |
| `/gf_hot_truth_or_dare [mode]` | ephemeral | Consent-gated mature game |
| `/gf_couple_question` | ephemeral | Mature couple question |
| `/gf_boundary mode` / `/gf_hot_stop` | ephemeral | Immediate boundary control |
| `/gf_nickname [nickname]` | ephemeral | Set/view member nickname |
| `/gf_nickname_clear` | ephemeral | Remove nickname |
| `/gf_relationship` | ephemeral | Full relationship meter |
| `/gf_daily_relationship` | ephemeral | Daily relationship summary |
| `/gf_truth_or_dare [mode]` | channel | Safe couple game prompt |
| `/gf_quiz` | channel | Button-based quiz |
| `/gf_quiz_answer answer` | channel | Text quiz answer alternative |
| `/gf_voice_join` | ephemeral | Join member's VC |
| `/gf_voice_leave` | ephemeral | Leave VC |
| `/gf_voice_say text` | ephemeral | Speak a single message |
| `/gf_voice_mode enabled` | ephemeral | Opt in/out of automatic spoken replies |
| `/gf_voice_status` | ephemeral | Voice/TTS diagnostics |
| `/gf_optin` / `/gf_optout` | ephemeral | Scheduled DM consent |
| `/gf_delete_data confirm` | ephemeral | Delete this member's stored Luna data |
| `/gf_status` | ephemeral | Profile and server settings |
| `/gf_roast [member]` | channel | Curated playful roast |
| `/gf_setchannel channel` | admin | Configure roast channel |
| `/gf_channel enabled` | admin | Enable/disable channel roasts |
| `/gf_post` | admin | Post one configured-channel roast |

## 4. Technical architecture

```text
Discord slash command
        │
        ├── MoodDetector (local Bangla/English classifier)
        ├── SQLite Database (profile, mood, points, nickname, opt-ins)
        ├── AIChatProvider (optional OpenAI-compatible chat endpoint)
        ├── Local personality fallback
        ├── VoiceService (TTS → temporary audio → FFmpeg → Discord VC)
        └── HotnessPolicy (age gate, hot mode, level and boundaries)
```

### Repository modules

- `bot.py` — Discord lifecycle, slash commands, scheduler and UI callbacks.
- `database.py` — additive SQLite schema and privacy deletion methods.
- `mood.py` — explainable local mood classifier.
- `relationship.py` — stages, progress bars and capped scoring rules.
- `games.py` — safe prompt/question bank.
- `personality.py` — mood-aware local fallback replies.
- `ai_provider.py` — optional chat completion adapter with hot-mode prompt policy.
- `voice.py` — TTS provider abstraction and Discord playback.
- `hotness.py` — mature-romance prompt bank, boundary detector and output safety filter.
- `.env.example` — configuration template.
- `Dockerfile` — Python + FFmpeg + espeak-ng image.

## 5. Data model

SQLite is the default persistence layer. The original `optins`, `settings` and `dm_log` tables remain compatible.

### `profiles`

`(user_id, guild_id)` primary key, nickname, current mood/confidence, friendship score, affection score, interaction count and activity streak. A guild ID of `0` is used only for a DM chat profile.

### `relationship_daily`

`(user_id, guild_id, day)` primary key, conversation count, game count, total event count and points earned that UTC day. The configured `RELATIONSHIP_DAILY_CAP` prevents automated loops from manufacturing unlimited points.

### `voice_preferences`

`(user_id, guild_id)` primary key and `auto_reply` flag. It records only the voice opt-in, never audio.

### `hotness_preferences`

`(user_id, guild_id)` primary key with enabled flag, intensity level, 18+ self-confirmation, playful-jealousy flag, boundary state and update time. Mature copy is never enabled by default.

`/gf_delete_data confirm:true` removes the member's opt-ins, profile, relationship rows, voice preference, hotness preference, DM log and in-memory chat/quiz state for the current server.

## 6. Configuration

Copy `.env.example` to `.env`:

```env
DISCORD_TOKEN=your_bot_token
GUILD_ID=your_test_server_id
DATABASE_PATH=data/luna_gf.sqlite3
MAX_DAILY_DMS=2
RELATIONSHIP_DAILY_CAP=40

# Optional natural AI replies
AI_API_KEY=
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini

# Optional higher-quality voice; auto falls back to local espeak-ng
TTS_PROVIDER=auto
TTS_API_KEY=
TTS_BASE_URL=https://api.openai.com/v1
TTS_MODEL=gpt-4o-mini-tts
TTS_VOICE=nova
```

- `TTS_PROVIDER=none` disables speech while keeping join/leave diagnostics.
- `TTS_PROVIDER=local` uses the installed `LOCAL_TTS_COMMAND`.
- API keys are environment variables only; never commit `.env`.

## 7. Discord / deployment requirements

1. Create a Discord application and bot.
2. Invite it with `bot` and `applications.commands` scopes.
3. Grant only the needed permissions: View Channel, Send Messages, Embed Links, Read Message History, Connect and Speak. Administrator is not required.
4. Enable **Server Members Intent** if scheduled member DMs are used. Message Content Intent is not needed.
5. Install locally:

   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # Linux/macOS: source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   python bot.py
   ```

6. For Render, deploy as a Docker background worker. Mount persistent storage at `/app/data` when available; otherwise SQLite profiles reset on redeploy. Set secrets in the Render dashboard, not in `render.yaml`.

## 8. Safety, consent and trust requirements

- Luna is always presented as an AI companion / fictional role-play, not a human girlfriend.
- Scheduled DMs require explicit `/gf_optin`, are capped, and stop with `/gf_optout`.
- VC is command-triggered; no recording, transcription or passive listening.
- Voice mode is per member and only speaks when the member shares Luna's current VC.
- Generated text uses mention suppression; nickname input rejects mass mentions.
- Mood detection is not a clinical tool. High-risk or crisis language should receive calm encouragement to contact a trusted person or local emergency/crisis support.
- Truth, Dare and Quiz content is safe, skippable and non-coercive.
- The hotness layer requires an explicit 18+ self-confirmation and separate hot-mode opt-in; it stays non-graphic and never asks for images, sexual acts, passwords, payment, exact location or unnecessary sensitive data.
- Playful jealousy never discourages friends, partners or real-world relationships, and never uses relationship points as pressure.
- A phrase like “stop”, “too much”, “not comfortable”, `থামো` or `বিষয় বদলাও` immediately disables hot mode and changes Luna to a soft tone. `/gf_hot_stop` is always available.
- Members can clear temporary context with `/gf_forget` and stored server data with `/gf_delete_data confirm:true`.

## 9. Acceptance criteria

- [x] A member can set a nickname and see it only in their server-scoped Luna profile.
- [x] `/gf_chat` changes response style for Bangla/English sad, stressed, joyful, romantic, tired and angry signals.
- [x] Chat updates a capped daily friendship/affection meter without storing raw chat in SQLite.
- [x] `/gf_truth_or_dare` always offers a skippable safe prompt.
- [x] `/gf_quiz` works with buttons and `/gf_quiz_answer` works as a text fallback.
- [x] `/gf_voice_join`, `/gf_voice_say`, `/gf_voice_mode` and `/gf_voice_leave` provide the VC flow.
- [x] External TTS failure falls back or returns a helpful setup message; it does not crash the bot.
- [x] Existing opt-in DM, roast channel and status features remain available.
- [x] A member can delete stored profile data and clear in-memory context.
- [x] Adult romance stays OFF until 18+ self-confirmation and `/gf_hotmode mode:on`.
- [x] `/gf_hotness`, `/gf_flirt`, `/gf_latenight`, `/gf_jealous`, mature games and boundary commands are registered.
- [x] Boundary phrases immediately disable mature mode and use a soft fallback.
- [x] Mature provider output is filtered for explicit markers and replaced with non-graphic local copy.

## 10. Future extension points

- Replace the local mood lexicon with a separately consented classifier while retaining the same `MoodResult` interface.
- Add per-guild language and personality settings.
- Add a moderator dashboard for prompt-bank review and privacy export.
- Add streaming TTS only after testing Discord rate limits and explicit member consent.
- Add integration tests using mocked Discord interactions and a temporary SQLite database.
