import os
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN").strip()
# ... ensure your other IDs are loaded here ...

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# This loads your modules (like modules/status.py)
async def load_extensions():
    await bot.load_extension("modules.status")

@bot.event
async def on_ready():
    print(f"SUCCESS: {bot.user} is online.")

# The Message Router
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Keep your Peasant -> King routing logic right here in main.py
    # for now, as it handles direct message interception.
    if message.channel.id == int(os.getenv("PEASANT_CHANNEL_ID")) and bot.user.mentioned_in(message):
        # ... (Your existing routing logic) ...
        pass

    await bot.process_commands(message)

async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())