import os
import requests
import re
import shutil
import discord
from datetime import datetime
import logging

logger = logging.getLogger("pirate_knights.selector")

def push_release(title: str, download_url: str) -> dict:
    """
    Pushes a torrent release to Sonarr and Radarr via their /api/v3/release/push endpoint.
    This instructs them to parse, match, and download the item automatically.
    """
    sonarr_url = os.getenv("SONARR_URL")
    sonarr_api_key = os.getenv("SONARR_API_KEY")
    radarr_url = os.getenv("RADARR_URL")
    radarr_api_key = os.getenv("RADARR_API_KEY")
    
    results = {}
    payload = {
        "title": title,
        "downloadUrl": download_url,
        "protocol": "torrent",
        "publishDate": datetime.utcnow().isoformat() + "Z",
        "indexer": "Fairy_Bit_Bot_Prowlarr"
    }
    
    if sonarr_url and sonarr_api_key:
        s_url = sonarr_url.strip().rstrip("/")
        try:
            logger.info(f"Pushing release to Sonarr: {title}")
            r = requests.post(
                f"{s_url}/api/v3/release/push", 
                headers={"X-Api-Key": sonarr_api_key.strip()}, 
                json=payload, 
                timeout=12
            )
            if r.status_code in [200, 201]:
                try:
                    resp_json = r.json()
                    data = resp_json[0] if isinstance(resp_json, list) else resp_json
                    if isinstance(data, dict):
                        approved = data.get("approved", True)
                        rejections = data.get("rejections", [])
                        if approved and not rejections:
                            results["sonarr"] = "Success (Grabbed/Approved) ✅"
                        else:
                            rej_msg = ", ".join(rejections) if rejections else "Rejected (e.g. series unmonitored or not in library)"
                            results["sonarr"] = f"Rejected ⚠️ ({rej_msg})"
                    else:
                        results["sonarr"] = "Success (200)"
                except Exception as ex:
                    results["sonarr"] = f"Success ({r.status_code}) but response unparsed: {ex}"
            else:
                results["sonarr"] = f"Failed ({r.status_code}): {r.text[:100]}"
        except Exception as e:
            results["sonarr"] = f"Error: {e}"
            logger.error(f"Error pushing to Sonarr: {e}")
            
    if radarr_url and radarr_api_key:
        r_url = radarr_url.strip().rstrip("/")
        try:
            logger.info(f"Pushing release to Radarr: {title}")
            r = requests.post(
                f"{r_url}/api/v3/release/push", 
                headers={"X-Api-Key": radarr_api_key.strip()}, 
                json=payload, 
                timeout=12
            )
            if r.status_code in [200, 201]:
                try:
                    resp_json = r.json()
                    data = resp_json[0] if isinstance(resp_json, list) else resp_json
                    if isinstance(data, dict):
                        approved = data.get("approved", True)
                        rejections = data.get("rejections", [])
                        if approved and not rejections:
                            results["radarr"] = "Success (Grabbed/Approved) ✅"
                        else:
                            rej_msg = ", ".join(rejections) if rejections else "Rejected (e.g. movie not in library or unmonitored)"
                            results["radarr"] = f"Rejected ⚠️ ({rej_msg})"
                    else:
                        results["radarr"] = "Success (200)"
                except Exception as ex:
                    results["radarr"] = f"Success ({r.status_code}) but response unparsed: {ex}"
            else:
                results["radarr"] = f"Failed ({r.status_code}): {r.text[:100]}"
        except Exception as e:
            results["radarr"] = f"Error: {e}"
            logger.error(f"Error pushing to Radarr: {e}")
            
    return results

def scrape_nyaa_title(nyaa_id: str) -> str:
    """
    Fetches the Nyaa.si view page for the given ID and extracts the actual
    torrent title from the <title> HTML tag.
    """
    try:
        url = f"https://nyaa.si/view/{nyaa_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        }
        logger.info(f"Fetching Nyaa.si view page to scrape release title for ID: {nyaa_id}")
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code == 200:
            m = re.search(r"<title>(.*?)</title>", r.text, re.IGNORECASE | re.DOTALL)
            if m:
                raw_title = m.group(1).strip()
                if raw_title.endswith(" :: Nyaa"):
                    raw_title = raw_title[:-8].strip()
                logger.info(f"Successfully scraped Nyaa title: {raw_title}")
                return raw_title
    except Exception as e:
        logger.error(f"Error scraping Nyaa title: {e}")
    return f"Nyaa Torrent [ID: {nyaa_id}]"

