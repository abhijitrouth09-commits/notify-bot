import os
import json
import time
import requests
from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import threading

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

SHOWS = {
    "tumm-se-tumm-tak": {
        "name": "Tumm Se Tum Tak",
        "show_id": "0-6-4z5727104"
    },
}

DATA_FILE = "last_episodes.json"

# ================== INIT ==================
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# ================== LOAD DATA ==================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        last_episodes = json.load(f)
else:
    last_episodes = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(last_episodes, f)

# ================== API FUNCTIONS ==================
def get_season_id(show_id):
    url = f"https://gwapi.zee5.com/content/tvshow/{show_id}?country=IN&platform=web"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "x-access-token": "guest"
    }

    try:
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()

        seasons = data.get("seasons", [])
        if not seasons:
            print("❌ No seasons found")
            return None

        season_id = seasons[0].get("id")
        print(f"Season ID: {season_id}")
        return season_id

    except Exception as e:
        print("Season error:", e)
        return None


def get_latest_episode(show_id):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "x-access-token": "guest",
        "Referer": "https://www.zee5.com/",
        "Origin": "https://www.zee5.com"
    }

    season_id = get_season_id(show_id)
    if not season_id:
        return None

    url = f"https://gwapi.zee5.com/content/tvshow/?season_id={season_id}&page=1&limit=20&country=IN&platform=web"

    try:
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()

        print("DEBUG keys:", data.keys())

        episodes = data.get("episode") or data.get("episodes")

        if not episodes:
            print("❌ No episodes found")
            return None

        # Sort by release_date (latest first)
        episodes.sort(
            key=lambda x: x.get("release_date", ""),
            reverse=True
        )

        latest = episodes[0]

        print("Latest:", latest.get("title"))

        return {
            "id": latest.get("id"),
            "title": latest.get("title"),
            "date": latest.get("release_date")
        }

    except Exception as e:
        print("Episode error:", e)
        return None


# ================== CHECKER ==================
def check_for_new_episodes():
    print(f"[{time.strftime('%H:%M:%S')}] Checking...")

    for key, info in SHOWS.items():
        result = get_latest_episode(info["show_id"])
        if not result:
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
            print("✅ Alert sent")

    print("Done\n")


# ================== FLASK ==================
@app.route('/', methods=['GET'])
def home():
    return "Bot Running ✅", 200


@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return '', 200


# ================== COMMANDS ==================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ Bot is running\nUse /check to test")


@bot.message_handler(commands=['check'])
def manual_check(message):
    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Checking...")
        check_for_new_episodes()
        bot.reply_to(message, "✅ Done")
    else:
        bot.reply_to(message, "❌ Owner only")


# ================== SCHEDULER ==================
def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=5, max_instances=1)
    scheduler.start()


# ================== MAIN ==================
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)

    bot.set_webhook(
        url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
    )

    threading.Thread(target=run_scheduler, daemon=True).start()

    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
