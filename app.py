import os
import json
import time
import requests
from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import xml.etree.ElementTree as ET

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

SHOWS = {
    "tumm-se-tumm-tak": {
        "name": "Tumm Se Tum Tak",
        "query": "Tumm Se Tum Tak latest episode"
    },
}

DATA_FILE = "last_episodes.json"

# ================= INIT =================
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# ================= TELEGRAM LOGGER =================
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

# ================= RSS FETCH =================
def get_latest_episode(query):
    try:
        url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
        tg_log(f"🌐 Fetching RSS: {url}")

        r = requests.get(url, timeout=15)
        root = ET.fromstring(r.content)

        items = root.findall(".//item")

        if not items:
            tg_log("❌ No RSS items found")
            return None

        latest = items[0]

        title = latest.find("title").text
        link = latest.find("link").text
        pub_date = latest.find("pubDate").text

        tg_log(f"📰 Latest RSS: {title}")

        return {
            "id": title,  # use title as unique ID
            "title": title,
            "date": pub_date,
            "link": link
        }

    except Exception as e:
        tg_log(f"❌ RSS error: {e}")
        return None

# ================= CHECK =================
def check_for_new_episodes():
    tg_log("🔥 FUNCTION STARTED")

    for key, info in SHOWS.items():
        result = get_latest_episode(info["query"])
        if not result:
            tg_log("⚠️ No result returned")
            continue

        old_id = last_episodes.get(key)

        if old_id != result["id"]:
            last_episodes[key] = result["id"]
            save_data()

            message = f"""🚨 *NEW UPDATE*

📺 {info["name"]}
📰 {result["title"]}
📅 {result["date"]}

🔗 {result["link"]}
"""

            bot.send_message(ADMIN_CHAT_ID, message, parse_mode="Markdown")
            tg_log("✅ Alert sent")
        else:
            tg_log("ℹ️ No new update")

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
    bot.reply_to(message, "✅ Bot is running\nUse /check")

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
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=10, max_instances=1)
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
