import os
import time
import json
import re
import threading
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
    "vasudha": {"name": "Vasudha", "url": "https://www.zee5.com/tv-shows/details/vasudha/0-6-4z5612471"},
    "jagadhatri": {"name": "Jagadhatri", "url": "https://www.zee5.com/tv-shows/details/jagadhatri/0-6-4z5853175"},
    "lakshmi-nivas": {"name": "Lakshmi Nivas", "url": "https://www.zee5.com/tv-shows/details/lakshmi-nivas/0-6-4z5891598"},
    "ganga-mai-ki-betiyan": {"name": "Ganga Mai Ki Betiyan", "url": "https://www.zee5.com/tv-shows/details/ganga-mai-ki-betiyan/0-6-4z5793364"},
    "jaane-anjaane-hum-mile": {"name": "Jaane Anjaane Hum Mile", "url": "https://www.zee5.com/tv-shows/details/jaane-anjaane-hum-mile/0-6-4z5646159"}
}

DATA_FILE = "last_episodes.json"

# ================= INIT =================
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# ================= DEBUG LOGGER =================
def debug(msg):
    try:
        print(msg)
        bot.send_message(ADMIN_CHAT_ID, f"🪵 {msg}")
    except:
        pass

# ================= LOAD =================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        last_episodes = json.load(f)
else:
    last_episodes = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(last_episodes, f)

# ================= PLAYWRIGHT =================
def get_latest_episode(show_url):
    try:
        debug(f"🌐 Opening: {show_url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )

            page = browser.new_page()

            debug("📡 Loading page...")
            page.goto(show_url, timeout=60000)

            page.wait_for_timeout(8000)
            debug("✅ Page loaded")

            html = page.content()
            debug(f"📄 HTML size: {len(html)}")

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
                latest = max(episodes)
                debug(f"🎬 Found episode: {latest}")
                return f"E{latest}"

            debug("⚠️ No episode found")
            return None

    except Exception as e:
        debug(f"❌ Playwright Error: {str(e)}")
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

            msg = f"""🚨 *NEW EPISODE*

📺 {info["name"]}
🎬 {latest}

🔥 {info["url"]}
"""
            bot.send_message(ADMIN_CHAT_ID, msg, parse_mode="Markdown")
            debug(f"✅ Alert sent for {info['name']}")
        else:
            debug(f"ℹ️ No update: {info['name']}")

    debug("✅ CHECK COMPLETE")

# ================= ROUTES =================
@app.route('/')
def home():
    return "Playwright Bot Running ✅"

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return "", 200

# ================= COMMANDS =================
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "✅ Bot running\nUse /check")

@bot.message_handler(commands=['check'])
def manual_check(msg):
    if msg.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(msg, "🔄 Checking...")
        check_for_new_episodes()
        bot.reply_to(msg, "✅ Done")
    else:
        bot.reply_to(msg, "❌ Not allowed")

# ================= SCHEDULER =================
def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=10)
    scheduler.start()
    debug("🚀 Scheduler started")

# ================= MAIN =================
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)

    bot.set_webhook(
        url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
    )

    threading.Thread(target=run_scheduler, daemon=True).start()

    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
