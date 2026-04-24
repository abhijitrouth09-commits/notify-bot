import os
import json
import time
import requests
from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import re
from bs4 import BeautifulSoup

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

SHOWS = {
    "tumm-se-tumm-tak": {
        "name": "Tumm Se Tum Tak",
        "url": "https://www.zee5.com/tv-shows/details/tumm-se-tumm-tak/0-6-4z5727104"
    },
}

DATA_FILE = "last_episodes.json"

# ================= INIT =================
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# ================= LOGGER =================
def tg_log(text):
    try:
        bot.send_message(ADMIN_CHAT_ID, f"🪵 {str(text)[:3500]}")
    except:
        pass

# ================= LOAD DATA =================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        last_episodes = json.load(f)
else:
    last_episodes = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(last_episodes, f)

# ================= SCRAPER =================
def get_latest_episode(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        tg_log("🌐 Fetching page...")

        r = requests.get(url, headers=headers, timeout=15)
        html = r.text

        if len(html) < 1000:
            tg_log("❌ Page too small (blocked)")
            return None

        soup = BeautifulSoup(html, "html.parser")

        # 🔥 Try to extract from script JSON
        scripts = soup.find_all("script")

        for script in scripts:
            if script.string and "episode" in script.string.lower():
                text = script.string

                # Try to find Episode patterns
                match = re.search(r'Episode\s*\d+', text, re.IGNORECASE)
                if match:
                    ep = match.group(0)
                    tg_log(f"✅ Found in script: {ep}")

                    return {
                        "id": ep,
                        "title": ep,
                        "date": "Latest"
                    }

        # 🔥 Fallback: raw text scan
        page_text = soup.get_text()

        match = re.search(r'Episode\s*\d+', page_text, re.IGNORECASE)
        if match:
            ep = match.group(0)
            tg_log(f"✅ Found in page text: {ep}")

            return {
                "id": ep,
                "title": ep,
                "date": "Latest"
            }

        tg_log("❌ No episode found")
        return None

    except Exception as e:
        tg_log(f"❌ Error: {e}")
        return None

# ================= CHECK =================
def check_for_new_episodes():
    tg_log("🔥 FUNCTION STARTED")

    for key, info in SHOWS.items():
        result = get_latest_episode(info["url"])
        if not result:
            tg_log("⚠️ No result returned")
            continue

        old_id = last_episodes.get(key)

        if old_id != result["id"]:
            last_episodes[key] = result["id"]
            save_data()

            message = f"""🚨 *NEW EPISODE*

📺 {info["name"]}
🎬 {result["title"]}

🔥 {info["url"]}
"""

            bot.send_message(ADMIN_CHAT_ID, message, parse_mode="Markdown")
            tg_log("✅ Alert sent")
        else:
            tg_log("ℹ️ No new episode")

# ================= FLASK =================
@app.route('/', methods=['GET'])
def home():
    return "Bot Running ✅", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return '', 200

# ================= COMMANDS =================
@bot.message_handler(commands=['start'])
def start(message):
    tg_log(f"📩 /start from {message.chat.id}")
    bot.reply_to(message, "✅ Bot running\nUse /check")

@bot.message_handler(commands=['check'])
def manual_check(message):
    tg_log(f"📩 /check from {message.chat.id}")

    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Checking...")

        try:
            check_for_new_episodes()
            bot.reply_to(message, "✅ Done")
        except Exception as e:
            tg_log(f"❌ ERROR: {e}")
            bot.reply_to(message, f"❌ Error: {e}")
    else:
        bot.reply_to(message, f"❌ Owner only\nYour ID: {message.chat.id}")

# ================= SCHEDULER =================
def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=10)
    scheduler.start()

# ================= MAIN =================
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)

    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
    tg_log(f"🔗 Webhook: {webhook_url}")

    bot.set_webhook(url=webhook_url)

    threading.Thread(target=run_scheduler, daemon=True).start()

    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
