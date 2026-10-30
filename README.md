# LUNA GF — Discord Bot

A playful mixed-personality Discord companion with **opt-in scheduled DMs**, slash-command chat/roasts, and an admin-configured roast channel.

## Features
- `/gf_optin` and `/gf_optout`: members control whether scheduled DMs are allowed.
- `/gf_chat`: friendly mixed cute/savage replies.
- `/gf_roast`: on-demand playful roast.
- `/gf_setchannel`, `/gf_channel`, `/gf_post`: admin-only channel configuration and posting.
- `/gf_status`: view personal/server settings.
- SQLite persistence; no external database required.
- Daily DM cap to reduce unwanted messages.

## Requirements
- Python 3.10+
- A Discord application/bot from the Discord Developer Portal.

## Local setup (Windows / VS Code)
1. Install Python 3.10 or newer.
2. Extract the ZIP and open the folder in VS Code.
3. Open Terminal and run:
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env`.
5. Put your bot token in `DISCORD_TOKEN`.
6. Put your Discord server ID in `GUILD_ID` for immediate command sync (optional but recommended while testing).
7. In Discord Developer Portal → Bot, enable **Server Members Intent**. Message Content Intent is not required.
8. Invite the bot with `bot` and `applications.commands` scopes. Grant View Channels, Send Messages, Embed Links (optional), and Read Message History (optional) permissions. Do not grant Administrator unless you truly need it.
9. Run:
   ```powershell
   python bot.py
   ```

## First use
- Member runs `/gf_optin` to consent to scheduled DMs.
- Member runs `/gf_optout` at any time to stop them.
- Admin runs `/gf_setchannel` and chooses a text channel.
- Admin runs `/gf_channel enabled:true` to enable channel posting.
- Admin can run `/gf_post` to test one message.
- `/gf_chat` and `/gf_roast` are on-demand commands.

## Render deployment
1. Push this folder to a GitHub repository.
2. In Render, create a **Background Worker** from the repo (Docker runtime).
3. Add environment variables `DISCORD_TOKEN`, `GUILD_ID`, and `MAX_DAILY_DMS=2`.
4. Deploy. Keep a persistent disk mounted at `/app/data` if your Render plan supports it; without persistent storage, SQLite settings can reset on redeploy/restart.

## Important behavior
- The bot never sends scheduled DMs to members who have not explicitly opted in.
- The bot does not scrape or message every server member.
- Scheduled DMs are capped at two per user per UTC day by default.
- Keep roasts playful; do not target protected traits, threats, sexual content, or personal vulnerabilities.
- Discord may block DMs based on recipient privacy settings.
- This starter uses curated local responses, not a paid AI API. You can add an AI provider later if you want more natural conversation.

## Troubleshooting
- `DISCORD_TOKEN is missing`: create `.env` from `.env.example` and set the token.
- Slash commands not showing: set `GUILD_ID`, restart, and ensure `applications.commands` scope was included.
- Bot cannot post: check channel permissions and that the selected channel is visible to the bot.
- DMs fail: the user may have server DMs disabled; they can still use public slash commands.
