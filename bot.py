import sys
import glob
import importlib.util
import logging
import logging.config
import asyncio
import uvloop
import time
import pytz
from pathlib import Path
from datetime import date, datetime
from aiohttp import web
from PIL import Image

# --- STEP 1: Loop & Library Setup ---
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
from kurigram import Client, idle, __version__
from kurigram.raw.all import layer
from kurigram.errors import FloodWait
import kurigram.utils

# Image pixel limit fix
Image.MAX_IMAGE_PIXELS = 500_000_000

# Database & Info Imports
from database.ia_filterdb import Media, Media2
from database.users_chats_db import db
from info import *
from utils import temp
from Script import script
from plugins import web_server, check_expired_premium, keep_alive
from dreamxbotz.Bot import dreamxbotz
from dreamxbotz.util.keepalive import ping_server
from dreamxbotz.Bot.clients import initialize_clients

# --- STEP 2: Logging Control (Render Fix) ---
logging.basicConfig(level=logging.INFO)
logging.getLogger("kurigram").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("pymongo").setLevel(logging.WARNING)

botStartTime = time.time()
kurigram.utils.MIN_CHANNEL_ID = -1009147483647

async def dreamxbotz_start():
    print('\n🚀 Initializing DreamxBotz on Kurigram...')
    await dreamxbotz.start()
    
    bot_info = await dreamxbotz.get_me()
    dreamxbotz.username = "@" + bot_info.username
    
    await initialize_clients()

    # --- Plugin Loading (Improved) ---
    plugins_dir = Path("plugins")
    for file in sorted(plugins_dir.rglob("*.py")):
        if file.name == "__init__.py":
            continue
        
        plugin_name = file.stem
        import_path = f"plugins.{plugin_name}"
        
        try:
            spec = importlib.util.spec_from_file_location(import_path, file)
            load = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(load)
            sys.modules[import_path] = load
            print(f"✅ Imported => {plugin_name}")
        except Exception as e:
            print(f"❌ Failed to load {plugin_name}: {e}")

    if ON_HEROKU:
        asyncio.create_task(ping_server()) 

    # Database setup
    try:
        b_users, b_chats = await db.get_banned()
        temp.BANNED_USERS, temp.BANNED_CHATS = b_users, b_chats
        await Media.ensure_indexes()
        if MULTIPLE_DB:
            await Media2.ensure_indexes()
            print("Multiple DB: ON")
    except:
        pass

    # Bot identity setup
    temp.ME = bot_info.id
    temp.U_NAME = bot_info.username
    temp.B_NAME = bot_info.first_name
    temp.B_LINK = bot_info.mention
    
    asyncio.create_task(check_expired_premium(dreamxbotz))
    
    # Restart Message logic
    tz = pytz.timezone('Asia/Kolkata')
    time_now = datetime.now(tz).strftime("%H:%M:%S %p")
    if LOG_CHANNEL:
        try:
            await dreamxbotz.send_message(
                chat_id=LOG_CHANNEL, 
                text=script.RESTART_TXT.format(temp.B_LINK, date.today(), time_now)
            )
        except:
            pass

    # --- Web Server for Render Port Binding ---
    try:
        web_app = await web_server()
        runner = web.AppRunner(web_app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", PORT).start()
    except:
        pass

    asyncio.create_task(keep_alive())
    print(f"✅ {bot_info.first_name} is LIVE!")
    await idle()
    
if __name__ == '__main__':
    try:
        asyncio.run(dreamxbotz_start())
    except FloodWait as e:
        time.sleep(e.value)
    except KeyboardInterrupt:
        logging.info('Service Stopped Bye 👋')
