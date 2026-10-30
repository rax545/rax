"""LUNA GF Discord bot.

The bot is interaction-first: members explicitly invoke chat, games and voice
features, while scheduled DMs remain opt-in.  Optional AI/TTS providers make
replies and voice more natural without preventing a local fallback from
running.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from ai_provider import AIChatProvider
from database import Database
from games import random_quiz, truth_or_dare
from hotness import (
    access_reply,
    boundary_reply,
    boundary_signal,
    couple_question,
    flirt_reply,
    hot_truth_or_dare,
    hotness_label,
    is_late_night,
    sanitise_provider_reply,
)
from mood import detect_mood, mood_label
from personality import random_line, relationship_address, reply_line, scheduled_line
from relationship import conversation_deltas, game_deltas, progress_bar, relationship_stage
from voice import VoiceService, VoiceUnavailable


load_dotenv()


def _int_env(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except ValueError:
        return default


TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = _int_env("GUILD_ID")
MAX_DAILY_DMS = max(0, _int_env("MAX_DAILY_DMS", 2))
RELATIONSHIP_DAILY_CAP = max(1, _int_env("RELATIONSHIP_DAILY_CAP", 40))
DB_PATH = os.getenv("DATABASE_PATH", "data/luna_gf.sqlite3")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("luna-gf")

intents = discord.Intents.default()
intents.members = True
# Message content is not needed: Luna responds to slash commands and voice
# controls only.  This keeps the data boundary small.
intents.message_content = False


class LunaBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database(DB_PATH)
        self.ai = AIChatProvider.from_env()
        self.voice = VoiceService.from_env()
        # Conversation text is held only in memory for the optional provider;
        # it disappears on restart and can be cleared with /gf_forget.
        self.chat_history: dict[tuple[int, int], list[dict[str, str]]] = {}
        self.quiz_sessions: dict[tuple[int, int], dict[str, Any]] = {}
        self._voice_tasks: set[asyncio.Task[Any]] = set()

    async def setup_hook(self) -> None:
        self.db.initialize()
        self.dm_scheduler.start()
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced commands to guild %s", GUILD_ID)
        else:
            await self.tree.sync()
            log.info("Synced global commands")

    async def close(self) -> None:
        if self.dm_scheduler.is_running():
            self.dm_scheduler.cancel()
        for task in self._voice_tasks:
            task.cancel()
        await super().close()

    def history_for(self, guild_id: int, user_id: int) -> list[dict[str, str]]:
        return list(self.chat_history.get((guild_id, user_id), []))

    def remember(self, guild_id: int, user_id: int, user_message: str, answer: str) -> None:
        key = (guild_id, user_id)
        history = self.chat_history.setdefault(key, [])
        history.extend(
            [
                {"role": "user", "content": user_message[:2000]},
                {"role": "assistant", "content": answer[:3500]},
            ]
        )
        del history[:-10]

    def forget(self, guild_id: int, user_id: int) -> None:
        self.chat_history.pop((guild_id, user_id), None)

    def schedule_voice_reply(self, guild: discord.Guild, user_id: int, text: str) -> None:
        member = guild.get_member(user_id)
        voice_client = guild.voice_client
        if not member or not member.voice or not voice_client or not voice_client.is_connected():
            return
        if member.voice.channel != voice_client.channel:
            return

        async def speak() -> None:
            try:
                await self.voice.speak(voice_client, text)
            except (VoiceUnavailable, discord.ClientException, discord.HTTPException) as exc:
                log.info("Voice reply skipped for %s: %s", user_id, exc)

        task = asyncio.create_task(speak())
        self._voice_tasks.add(task)
        task.add_done_callback(self._voice_tasks.discard)

    @tasks.loop(minutes=5)
    async def dm_scheduler(self) -> None:
        """Send occasional playful DMs only to explicit opt-ins."""

        if MAX_DAILY_DMS <= 0:
            return
        for guild in self.guilds:
            rows = self.db.get_opted_in(guild.id)
            for row in rows:
                user_id = int(row["user_id"])
                if self.db.dm_count_today(user_id) >= MAX_DAILY_DMS:
                    continue
                member = guild.get_member(user_id)
                if member is None or member.bot:
                    continue
                try:
                    nickname = self.db.get_nickname(user_id, guild.id)
                    await member.send(
                        scheduled_line(nickname),
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                    self.db.log_dm(user_id)
                    await asyncio.sleep(2)
                except (discord.Forbidden, discord.HTTPException):
                    log.info("Could not DM user %s; leaving opt-in unchanged", user_id)

    @dm_scheduler.before_loop
    async def before_dm_scheduler(self) -> None:
        await self.wait_until_ready()


bot = LunaBot()


def is_admin(interaction: discord.Interaction) -> bool:
    return bool(interaction.guild and interaction.user.guild_permissions.manage_guild)


def guild_id_for(interaction: discord.Interaction) -> int:
    # A zero scope is used for a DM chat profile; all relationship/game/voice
    # commands explicitly require a real guild.
    return int(interaction.guild_id or 0)


def require_guild(interaction: discord.Interaction) -> str | None:
    if not interaction.guild or not interaction.guild_id:
        return "এই feature-টি Discord server-এ ব্যবহার করো, DM-এ নয়। 💗"
    return None


def hot_state_for(interaction: discord.Interaction) -> dict[str, Any]:
    return bot.db.get_hotness(interaction.user.id, guild_id_for(interaction))


def hot_access_error(state: dict[str, Any]) -> str:
    return access_reply(
        age_confirmed=bool(state["age_confirmed"]),
        enabled=bool(state["enabled"]),
        boundary_mode=str(state["boundary_mode"]),
    )


async def generate_hot_reply(
    interaction: discord.Interaction,
    message: str,
    *,
    late_night: bool = False,
) -> str:
    """Generate a consent-gated mature-romance reply with a safe fallback."""

    scope_id = guild_id_for(interaction)
    state = hot_state_for(interaction)
    mood = detect_mood(message or "ভালো লাগছে")
    friendship_delta, affection_delta = conversation_deltas(mood)
    profile = bot.db.record_conversation(
        interaction.user.id,
        scope_id,
        mood=mood.mood,
        mood_confidence=mood.confidence,
        friendship_delta=friendship_delta,
        affection_delta=affection_delta,
        daily_cap=RELATIONSHIP_DAILY_CAP,
    )
    nickname = bot.db.get_nickname(interaction.user.id, scope_id)
    fallback = flirt_reply(
        message,
        nickname=nickname,
        level=int(state["level"]),
        jealous=bool(state["jealous_enabled"]),
        late_night=late_night,
        mood=mood,
    )
    answer = await bot.ai.reply(
        message=message or "Give me a tasteful, confident romantic compliment.",
        nickname=nickname,
        mood=mood.mood,
        response_style=mood.response_style,
        friendship=float(profile["friendship_score"]),
        affection=float(profile["affection_score"]),
        history=bot.history_for(scope_id, interaction.user.id),
        hot_mode=True,
        hotness_level=int(state["level"]),
        jealous_mode=bool(state["jealous_enabled"]),
        late_night=late_night,
    )
    answer = sanitise_provider_reply(answer or "", fallback)
    bot.remember(scope_id, interaction.user.id, message or "late-night mode", answer)
    return answer


@bot.event
async def on_ready() -> None:
    if bot.user:
        log.info("Logged in as %s (%s)", bot.user, bot.user.id)
    if not bot.ai.enabled:
        log.warning("AI_API_KEY is not configured; /gf_chat is using Luna's local conversation fallback")
    await bot.change_presence(activity=discord.Game(name="being your chaotic GF 💗"))


# ---------------------------------------------------------------------------
# Consent and chat
# ---------------------------------------------------------------------------
@bot.tree.command(name="gf_optin", description="Allow Luna to send you occasional funny DMs.")
async def gf_optin(interaction: discord.Interaction) -> None:
    if not interaction.guild:
        await interaction.response.send_message(
            "Use this command in the server where Luna is installed.", ephemeral=True
        )
        return
    bot.db.set_optin(interaction.user.id, interaction.guild.id, True)
    await interaction.response.send_message(
        "💗 You're opted in! Luna may send occasional playful DMs. Use `/gf_optout` anytime.",
        ephemeral=True,
    )


@bot.tree.command(name="gf_optout", description="Stop all scheduled DMs from Luna.")
async def gf_optout(interaction: discord.Interaction) -> None:
    if interaction.guild:
        bot.db.set_optin(interaction.user.id, interaction.guild.id, False)
    await interaction.response.send_message("Done — scheduled DMs are off. 💗", ephemeral=True)


@bot.tree.command(name="gf_chat", description="Chat with Luna's mood-aware AI companion.")
@app_commands.describe(message="Say something to Luna")
async def gf_chat(interaction: discord.Interaction, message: str) -> None:
    if not message.strip():
        await interaction.response.send_message("একটা কথা বলো, আমি শুনছি। 💗", ephemeral=True)
        return
    if len(message) > 500:
        await interaction.response.send_message(
            "Keep it under 500 characters, bestie 😭", ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)
    scope_id = guild_id_for(interaction)
    hot_state = hot_state_for(interaction)
    boundary_phrase = boundary_signal(message)
    if boundary_phrase and interaction.guild_id:
        # A clear discomfort signal immediately disables mature tone for this
        # member.  Re-enabling requires a deliberate hot-mode command.
        bot.db.set_hotness_boundary(interaction.user.id, interaction.guild_id, "soft")
        hot_state = hot_state_for(interaction)
    hot_active = bool(
        interaction.guild_id
        and hot_state["age_confirmed"]
        and hot_state["enabled"]
        and hot_state["boundary_mode"] == "normal"
    )
    mood = detect_mood(message)
    friendship_delta, affection_delta = conversation_deltas(mood)
    profile = bot.db.record_conversation(
        interaction.user.id,
        scope_id,
        mood=mood.mood,
        mood_confidence=mood.confidence,
        friendship_delta=friendship_delta,
        affection_delta=affection_delta,
        daily_cap=RELATIONSHIP_DAILY_CAP,
    )
    nickname = bot.db.get_nickname(interaction.user.id, scope_id)
    history = bot.history_for(scope_id, interaction.user.id)

    answer = None
    if not boundary_phrase:
        answer = await bot.ai.reply(
            message=message,
            nickname=nickname,
            mood=mood.mood,
            response_style=mood.response_style,
            friendship=float(profile["friendship_score"]),
            affection=float(profile["affection_score"]),
            history=history,
            hot_mode=hot_active,
            hotness_level=int(hot_state["level"]),
            jealous_mode=bool(hot_state["jealous_enabled"]),
            late_night=is_late_night(),
        )
    if not answer:
        if boundary_phrase:
            answer = boundary_reply()
        elif hot_active:
            answer = flirt_reply(
                message,
                nickname=nickname,
                level=int(hot_state["level"]),
                jealous=bool(hot_state["jealous_enabled"]),
                late_night=is_late_night(),
                mood=mood,
            )
        else:
            answer = reply_line(message, nickname=nickname, mood=mood, history=history)
    if hot_active:
        answer = sanitise_provider_reply(
            answer,
            flirt_reply(
                message,
                nickname=nickname,
                level=int(hot_state["level"]),
                jealous=bool(hot_state["jealous_enabled"]),
                late_night=is_late_night(),
                mood=mood,
            ),
        )
    bot.remember(scope_id, interaction.user.id, message, answer)

    # Mentions in provider/local text are always neutralised so a playful AI
    # cannot mass-ping a server by accident.
    await interaction.followup.send(
        answer,
        allowed_mentions=discord.AllowedMentions.none(),
    )

    if (
        interaction.guild
        and bot.db.voice_mode(interaction.user.id, interaction.guild.id)
        and interaction.guild.voice_client
    ):
        bot.schedule_voice_reply(interaction.guild, interaction.user.id, answer)


@bot.tree.command(name="gf_mood", description="See Luna's latest mood reading for your conversation.")
async def gf_mood(interaction: discord.Interaction) -> None:
    scope_id = guild_id_for(interaction)
    profile = bot.db.get_profile(interaction.user.id, scope_id)
    if not profile:
        await interaction.response.send_message(
            "এখনও কোনো mood signal নেই—`/gf_chat`-এ কিছু বলো। 🙂", ephemeral=True
        )
        return
    label = mood_label(profile["current_mood"], float(profile["mood_confidence"]))
    await interaction.response.send_message(
        f"Luna এখন তোমার কথার জন্য **{label}** style ব্যবহার করছে।\n"
        "এটা শুধু conversation style signal—কোনো diagnosis নয়।",
        ephemeral=True,
    )


@bot.tree.command(name="gf_forget", description="Clear Luna's in-memory chat context for you.")
async def gf_forget(interaction: discord.Interaction) -> None:
    bot.forget(guild_id_for(interaction), interaction.user.id)
    await interaction.response.send_message(
        "Done — Luna's temporary chat context for you is cleared. 💗", ephemeral=True
    )


# ---------------------------------------------------------------------------
# Consent-gated 18+ mature romance (non-graphic)
# ---------------------------------------------------------------------------
@bot.tree.command(name="gf_age_confirm", description="Confirm you are 18+ before using mature romance mode.")
@app_commands.describe(confirm="Confirm that you are 18 or older")
async def gf_age_confirm(interaction: discord.Interaction, confirm: bool) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    bot.db.set_age_confirmed(interaction.user.id, interaction.guild_id, confirm)
    if confirm:
        await interaction.response.send_message(
            "18+ self-confirmation saved. This is not identity/age verification, and hot mode is still OFF until you explicitly enable it with `/gf_hotmode mode:on`.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "Age confirmation removed and mature romance mode disabled. 💗", ephemeral=True
        )


@bot.tree.command(name="gf_hotness", description="View or set Luna's mature romance intensity.")
@app_commands.describe(level="Warm, bold or spicy non-graphic romance")
@app_commands.choices(
    level=[
        app_commands.Choice(name="Warm flirt", value="1"),
        app_commands.Choice(name="Bold flirt", value="2"),
        app_commands.Choice(name="Spicy romance", value="3"),
    ]
)
async def gf_hotness(
    interaction: discord.Interaction,
    level: app_commands.Choice[str] | None = None,
) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    if level:
        bot.db.set_hotness_level(interaction.user.id, interaction.guild_id, int(level.value))
    state = hot_state_for(interaction)
    status = "ON" if state["enabled"] else "OFF"
    jealous = "ON" if state["jealous_enabled"] else "OFF"
    await interaction.response.send_message(
        f"🔥 **Luna Hotness**\n"
        f"Level: **{hotness_label(state['level'])}**\n"
        f"Mode: **{status}** · Playful jealousy: **{jealous}**\n"
        f"18+ confirmed: **{'YES' if state['age_confirmed'] else 'NO'}**\n"
        f"Boundary state: **{state['boundary_mode']}**\n\n"
        "এটি non-graphic mature romance; consent এবং comfort সবসময় আগে।",
        ephemeral=True,
    )


@bot.tree.command(name="gf_hotmode", description="Turn consent-gated mature flirting on or off.")
@app_commands.describe(mode="Explicitly enable or disable mature romance")
@app_commands.choices(
    mode=[
        app_commands.Choice(name="On", value="on"),
        app_commands.Choice(name="Off", value="off"),
    ]
)
async def gf_hotmode(interaction: discord.Interaction, mode: app_commands.Choice[str]) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    if mode.value == "off":
        bot.db.set_hotness_enabled(interaction.user.id, interaction.guild_id, False)
        await interaction.response.send_message(
            "🔥 Hot mode OFF. Luna এখন normal/soft tone-এ থাকবে।", ephemeral=True
        )
        return

    state = hot_state_for(interaction)
    if not state["age_confirmed"]:
        await interaction.response.send_message(
            access_reply(
                age_confirmed=False,
                enabled=False,
                boundary_mode=str(state["boundary_mode"]),
            ),
            ephemeral=True,
        )
        return
    if state["boundary_mode"] in {"soft", "stop"}:
        await interaction.response.send_message(
            access_reply(
                age_confirmed=True,
                enabled=False,
                boundary_mode=str(state["boundary_mode"]),
            ),
            ephemeral=True,
        )
        return
    bot.db.set_hotness_enabled(interaction.user.id, interaction.guild_id, True)
    state = hot_state_for(interaction)
    await interaction.response.send_message(
        f"🔥 Hot mode ON — **{hotness_label(state['level'])}**. `/gf_flirt` বা `/gf_latenight` দিয়ে শুরু করো।",
        ephemeral=True,
    )


@bot.tree.command(name="gf_jealous", description="Toggle Luna's playful, non-controlling jealousy teasing.")
@app_commands.describe(mode="Turn playful jealousy on or off")
@app_commands.choices(
    mode=[
        app_commands.Choice(name="On", value="on"),
        app_commands.Choice(name="Off", value="off"),
    ]
)
async def gf_jealous(interaction: discord.Interaction, mode: app_commands.Choice[str]) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    if mode.value == "on":
        state = hot_state_for(interaction)
        blocked = hot_access_error(state)
        if blocked:
            await interaction.response.send_message(blocked, ephemeral=True)
            return
    bot.db.set_jealous_mode(interaction.user.id, interaction.guild_id, mode.value == "on")
    await interaction.response.send_message(
        f"Playful jealousy {'ON' if mode.value == 'on' else 'OFF'} — Luna কখনো control বা isolation করবে না। 😌",
        ephemeral=True,
    )


@bot.tree.command(name="gf_flirt", description="Start a consent-gated mature romantic flirt chat.")
@app_commands.describe(message="Optional flirty topic, up to 500 characters")
async def gf_flirt(interaction: discord.Interaction, message: str | None = None) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    state = hot_state_for(interaction)
    blocked = hot_access_error(state)
    if blocked:
        await interaction.response.send_message(blocked, ephemeral=True)
        return
    if message and len(message) > 500:
        await interaction.response.send_message("Message 500 characters-এর মধ্যে রাখো।", ephemeral=True)
        return
    prompt = message or "Give me a confident romantic compliment."
    if boundary_signal(prompt):
        assert interaction.guild_id is not None
        bot.db.set_hotness_boundary(interaction.user.id, interaction.guild_id, "soft")
        await interaction.response.send_message(boundary_reply(), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    answer = await generate_hot_reply(interaction, prompt)
    await interaction.followup.send(answer, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


@bot.tree.command(name="gf_latenight", description="Start a soft, intimate late-night romance conversation.")
@app_commands.describe(message="Optional late-night topic, up to 500 characters")
async def gf_latenight(interaction: discord.Interaction, message: str | None = None) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    state = hot_state_for(interaction)
    blocked = hot_access_error(state)
    if blocked:
        await interaction.response.send_message(blocked, ephemeral=True)
        return
    if message and len(message) > 500:
        await interaction.response.send_message("Message 500 characters-এর মধ্যে রাখো।", ephemeral=True)
        return
    prompt = message or "Start a gentle, intimate late-night conversation."
    if boundary_signal(prompt):
        assert interaction.guild_id is not None
        bot.db.set_hotness_boundary(interaction.user.id, interaction.guild_id, "soft")
        await interaction.response.send_message(boundary_reply(), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    answer = await generate_hot_reply(interaction, prompt, late_night=True)
    await interaction.followup.send(answer, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


@bot.tree.command(name="gf_hot_truth_or_dare", description="Play a safe, mature-romance Truth or Dare round.")
@app_commands.describe(mode="Choose truth, dare, or let Luna pick")
@app_commands.choices(
    mode=[
        app_commands.Choice(name="Random", value="random"),
        app_commands.Choice(name="Truth", value="truth"),
        app_commands.Choice(name="Dare", value="dare"),
    ]
)
async def gf_hot_truth_or_dare(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str] | None = None,
) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    state = hot_state_for(interaction)
    blocked = hot_access_error(state)
    if blocked:
        await interaction.response.send_message(blocked, ephemeral=True)
        return
    kind, prompt = hot_truth_or_dare(mode.value if mode else "random", int(state["level"]))
    friendship, affection = game_deltas()
    bot.db.record_game(
        interaction.user.id,
        interaction.guild_id,
        friendship_delta=friendship,
        affection_delta=affection,
        daily_cap=RELATIONSHIP_DAILY_CAP,
    )
    await interaction.response.send_message(
        f"**🔥 Mature {kind.title()}**\n{prompt}\n\n"
        "*Skip, change the prompt, or use `/gf_hot_stop` anytime. No photos, proof, secrets or unsafe actions.*",
        ephemeral=True,
        allowed_mentions=discord.AllowedMentions.none(),
    )


@bot.tree.command(name="gf_couple_question", description="Get a mature but non-graphic couple question.")
async def gf_couple_question(interaction: discord.Interaction) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    state = hot_state_for(interaction)
    blocked = hot_access_error(state)
    if blocked:
        await interaction.response.send_message(blocked, ephemeral=True)
        return
    friendship, affection = game_deltas()
    bot.db.record_game(
        interaction.user.id,
        interaction.guild_id,
        friendship_delta=friendship,
        affection_delta=affection,
        daily_cap=RELATIONSHIP_DAILY_CAP,
    )
    await interaction.response.send_message(
        f"**💗 Couple question**\n{couple_question(int(state['level']))}\n\n"
        "*Answer only what feels comfortable; skip is always okay.*",
        ephemeral=True,
        allowed_mentions=discord.AllowedMentions.none(),
    )


@bot.tree.command(name="gf_boundary", description="Set or reset Luna's mature-romance boundary state.")
@app_commands.describe(mode="Soft stops flirting; reset prepares for a deliberate re-enable")
@app_commands.choices(
    mode=[
        app_commands.Choice(name="Soft / stop", value="soft"),
        app_commands.Choice(name="Reset boundary", value="reset"),
    ]
)
async def gf_boundary(interaction: discord.Interaction, mode: app_commands.Choice[str]) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    if mode.value == "soft":
        bot.db.set_hotness_boundary(interaction.user.id, interaction.guild_id, "soft")
        await interaction.response.send_message(boundary_reply(), ephemeral=True)
        return
    state = hot_state_for(interaction)
    if not state["age_confirmed"]:
        await interaction.response.send_message(
            "Reset-এর আগে `/gf_age_confirm confirm:true` দরকার।", ephemeral=True
        )
        return
    bot.db.set_hotness_boundary(interaction.user.id, interaction.guild_id, "normal")
    await interaction.response.send_message(
        "Boundary reset হয়েছে, কিন্তু hot mode এখনও OFF। চাইলে `/gf_hotmode mode:on` দিয়ে deliberate opt-in করো।",
        ephemeral=True,
    )


@bot.tree.command(name="gf_hot_stop", description="Immediately stop all mature romance tone for you.")
async def gf_hot_stop(interaction: discord.Interaction) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    bot.db.set_hotness_boundary(interaction.user.id, interaction.guild_id, "stop")
    await interaction.response.send_message(
        "🛑 Hot mode immediately stopped. Luna এখন normal, respectful tone-এ থাকবে।",
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# Personalized identity and daily relationship level
# ---------------------------------------------------------------------------
@bot.tree.command(name="gf_nickname", description="Set or view your personal Luna nickname.")
@app_commands.describe(nickname="A nickname up to 32 characters; leave blank to view it")
async def gf_nickname(interaction: discord.Interaction, nickname: str | None = None) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    if nickname is None:
        current = bot.db.get_nickname(interaction.user.id, interaction.guild_id)
        await interaction.response.send_message(
            f"তোমার Luna nickname: **{current or 'not set'}**\n"
            "বদলাতে `/gf_nickname nickname:...` ব্যবহার করো।",
            ephemeral=True,
        )
        return

    clean = " ".join(nickname.split()).strip()
    if not clean or len(clean) > 32 or "@everyone" in clean.lower() or "@here" in clean.lower():
        await interaction.response.send_message(
            "Nickname 1–32 characters-এর হতে হবে এবং mention থাকতে পারবে না।", ephemeral=True
        )
        return
    bot.db.set_nickname(interaction.user.id, interaction.guild_id, clean)
    await interaction.response.send_message(
        f"ঠিক আছে, {clean}—এখন থেকে এই server-এ Luna তোমাকে এই nickname-এ ডাকবে। 💗",
        ephemeral=True,
    )


@bot.tree.command(name="gf_nickname_clear", description="Remove your personal Luna nickname.")
async def gf_nickname_clear(interaction: discord.Interaction) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    bot.db.set_nickname(interaction.user.id, interaction.guild_id, None)
    await interaction.response.send_message("Nickname cleared — default display name ফিরে এসেছে।", ephemeral=True)


async def send_relationship(interaction: discord.Interaction) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    profile = bot.db.get_relationship(interaction.user.id, interaction.guild_id)
    stage, explanation, score = relationship_stage(
        profile["friendship_score"], profile["affection_score"]
    )
    daily = profile["daily"]
    nickname = relationship_address(profile.get("nickname"), interaction.user.display_name)
    embed = discord.Embed(
        title=f"💗 {nickname}'s Daily Relationship Level",
        description=(
            f"**{stage}** · {score:.0f}/100\n{explanation}\n\n"
            "এটি কথোপকথন ও game participation-এর fictional progress meter—বাস্তব commitment নয়।"
        ),
        colour=discord.Colour.from_rgb(242, 125, 168),
    )
    embed.add_field(
        name="Friendship",
        value=f"{progress_bar(profile['friendship_score'])} {profile['friendship_score']:.1f}/100",
        inline=False,
    )
    embed.add_field(
        name="Affection",
        value=f"{progress_bar(profile['affection_score'])} {profile['affection_score']:.1f}/100",
        inline=False,
    )
    embed.add_field(
        name="Today",
        value=(
            f"{daily['conversation_count']} chats · {daily['game_count']} games\n"
            f"+{daily['friendship_points']:.1f} friendship · +{daily['affection_points']:.1f} affection"
        ),
        inline=False,
    )
    embed.set_footer(text=f"Active streak: {profile['streak_days']} day(s) · Scores are capped daily")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="gf_relationship", description="See your friendship and affection progress with Luna.")
async def gf_relationship(interaction: discord.Interaction) -> None:
    await send_relationship(interaction)


@bot.tree.command(name="gf_daily_relationship", description="See today's Luna relationship summary.")
async def gf_daily_relationship(interaction: discord.Interaction) -> None:
    await send_relationship(interaction)


@bot.tree.command(name="gf_delete_data", description="Delete your Luna profile and relationship data here.")
@app_commands.describe(confirm="Set true to permanently delete this server profile")
async def gf_delete_data(interaction: discord.Interaction, confirm: bool) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    if not confirm:
        await interaction.response.send_message(
            "No data was deleted. Run `/gf_delete_data confirm:true` if you really want to erase it.",
            ephemeral=True,
        )
        return
    assert interaction.guild_id is not None
    bot.db.delete_user_data(interaction.user.id, interaction.guild_id)
    bot.forget(interaction.guild_id, interaction.user.id)
    bot.quiz_sessions.pop((interaction.guild_id, interaction.user.id), None)
    await interaction.response.send_message(
        "তোমার Luna profile, relationship stats, nickname, voice preference এবং DM opt-in মুছে দেওয়া হয়েছে।",
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# Couple games
# ---------------------------------------------------------------------------
@bot.tree.command(name="gf_truth_or_dare", description="Play a safe Truth or Dare round with Luna.")
@app_commands.describe(mode="Choose truth, dare, or let Luna pick")
@app_commands.choices(
    mode=[
        app_commands.Choice(name="Random", value="random"),
        app_commands.Choice(name="Truth", value="truth"),
        app_commands.Choice(name="Dare", value="dare"),
    ]
)
async def gf_truth_or_dare(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str] | None = None,
) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    kind, prompt = truth_or_dare(mode.value if mode else "random")
    bot.db.record_game(
        interaction.user.id,
        interaction.guild_id,
        friendship_delta=game_deltas()[0],
        affection_delta=game_deltas()[1],
        daily_cap=RELATIONSHIP_DAILY_CAP,
    )
    title = "Truth" if kind == "truth" else "Dare"
    await interaction.response.send_message(
        f"**💞 {title}**\n{prompt}\n\n*Skip or change the prompt anytime—no pressure, no unsafe proof needed.*",
        allowed_mentions=discord.AllowedMentions.none(),
    )


class QuizView(discord.ui.View):
    def __init__(self, owner_id: int, guild_id: int, question: dict[str, Any]) -> None:
        super().__init__(timeout=90)
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.question = question
        self.message: discord.Message | None = None

        for index, choice in enumerate(question["choices"]):
            button = discord.ui.Button(
                label=f"{index + 1}. {choice}"[:80],
                style=discord.ButtonStyle.secondary,
                custom_id=f"luna-quiz-{owner_id}-{index}",
            )

            async def callback(
                button_interaction: discord.Interaction,
                selected: int = index,
            ) -> None:
                await self.answer(button_interaction, selected)

            button.callback = callback
            self.add_item(button)

    async def answer(self, interaction: discord.Interaction, selected: int) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "এই quiz round-টা অন্য member-এর—নিজের round শুরু করো। 🙂", ephemeral=True
            )
            return
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message("এই quiz round-এর server scope মেলেনি।", ephemeral=True)
            return

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        bot.quiz_sessions.pop((self.guild_id, self.owner_id), None)
        correct = selected == int(self.question["answer"])
        friendship, affection = game_deltas(correct)
        bot.db.record_game(
            self.owner_id,
            self.guild_id,
            friendship_delta=friendship,
            affection_delta=affection,
            daily_cap=RELATIONSHIP_DAILY_CAP,
        )
        if correct:
            result = f"✅ Correct! {self.question['explanation']}\n+{affection:.2f} affection game points 💗"
        else:
            result = (
                f"Not this time 🙂 The answer was **{int(self.question['answer']) + 1}. "
                f"{self.question['choices'][int(self.question['answer'])]}**.\n"
                f"{self.question['explanation']}"
            )
        await interaction.response.edit_message(
            content=result,
            embed=None,
            view=self,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.stop()

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="Quiz expired—চাইলে `/gf_quiz` দিয়ে নতুন round শুরু করো।", view=self)
            except discord.HTTPException:
                pass


@bot.tree.command(name="gf_quiz", description="Start a fun Luna quiz round.")
async def gf_quiz(interaction: discord.Interaction) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    question = random_quiz()
    bot.quiz_sessions[(interaction.guild_id, interaction.user.id)] = question
    embed = discord.Embed(
        title="🧠 Luna Couple Quiz",
        description=f"**{question['question']}**\n\nChoose one answer:",
        colour=discord.Colour.blurple(),
    )
    view = QuizView(interaction.user.id, interaction.guild_id, question)
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()


@bot.tree.command(name="gf_quiz_answer", description="Answer your active Luna quiz using option number 1–4.")
@app_commands.describe(answer="The number shown before your chosen answer")
async def gf_quiz_answer(interaction: discord.Interaction, answer: int) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    question = bot.quiz_sessions.get((interaction.guild_id, interaction.user.id))
    if not question:
        await interaction.response.send_message(
            "তোমার active quiz নেই—আগে `/gf_quiz` চালাও।", ephemeral=True
        )
        return
    if answer < 1 or answer > len(question["choices"]):
        await interaction.response.send_message("Option number ঠিক করে 1–4-এর মধ্যে দাও।", ephemeral=True)
        return
    bot.quiz_sessions.pop((interaction.guild_id, interaction.user.id), None)
    correct = answer - 1 == int(question["answer"])
    friendship, affection = game_deltas(correct)
    bot.db.record_game(
        interaction.user.id,
        interaction.guild_id,
        friendship_delta=friendship,
        affection_delta=affection,
        daily_cap=RELATIONSHIP_DAILY_CAP,
    )
    text = (
        f"✅ Correct! {question['explanation']}"
        if correct
        else f"Not quite 🙂 Correct answer: **{int(question['answer']) + 1}. {question['choices'][int(question['answer'])]}**\n{question['explanation']}"
    )
    await interaction.response.send_message(text, allowed_mentions=discord.AllowedMentions.none())


# ---------------------------------------------------------------------------
# Discord Voice GF
# ---------------------------------------------------------------------------
def member_voice_channel(interaction: discord.Interaction) -> discord.abc.GuildChannel | None:
    member = interaction.user if isinstance(interaction.user, discord.Member) else None
    return member.voice.channel if member and member.voice else None


async def connect_to_member_voice(interaction: discord.Interaction) -> discord.VoiceClient:
    if not interaction.guild:
        raise VoiceUnavailable("Voice commands need a server")
    channel = member_voice_channel(interaction)
    if channel is None:
        raise VoiceUnavailable("আগে একটি Discord voice channel-এ join করো")
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_connected():
        if voice_client.channel != channel:
            await voice_client.move_to(channel)
        return voice_client
    return await channel.connect(self_deaf=False)


@bot.tree.command(name="gf_voice_join", description="Join your current Discord voice channel as Luna.")
async def gf_voice_join(interaction: discord.Interaction) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        voice_client = await connect_to_member_voice(interaction)
        channel_name = getattr(voice_client.channel, "name", "your VC")
        await interaction.followup.send(
            f"🎙️ Luna joined **{channel_name}**. `/gf_voice_say` দিয়ে কথা বলাও, অথবা `/gf_voice_mode enabled:true` করো।",
            ephemeral=True,
        )
    except (VoiceUnavailable, discord.ClientException, discord.Forbidden, discord.HTTPException) as exc:
        await interaction.followup.send(f"Voice join হয়নি: {exc}", ephemeral=True)


@bot.tree.command(name="gf_voice_leave", description="Disconnect Luna from the current voice channel.")
async def gf_voice_leave(interaction: discord.Interaction) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild is not None
    voice_client = interaction.guild.voice_client
    if not voice_client:
        await interaction.response.send_message("Luna কোনো voice channel-এ নেই।", ephemeral=True)
        return
    voice_client.stop()
    await voice_client.disconnect(force=True)
    await interaction.response.send_message("👋 Luna voice channel থেকে বেরিয়ে গেল।", ephemeral=True)


@bot.tree.command(name="gf_voice_say", description="Make Luna say a short message in Discord VC.")
@app_commands.describe(text="What Luna should say, up to 500 characters")
async def gf_voice_say(interaction: discord.Interaction, text: str) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    if not text.strip() or len(text) > 500:
        await interaction.response.send_message("Text 1–500 characters-এর মধ্যে দাও।", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        voice_client = interaction.guild.voice_client if interaction.guild else None
        if not voice_client or not voice_client.is_connected():
            voice_client = await connect_to_member_voice(interaction)
        elif member_voice_channel(interaction) != voice_client.channel:
            await interaction.followup.send("তুমি Luna-র বর্তমান VC-তে নেই।", ephemeral=True)
            return
        await bot.voice.speak(voice_client, text)
        await interaction.followup.send("🔊 বলা হচ্ছে…", ephemeral=True)
    except (VoiceUnavailable, discord.ClientException, discord.Forbidden, discord.HTTPException) as exc:
        await interaction.followup.send(
            f"Luna কথা বলতে পারেনি: {exc}\nTTS setup-এর জন্য project spec দেখো।", ephemeral=True
        )


@bot.tree.command(name="gf_voice_mode", description="Toggle automatic spoken replies to your /gf_chat messages.")
@app_commands.describe(enabled="Whether Luna should speak your chat replies in the VC")
async def gf_voice_mode(interaction: discord.Interaction, enabled: bool) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild_id is not None
    if enabled and not interaction.guild.voice_client:
        await interaction.response.send_message(
            "আগে `/gf_voice_join` দিয়ে Luna-কে VC-তে আনো।", ephemeral=True
        )
        return
    bot.db.set_voice_mode(interaction.user.id, interaction.guild_id, enabled)
    await interaction.response.send_message(
        f"Automatic voice replies {'ON' if enabled else 'OFF'} for you. 🎙️", ephemeral=True
    )


@bot.tree.command(name="gf_voice_status", description="Show Luna's voice connection and TTS status.")
async def gf_voice_status(interaction: discord.Interaction) -> None:
    error = require_guild(interaction)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    assert interaction.guild is not None and interaction.guild_id is not None
    voice_client = interaction.guild.voice_client
    status = bot.voice.status
    connection = getattr(voice_client.channel, "name", "not connected") if voice_client else "not connected"
    provider = "external API + local fallback" if status["external_configured"] else (
        "local TTS" if status["local_configured"] else "not configured"
    )
    await interaction.response.send_message(
        f"**VC:** {connection}\n**TTS:** {provider}\n"
        f"**FFmpeg:** {'ready' if status['ffmpeg_configured'] else 'missing'}\n"
        f"**Your auto voice:** {'ON' if bot.db.voice_mode(interaction.user.id, interaction.guild_id) else 'OFF'}",
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# Existing playful/admin tools
# ---------------------------------------------------------------------------
@bot.tree.command(name="gf_roast", description="Ask Luna for a playful roast in this channel.")
@app_commands.describe(member="Optional member to roast (keep it friendly)")
async def gf_roast(interaction: discord.Interaction, member: discord.Member | None = None) -> None:
    target = member or interaction.user
    if target.bot:
        await interaction.response.send_message("Bots don't have feelings... probably. 🤖")
        return
    await interaction.response.send_message(
        f"{target.mention} {random_line()}",
        allowed_mentions=discord.AllowedMentions(users=True),
    )


@bot.tree.command(name="gf_setchannel", description="Set Luna's optional roast channel (admin only).")
@app_commands.describe(channel="The allowed roast channel")
async def gf_setchannel(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    if not is_admin(interaction):
        await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
        return
    assert interaction.guild_id is not None
    bot.db.set_channel(interaction.guild_id, channel.id)
    await interaction.response.send_message(
        f"💗 Roast channel set to {channel.mention}. Use `/gf_channel enabled:true` to enable.",
        ephemeral=True,
    )


@bot.tree.command(name="gf_channel", description="Turn scheduled channel roasts on or off (admin only).")
@app_commands.describe(enabled="Whether Luna should post in the configured channel")
async def gf_channel(interaction: discord.Interaction, enabled: bool) -> None:
    if not is_admin(interaction):
        await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
        return
    assert interaction.guild_id is not None
    if enabled and not bot.db.get_channel(interaction.guild_id):
        await interaction.response.send_message(
            "Set a channel first with `/gf_setchannel`.", ephemeral=True
        )
        return
    bot.db.set_channel_enabled(interaction.guild_id, enabled)
    await interaction.response.send_message(
        f"Channel roasts {'enabled' if enabled else 'disabled'} 💗", ephemeral=True
    )


@bot.tree.command(name="gf_post", description="Post one playful roast in the configured channel (admin only).")
async def gf_post(interaction: discord.Interaction) -> None:
    if not is_admin(interaction):
        await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
        return
    assert interaction.guild is not None and interaction.guild_id is not None
    channel_id = bot.db.get_channel(interaction.guild_id)
    channel = interaction.guild.get_channel(channel_id) if channel_id else None
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message(
            "Configure a valid channel first with `/gf_setchannel`.", ephemeral=True
        )
        return
    await channel.send(random_line(), allowed_mentions=discord.AllowedMentions.none())
    await interaction.response.send_message(f"Posted in {channel.mention} 💗", ephemeral=True)


@bot.tree.command(name="gf_status", description="Show your Luna profile and server settings.")
async def gf_status(interaction: discord.Interaction) -> None:
    scope_id = guild_id_for(interaction)
    profile = bot.db.get_profile(interaction.user.id, scope_id)
    opted = bot.db.is_opted_in(interaction.user.id, interaction.guild_id) if interaction.guild_id else False
    channel_id = bot.db.get_channel(interaction.guild_id) if interaction.guild_id else None
    enabled = bot.db.channel_enabled(interaction.guild_id) if interaction.guild_id else False
    hot_state = bot.db.get_hotness(interaction.user.id, scope_id)
    channel_text = f"<#{channel_id}>" if channel_id else "not configured"
    ai_mode = "Real AI provider" if bot.ai.enabled else "Local fallback — set AI_API_KEY for open-ended AI replies"
    if profile:
        stage, _, score = relationship_stage(profile["friendship_score"], profile["affection_score"])
        profile_text = (
            f"**Nickname:** {profile.get('nickname') or 'not set'}\n"
            f"**Relationship:** {stage} ({score:.0f}/100)\n"
            f"**Latest mood:** {mood_label(profile['current_mood'], profile['mood_confidence'])}"
        )
    else:
        profile_text = "No profile activity yet."
    await interaction.response.send_message(
        f"{profile_text}\n\n"
        f"**Your DM opt-in:** {'ON' if opted else 'OFF'}\n"
        f"**Server roast channel:** {channel_text}\n"
        f"**Scheduled channel roasts:** {'ON' if enabled else 'OFF'}\n"
        f"**Reply engine:** {ai_mode}\n"
        f"**Hot mode:** {'ON' if hot_state['enabled'] else 'OFF'}",
        ephemeral=True,
    )


async def main() -> None:
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN is missing. Copy .env.example to .env and add your bot token.")
    await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
