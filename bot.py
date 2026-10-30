import os
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from database import Database
from personality import random_line, reply_line

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0") or 0)
DEFAULT_INTERVAL = int(os.getenv("DM_INTERVAL_MINUTES", "180"))
MAX_DAILY_DMS = int(os.getenv("MAX_DAILY_DMS", "2"))
DB_PATH = os.getenv("DATABASE_PATH", "data/luna_gf.sqlite3")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("luna-gf")

intents = discord.Intents.default()
intents.members = True
intents.message_content = False

class LunaBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database(DB_PATH)

    async def setup_hook(self):
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

    async def close(self):
        self.dm_scheduler.cancel()
        await super().close()

    @tasks.loop(minutes=5)
    async def dm_scheduler(self):
        # DM only members who explicitly opted in; enforce per-user daily cap.
        for guild in self.guilds:
            rows = self.db.get_opted_in(guild.id)
            for row in rows:
                user_id = row["user_id"]
                if self.db.dm_count_today(user_id) >= MAX_DAILY_DMS:
                    continue
                member = guild.get_member(user_id)
                if member is None or member.bot:
                    continue
                try:
                    await member.send(random_line())
                    self.db.log_dm(user_id)
                    await discord.utils.sleep_until(discord.utils.utcnow() + discord.timedelta(seconds=2))
                except (discord.Forbidden, discord.HTTPException):
                    log.info("Could not DM user %s; leaving opt-in unchanged", user_id)

    @dm_scheduler.before_loop
    async def before_dm_scheduler(self):
        await self.wait_until_ready()

bot = LunaBot()

def is_admin(interaction: discord.Interaction) -> bool:
    return bool(interaction.guild and interaction.user.guild_permissions.manage_guild)

@bot.event
async def on_ready():
    log.info("Logged in as %s (%s)", bot.user, bot.user.id)
    await bot.change_presence(activity=discord.Game(name="being your chaotic GF 💗"))

@bot.tree.command(name="gf_optin", description="Allow Luna to send you occasional funny DMs.")
async def gf_optin(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Use this command in the server where Luna is installed.", ephemeral=True)
    bot.db.set_optin(interaction.user.id, interaction.guild.id, True)
    await interaction.response.send_message("💗 You're opted in! Luna may send you occasional playful DMs. Use `/gf_optout` anytime.", ephemeral=True)

@bot.tree.command(name="gf_optout", description="Stop all scheduled DMs from Luna.")
async def gf_optout(interaction: discord.Interaction):
    if interaction.guild:
        bot.db.set_optin(interaction.user.id, interaction.guild.id, False)
    await interaction.response.send_message("Done — scheduled DMs are off. 💗", ephemeral=True)

@bot.tree.command(name="gf_chat", description="Chat with Luna's mixed cute/savage personality.")
@app_commands.describe(message="Say something to Luna")
async def gf_chat(interaction: discord.Interaction, message: str):
    if len(message) > 500:
        return await interaction.response.send_message("Keep it under 500 characters, bestie 😭", ephemeral=True)
    await interaction.response.send_message(reply_line(message), ephemeral=False)

@bot.tree.command(name="gf_roast", description="Ask Luna for a playful roast in this channel.")
@app_commands.describe(member="Optional member to roast (keep it friendly)")
async def gf_roast(interaction: discord.Interaction, member: discord.Member | None = None):
    target = member or interaction.user
    if target.bot:
        return await interaction.response.send_message("Bots don't have feelings... probably. 🤖", ephemeral=True)
    await interaction.response.send_message(f"{target.mention} {random_line()}", allowed_mentions=discord.AllowedMentions(users=True))

@bot.tree.command(name="gf_setchannel", description="Set the channel where Luna may post occasional roasts (admin only).")
@app_commands.describe(channel="The allowed roast channel")
async def gf_setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction):
        return await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
    bot.db.set_channel(interaction.guild_id, channel.id)
    await interaction.response.send_message(f"💗 Roast channel set to {channel.mention}. Use `/gf_channel on` to enable.", ephemeral=True)

@bot.tree.command(name="gf_channel", description="Turn scheduled channel roasts on or off (admin only).")
@app_commands.describe(enabled="Whether Luna should post in the configured channel")
async def gf_channel(interaction: discord.Interaction, enabled: bool):
    if not is_admin(interaction):
        return await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
    if enabled and not bot.db.get_channel(interaction.guild_id):
        return await interaction.response.send_message("Set a channel first with `/gf_setchannel`.", ephemeral=True)
    bot.db.set_channel_enabled(interaction.guild_id, enabled)
    await interaction.response.send_message(f"Channel roasts {'enabled' if enabled else 'disabled'} 💗", ephemeral=True)

@bot.tree.command(name="gf_post", description="Post one playful roast in the configured channel (admin only).")
async def gf_post(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
    channel_id = bot.db.get_channel(interaction.guild_id)
    channel = interaction.guild.get_channel(channel_id) if channel_id else None
    if not isinstance(channel, discord.TextChannel):
        return await interaction.response.send_message("Configure a valid channel first with `/gf_setchannel`.", ephemeral=True)
    await channel.send(random_line(), allowed_mentions=discord.AllowedMentions.none())
    await interaction.response.send_message(f"Posted in {channel.mention} 💗", ephemeral=True)

@bot.tree.command(name="gf_status", description="Show your Luna DM settings and server channel status.")
async def gf_status(interaction: discord.Interaction):
    opted = bot.db.is_opted_in(interaction.user.id, interaction.guild_id) if interaction.guild_id else False
    channel_id = bot.db.get_channel(interaction.guild_id) if interaction.guild_id else None
    enabled = bot.db.channel_enabled(interaction.guild_id) if interaction.guild_id else False
    channel_text = f"<#{channel_id}>" if channel_id else "not configured"
    await interaction.response.send_message(
        f"**Your DM opt-in:** {'ON' if opted else 'OFF'}\n**Server roast channel:** {channel_text}\n**Scheduled channel roasts:** {'ON' if enabled else 'OFF'}",
        ephemeral=True
    )

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing. Copy .env.example to .env and add your bot token.")
bot.run(TOKEN)