class TorrentDropdownView(discord.ui.View):
    def __init__(self, request_content, requester, king_user_id, announcements_channel_id):
        super().__init__(timeout=None)
        self.request_content = request_content
        self.requester = requester
        self.king_user_id = king_user_id
        self.announcements_channel_id = announcements_channel_id
        
        # Grab live storage statistics from the root directory
        total, used, free = shutil.disk_usage("/")
        free_gb = free // (2**30)
        
        # Pass the dynamic free_gb value into the dropdown item constructor
        self.add_item(TorrentDropdown(request_content, requester, king_user_id, announcements_channel_id, free_gb))


class TorrentDropdown(discord.ui.Select):
    def __init__(self, request_content, requester, king_user_id, announcements_channel_id, free_gb):
        self.request_content = request_content
        self.requester = requester
        self.king_user_id = king_user_id
        self.announcements_channel_id = announcements_channel_id
        self.free_gb = free_gb
        
        self.results_map = {}
        options = []

        # 1. Check if the request contains a direct link (like nyaa.si)
        direct_url = None
        direct_title = "Direct Torrent Link"
        scraped_title = None
        
        # Match Nyaa.si view page
        nyaa_match = re.search(r"https?://(www\.)?nyaa\.si/view/(\d+)", request_content)
        if nyaa_match:
            nyaa_id = nyaa_match.group(2)
            direct_url = f"https://nyaa.si/download/{nyaa_id}.torrent"
            scraped_title = scrape_nyaa_title(nyaa_id)
            direct_title = scraped_title
        elif "magnet:?" in request_content:
            direct_url = request_content
            # Try to get dn (display name) from magnet link
            dn_match = re.search(r"dn=([^&]+)", request_content)
            if dn_match:
                import urllib.parse
                direct_title = urllib.parse.unquote(dn_match.group(1)).replace("+", " ")
            else:
                direct_title = "Magnet Link Payload"
        elif request_content.startswith("http") and (request_content.endswith(".torrent") or "download" in request_content.lower()):
            direct_url = request_content
            direct_title = request_content.split("/")[-1] or "Direct Torrent URL"

        # If a direct download URL was found, prioritize it!
        if direct_url:
            self.results_map["direct_opt"] = {
                "title": direct_title,
                "downloadUrl": direct_url,
                "size_bytes": 0,
                "indexer": "DirectLink"
            }
            options.append(
                discord.SelectOption(
                    label=f"🔗 {direct_title[:80]}",
                    description="Download direct payload from the link provided.",
                    emoji="🔗",
                    value="direct_opt"
                )
            )

        # 2. Query Prowlarr for real search results
        prowlarr_url = os.getenv("PROWLARR_URL")
        prowlarr_api_key = os.getenv("PROWLARR_API_KEY")
        
        prowlarr_results = []
        if prowlarr_url and prowlarr_api_key:
            # Determine search query keyword
            search_query = request_content
            if request_content.startswith("http"):
                if scraped_title:
                    search_query = scraped_title
                elif "dn=" in request_content:
                    dn_match = re.search(r"dn=([^&]+)", request_content)
                    if dn_match:
                        import urllib.parse
                        search_query = urllib.parse.unquote(dn_match.group(1)).replace("+", " ")
                else:
                    path_words = re.sub(r"https?://[^/]+", "", request_content)
                    path_words = re.sub(r"[^a-zA-Z0-9]+", " ", path_words).strip()
                    search_query = path_words
            
            if search_query and len(search_query) > 2:
                logger.info(f"Querying Prowlarr for query: '{search_query}'")
                base_url = prowlarr_url.strip().rstrip("/")
                url = f"{base_url}/api/v1/search"
                headers = {"X-Api-Key": prowlarr_api_key.strip()}
                params = {"query": search_query}
                try:
                    r = requests.get(url, headers=headers, params=params, timeout=10)
                    if r.status_code == 200:
                        prowlarr_results = r.json()
                        logger.info(f"Prowlarr returned {len(prowlarr_results)} results.")
                    else:
                        logger.warning(f"Prowlarr search failed with code {r.status_code}")
                except Exception as e:
                    logger.error(f"Prowlarr connection error: {e}")

        # Add Prowlarr search results to options (limit to avoid exceeding Discord limits)
        for idx, item in enumerate(prowlarr_results):
            if len(options) >= 23: # max options inside a dropdown is 25 (reserve 1 for abort)
                break
                
            title = item.get("title", "Unknown release")
            download_url = item.get("downloadUrl")
            if not download_url:
                continue
                
            size_bytes = item.get("size", 0)
            size_gb = size_bytes / (2**30)
            seeders = item.get("seeders", 0)
            indexer = item.get("indexer", "Prowlarr")
            
            opt_key = f"prowlarr_{idx}"
            self.results_map[opt_key] = {
                "title": title,
                "downloadUrl": download_url,
                "size_bytes": size_bytes,
                "indexer": indexer
            }
            
            # Keep labels clean and below the 100 character limit
            label_text = f"📀 {title}"
            if len(label_text) > 95:
                label_text = label_text[:92] + "..."
            
            desc = f"Size: {size_gb:.1f} GB | Seeders: {seeders} | Indexer: {indexer}"[:100]
            
            options.append(
                discord.SelectOption(
                    label=label_text,
                    description=desc,
                    emoji="💾",
                    value=opt_key
                )
            )

        # Fallback to No Results option if absolutely no results found (neither direct link nor Prowlarr results)
        if not options:
            logger.info("No options populated. Adding 'No results available' option.")
            options.append(
                discord.SelectOption(
                    label="Ran into error / No results available", 
                    description="Prowlarr returned zero query matches or connection failed.", 
                    emoji="⚠️",
                    value="no_results"
                )
            )

        # Always add the Abort option at the very end
        options.append(
            discord.SelectOption(
                label="❌ Abort Request", 
                description="Cancel and dump this search query completely.", 
                emoji="🗑️",
                value="abort"
            )
        )

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

        if user_choice == "no_results":
            await interaction.response.send_message(
                "❌ **Error:** No search results are available for this query. Please use the Abort Request option.",
                ephemeral=True
            )
            return

        if user_choice == "abort":
            await interaction.response.edit_message(
                content=f"🙅‍♂️ **Search Aborted:** Request for *{self.request_content}* was tossed out.",
                view=None
            )
            return

        # Retrieve selected option metadata
        selected_data = self.results_map.get(user_choice)
        if not selected_data:
            await interaction.response.send_message("⚠️ Error: Selected option data is missing.", ephemeral=True)
            return

        selected_title = selected_data["title"]
        selected_download_url = selected_data["downloadUrl"]
        size_bytes = selected_data["size_bytes"]
        size_gb = size_bytes / (2**30)
        indexer = selected_data["indexer"]

        await interaction.response.edit_message(
            content=f"👑 **Source Selected!**\nChosen Payload: `{selected_title[:120]}`\nSent over to data central grid.",
            view=None
        )

        # 3. Call the release push API to actually send the torrent to Sonarr & Radarr!
        logger.info(f"Triggering release push for title: {selected_title}")
        push_statuses = push_release(selected_title, selected_download_url)
        
        # Calculate dynamic remaining space
        new_free_gb = self.free_gb - size_gb if size_gb > 0 else self.free_gb - 2.0

        announcements_channel = interaction.client.get_channel(self.announcements_channel_id)
        if announcements_channel:
            # Build pretty status block
            status_parts = []
            for service, status in push_statuses.items():
                status_parts.append(f"• **{service.capitalize()}:** {status}")
            status_text = "\n".join(status_parts) if status_parts else "• *No Servarr endpoints configured.*"

            await announcements_channel.send(
                f"📊 **DATA CENTRAL UPDATE**\n"
                f"📥 **Downloading:** `{selected_title[:100]}`\n"
                f"👤 **Request:** {self.request_content} (by {self.requester.mention})\n"
                f"🔌 **Servarr Integration Status:**\n{status_text}\n"
                f"⏳ **Status:** Download pipeline initialized via qBittorrent...\n"
                f"⚖️ **Size:** `{size_gb:.2f} GB` (Indexer: `{indexer}`)\n"
                f"💾 **Remaining size on disk:** `{new_free_gb:.1f} GB`"
            )
