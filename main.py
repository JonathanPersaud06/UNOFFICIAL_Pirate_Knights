import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from views.gatekeeper import InitialGatekeeperPanel

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN").strip()
PEASANT_CHANNEL_ID = int(os.getenv("PEASANT_CHANNEL_ID").strip())
KING_CHANNEL_ID = int(os.getenv("KING_CHANNEL_ID").strip())
ANNOUNCEMENTS_CHANNEL_ID = int(os.getenv("ANNOUNCEMENTS_CHANNEL_ID").strip())
KING_USER_ID = int(os.getenv("KING_USER_ID").strip())

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("=============================================")
    print(f" SUCCESS: Fairy.Bit Refactored Module Grid Online!")
    print("=============================================")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.channel.id == PEASANT_CHANNEL_ID:
        if bot.user.mentioned_in(message):
            clean_request = message.content.replace(f'<@!{bot.user.id}>', '').replace(f'<@{bot.user.id}>', '').strip()
            await message.channel.send(f"⚙️ Processing request for {message.author.mention}... routing up to the High Court.")

            king_channel = bot.get_channel(KING_CHANNEL_ID)
            if king_channel:
                await king_channel.send(
                    content=f"👑 **Sire, an incoming media entry requires review!**\n"
                            f"User <@{KING_USER_ID}>, do you authorize searching for:\n"
                            f"> `{clean_request}`?",
                    view=InitialGatekeeperPanel(clean_request, message.author, KING_USER_ID, ANNOUNCEMENTS_CHANNEL_ID)
                )

    await bot.process_commands(message)

bot.run(TOKEN)