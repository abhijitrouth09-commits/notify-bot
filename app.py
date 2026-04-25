import os
import time
import json
import re
import threading
import subprocess

from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

SHOWS = {
    "tumm-se-tumm-tak": {"name": "Tumm Se Tum Tak", "url": "https://www.zee5.com/tv-shows/details/tumm-se-tumm-tak/0-6-4z5727104"},
    "saru": {"name": "Saru", "url": "https://www.zee5.com/tv-shows/details/saru/0-6-4z5727070"},
}

DATA_FILE = "last_episodes.json"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# ================= DEBUG =================
def debug(msg):
    print(msg)
    try:
        bot.send_message(ADMIN_CHAT_ID, f"🪵 {msg}")
    except:
        pass

# ================= ENSURE PLAYWRIGHT =================
def ensure_browser():
    try:
        debug("🔧 Ensuring Playwright browser...")
        subprocess.run(["playwright", "install", "chromium"], check=True)
        debug("✅ Browser ready")
    except Exception as e:
        debug(f"❌ Install failed: {e}")

# ================= LOAD =================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        last_episodes = json.load(f)
else:
    last_episodes = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(last_episodes, f)

# ================= SCRAPER =================
def get_latest_episode(show_url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )

            page = browser.new_page()
            page.goto(show_url, timeout=60000)
            page.wait_for_timeout(8000)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            episodes = []

            for img in soup.find_all("img"):
                title = img.get("title") or img.get("alt")

                if title and "Episode" in title:
                    match = re.search(r"Episode\s*(\d+)", title)
                    if match:
                        episodes.append(int(match.group(1)))

            browser.close()

            if episodes:
                return f"E{max(episodes)}"

            return None

    except Exception as e:
        debug(f"❌ Playwright Error: {e}")
        return None

# ================= CHECK =================
def check_for_new_episodes():
    debug("🔥 FUNCTION STARTED")

    for key, info in SHOWS.items():
        debug(f"📺 Checking: {info['name']}")

        latest = get_latest_episode(info["url"])

        if not latest:
            debug(f"⚠️ No data for {info['name']}")
            continue

        old = last_episodes.get(key)
        debug(f"📊 Old: {old} | New: {latest}")

        if old != latest:
            last_episodes[key] = latest
            save_data()

            bot.send_message(
                ADMIN_CHAT_ID,
                f"🚨 NEW EPISODE\n\n📺 {info['name']}\n🎬 {latest}\n\n{info['url']}"
            )
            debug("✅ Alert sent")
        else:
            debug("ℹ️ No update")

    debug("✅ CHECK COMPLETE")

# ================= ROUTES =================
@app.route('/')
def home():
    return "Bot Running ✅"

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return "", 200

# ================= COMMAND =================
@bot.message_handler(commands=['check'])
def manual_check(msg):
    if msg.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(msg, "🔄 Checking...")
        check_for_new_episodes()
    else:
        bot.reply_to(msg, "❌ Not allowed")

# ================= SCHEDULER =================
def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=10)
    scheduler.start()

# ================= MAIN =================
if __name__ == "__main__":
    ensure_browser()  # 🔥 CRITICAL FIX

    bot.remove_webhook()
    time.sleep(1)

    bot.set_webhook(
        url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
    )

    threading.Thread(target=run_scheduler, daemon=True).start()

    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
