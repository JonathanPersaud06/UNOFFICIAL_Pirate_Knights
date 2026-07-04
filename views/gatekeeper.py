import discord
from views.selector import TorrentDropdownView

class InitialGatekeeperPanel(discord.ui.View):
    def __init__(self, request_content, requester, king_user_id, announcements_channel_id, aip_response=None):
        super().__init__(timeout=None)
        self.request_content = request_content
        self.requester = requester
        self.king_user_id = king_user_id
        self.announcements_channel_id = announcements_channel_id
        self.aip_response = aip_response

    @discord.ui.button(label="Yes, Search Sources", style=discord.ButtonStyle.green, emoji="🔍")
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.king_user_id:
            await interaction.response.send_message("You have no power here, peasant! 🌾", ephemeral=True)
            return

        await interaction.response.edit_message(
            content=f"👑 **Initial Approval Confirmed!**\nSire, select your preferred torrent source file for:\n> `{self.request_content}`",
            view=TorrentDropdownView(self.request_content, self.requester, self.king_user_id, self.announcements_channel_id)
        )

    @discord.ui.button(label="No, Deny Request", style=discord.ButtonStyle.red, emoji="❌")
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.king_user_id:
            await interaction.response.send_message("You have no power here, peasant! 🌾", ephemeral=True)
            return

        await interaction.response.edit_message(
            content=f"🙅‍♂️ **Request Denied Instantly.**\nRejected request: *{self.request_content}*",
            view=None
        )
