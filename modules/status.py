import discord
import os
from discord.ext import commands, tasks

class StatusMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = int(os.getenv("ANNOUNCEMENTS_CHANNEL_ID"))
        self.hourly_status_update.start()

    def cog_unload(self):
        self.hourly_status_update.cancel()

    @tasks.loop(hours=1)
    async def hourly_status_update(self):
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            # Placeholder logic
            await channel.send("--- 🕒 Hourly Status Update: System Optimal ---")

    @hourly_status_update.before_loop
    async def before_status_update(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(StatusMonitor(bot))