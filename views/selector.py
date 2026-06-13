import discord
import modules.state as state

class TorrentDropdown(discord.ui.Select):
    def __init__(self, request_content, requester, king_user_id, announcements_channel_id):
        self.request_content = request_content
        self.requester = requester
        self.king_user_id = king_user_id
        self.announcements_channel_id = announcements_channel_id
        
        options = [
            discord.SelectOption(
                label="Johnny's Dub [Dual Audio]", 
                description="Size: 6.0 GB | Quality: 1080p Batch", 
                emoji="📀"
            ),
            discord.SelectOption(
                label="SubsPlease Release [Subbed]", 
                description="Size: 1.4 GB | Quality: 720p Single", 
                emoji="📝"
            ),
            discord.SelectOption(
                label="❌ Abort Request", 
                description="Cancel and dump this search query completely.", 
                emoji="🗑️"
            )
        ]
        
        # Display the live tracked storage space directly in the placeholder string
        current_space = state.get_storage_string()
        super().__init__(
            placeholder=f"Select Source ({current_space} Remaining)...", 
            min_values=1, 
            max_values=1, 
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.king_user_id:
            await interaction.response.send_message("You have no power here, peasant! 🌾", ephemeral=True)
            return

        user_choice = self.values[0]

        if user_choice == "❌ Abort Request":
            await interaction.response.edit_message(
                content=f"🙅‍♂️ **Search Aborted:** Request for *{self.request_content}* was tossed out.",
                view=None
            )
            return

        # Determine file size dynamically based on selection and modify storage balance
        file_size_gb = 6.0 if "Johnny" in user_choice else 1.4
        state.subtract_storage(file_size_gb)
        new_remaining = state.get_storage_string()

        await interaction.response.edit_message(
            content=f"👑 **Source Selected!**\nChosen Payload: `{user_choice}`\nSent over to data central grid.",
            view=None
        )

        announcements_channel = interaction.client.get_channel(self.announcements_channel_id)
        if announcements_channel:
            await announcements_channel.send(
                f"📊 **DATA CENTRAL UPDATE**\n"
                f"📥 **Downloading:** `{user_choice}`\n"
                f"👤 **Request:** {self.request_content} (by {self.requester.mention})\n"
                f"⏳ **Status:** Initializing download pipeline via qBittorrent...\n"
                f"⚖️ **Size:** `{file_size_gb} GB`\n"
                f"💾 **Remaining size on disk:** `{new_remaining}`"
            )

class TorrentDropdownView(discord.ui.View):
    def __init__(self, request_content, requester, king_user_id, announcements_channel_id):
        super().__init__(timeout=None)
        self.add_item(TorrentDropdown(request_content, requester, king_user_id, announcements_channel_id))