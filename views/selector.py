import shutil
import discord

class TorrentDropdownView(discord.ui.View):
    def __init__(self, request_content, requester, king_user_id, announcements_channel_id):
        super().__init__(timeout=None)
        self.request_content = request_content
        self.requester = requester
        self.king_user_id = king_user_id
        self.announcements_channel_id = announcements_channel_id
        
        # 1. Grab live storage statistics from the root directory
        total, used, free = shutil.disk_usage("/")
        
        # 2. Convert raw bytes cleanly into Gigabytes (1024^3)
        free_gb = free // (2**30)
        
        # 3. Pass the dynamic free_gb value into the dropdown item constructor
        self.add_item(TorrentDropdown(request_content, requester, king_user_id, announcements_channel_id, free_gb))


class TorrentDropdown(discord.ui.Select):
    def __init__(self, request_content, requester, king_user_id, announcements_channel_id, free_gb):
        self.request_content = request_content
        self.requester = requester
        self.king_user_id = king_user_id
        self.announcements_channel_id = announcements_channel_id
        self.free_gb = free_gb
        
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
        
        # Look here! Your placeholder now injects your laptop's actual remaining space!
        super().__init__(
            placeholder=f"Select Source ({free_gb} GB Free on Disk)...", 
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

        # Calculate a mock simulated remaining space line for the final printout
        file_size_gb = 6.0 if "Johnny" in user_choice else 1.4
        mock_new_remaining = self.free_gb - file_size_gb

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
                f"💾 **Remaining size on disk:** `{mock_new_remaining:.1f} GB`"
            )
