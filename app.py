import os
import json
import time
import requests
from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import threading

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

SHOWS = {
    "tumm-se-tumm-tak": {
        "name": "Tumm Se Tum Tak",
        "show_id": "0-6-4z5727104"
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

# ================= HEADERS =================
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.zee5.com/",
    "Origin": "https://www.zee5.com"
}

# ================= GET SEASON =================
def get_season_id(show_id):
    url = f"https://gwapi.zee5.com/content/details/{show_id}?translation=en&country=IN"

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()

        tg_log(f"📦 SHOW DATA: {data}")

        seasons = (
            data.get("seasons")
            or data.get("result", {}).get("seasons")
            or []
        )

        if not seasons:
            tg_log("❌ No seasons found")
            return None

        season_id = seasons[0].get("id")
        tg_log(f"✅ Season ID: {season_id}")

        return season_id

    except Exception as e:
        tg_log(f"❌ Season error: {e}")
        return None

# ================= GET EPISODES =================
def get_latest_episode(show_id):
    season_id = get_season_id(show_id)
    if not season_id:
        return None

    url = f"https://gwapi.zee5.com/content/tvshow/?season_id={season_id}&page=1&limit=20&country=IN&platform=web"

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()

        tg_log(f"📦 EPISODE DATA: {data}")

        episodes = (
            data.get("episode")
            or data.get("episodes")
            or data.get("items")
            or data.get("result")
        )

        if not episodes:
            tg_log("❌ No episodes found")
            return None

        valid_eps = [ep for ep in episodes if isinstance(ep, dict)]

        if not valid_eps:
            tg_log("❌ No valid episode objects")
            return None

        valid_eps.sort(
            key=lambda x: x.get("release_date") or "",
            reverse=True
        )

        latest = valid_eps[0]

        tg_log(f"🎬 LATEST: {latest}")

        return {
            "id": latest.get("id") or latest.get("content_id"),
            "title": latest.get("title") or latest.get("name"),
            "date": latest.get("release_date") or latest.get("publish_date")
        }

    except Exception as e:
        tg_log(f"❌ Episode error: {e}")
        return None

# ================= CHECK =================
def check_for_new_episodes():
    tg_log("🔥 FUNCTION STARTED")

    for key, info in SHOWS.items():
        result = get_latest_episode(info["show_id"])
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
📅 {result["date"]}

🔥 https://www.zee5.com/tv-shows/details/{key}/{info["show_id"]}
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
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=5, max_instances=1)
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
