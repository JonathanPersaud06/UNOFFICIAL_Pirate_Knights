import os
import discord
import asyncio
import logging
from discord.ext import commands
from dotenv import load_dotenv

# Import our Palantir AIP Client and Views
from modules.palantir_aip import AIPAgentClient
from views.gatekeeper import InitialGatekeeperPanel

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("pirate_knights")

load_dotenv()

# Required Discord Settings
TOKEN = (os.getenv("DISCORD_TOKEN") or "").strip()
PEASANT_CHANNEL_ID = os.getenv("PEASANT_CHANNEL_ID")
KING_CHANNEL_ID = os.getenv("KING_CHANNEL_ID")
ANNOUNCEMENTS_CHANNEL_ID = os.getenv("ANNOUNCEMENTS_CHANNEL_ID")
KING_USER_ID = os.getenv("KING_USER_ID")

# Verify core Discord configs
if not TOKEN:
    logger.warning("DISCORD_TOKEN is missing in .env! Bot will not start.")
if not PEASANT_CHANNEL_ID:
    logger.warning("PEASANT_CHANNEL_ID is missing in .env!")
if not KING_CHANNEL_ID:
    logger.warning("KING_CHANNEL_ID is missing in .env!")
if not ANNOUNCEMENTS_CHANNEL_ID:
    logger.warning("ANNOUNCEMENTS_CHANNEL_ID is missing in .env!")
if not KING_USER_ID:
    logger.warning("KING_USER_ID is missing in .env!")

# Initialize Palantir AIP Agent Client
aip_client = AIPAgentClient()

# Set up Discord bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Track active request sessions (mapping request content to session details)
active_sessions = {}

# Load Cogs/extensions
async def load_extensions():
    try:
        # Check if modules/status.py exists and setup status Cog
        await bot.load_extension("modules.status")
        logger.info("Successfully loaded modules.status cog.")
    except Exception as e:
        logger.error(f"Error loading status cog: {e}")

@bot.event
async def on_ready():
    logger.info(f"SUCCESS: {bot.user} is online and operational.")
    print(f"SUCCESS: {bot.user} is online.")

# The Message Router (Peasant -> AIP -> King pipeline)
@bot.event
async def on_message(message):
    # Don't respond to ourselves
    if message.author == bot.user:
        return

    # Check if this message is in the peasant channel and mentions the bot
    peasant_ch_id = int(PEASANT_CHANNEL_ID) if PEASANT_CHANNEL_ID else None
    
    if peasant_ch_id and message.channel.id == peasant_ch_id and bot.user.mentioned_in(message):
        # Extract the request (strip out the bot mention)
        request_text = message.content.replace(f"<@!{bot.user.id}>", "").replace(f"<@{bot.user.id}>", "").strip()
        
        if not request_text:
            await message.channel.send("🌾 Ahoy Peasant! Mention me along with what you want to download (e.g., `@Bot Download Bleach 1080p`).")
            return

        # 1. Inform the peasant that the request is being analyzed by our AI Orchestrator
        status_msg = await message.channel.send(
            f"🌾 **Your request received, peasant!** `{request_text}`\n"
            f"🔮 *Analyzing disk quota, system parameters, and recording in Palantir AIP Ontology...*"
        )

        try:
            # 2. Spin up a new session with our Palantir AIP Orchestrator
            logger.info("Main: Creating Palantir AIP session...")
            session_id = aip_client.create_session()
            
            # 3. Prompt the agent to evaluate the request and trigger our action
            logger.info(f"Main: Prompting AIP with peasant request: '{request_text}'")
            # We add context so the agent knows who requested it and where
            full_prompt = f"Peasant '{message.author.name}' requested: '{request_text}'."
            aip_evaluation = aip_client.prompt_agent(session_id, full_prompt)
            
            # 4. Save session metadata for later reference
            active_sessions[request_text] = {
                "session_id": session_id,
                "requester": message.author,
                "aip_response": aip_evaluation
            }

            # 5. Send notification to peasant that it has gone to the King's court
            await status_msg.edit(
                content=f"📝 **Request Registered in Palantir AIP!**\n"
                        f"👑 *Sent over to the High King's Court for approval. Please wait...*"
            )

            # 6. Dispatch the evaluation and approval view to the King Channel
            king_ch_id = int(KING_CHANNEL_ID) if KING_CHANNEL_ID else None
            king_user_id_val = int(KING_USER_ID) if KING_USER_ID else None
            ann_ch_id_val = int(ANNOUNCEMENTS_CHANNEL_ID) if ANNOUNCEMENTS_CHANNEL_ID else None

            if king_ch_id and king_user_id_val and ann_ch_id_val:
                king_channel = bot.get_channel(king_ch_id)
                if king_channel:
                    # Construct message to the King
                    king_message = (
                        f"🛡️ 👑 **NEW MEDIA REQUEST SUBMITTED** 👑 🛡️\n"
                        f"👤 **Requester:** {message.author.mention}\n"
                        f"📋 **Request Title:** `{request_text}`\n\n"
                        f"🔮 **Palantir AIP Orchestrator Assessment:**\n"
                        f"```markdown\n{aip_evaluation}\n```\n"
                        f"Sire, please evaluate this request below:"
                    )
                    
                    # Send with InitialGatekeeperPanel
                    await king_channel.send(
                        content=king_message,
                        view=InitialGatekeeperPanel(
                            request_content=request_text,
                            requester=message.author,
                            king_user_id=king_user_id_val,
                            announcements_channel_id=ann_ch_id_val,
                            aip_response=aip_evaluation
                        )
                    )
                    logger.info("Main: Dispatch message sent to King's Court successfully.")
                else:
                    logger.error("Main: Could not resolve King Channel object.")
            else:
                logger.error("Main: Missing necessary env keys to send message to King's channel.")

        except Exception as e:
            logger.error(f"Error in peasant request pipeline: {e}")
            await status_msg.edit(content="⚠️ **Error processing request.** Our technical mages have been notified!")

    # Standard command processing
    await bot.process_commands(message)

async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
