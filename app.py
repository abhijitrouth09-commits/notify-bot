import os
import json
import time
import requests
from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import threading

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

SHOWS = {
    "tumm-se-tumm-tak": {
        "name": "Tumm Se Tum Tak",
        "show_id": "0-6-4z5727104"
    },
}

DATA_FILE = "last_episodes.json"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# ---------------- LOAD / SAVE ----------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(last_episodes, f)

last_episodes = load_data()

# ---------------- API FETCH ----------------
def get_latest_episode(show_id):
    url = f"https://gwapi.zee5.com/content/tvshow/{show_id}?country=IN&translation=en&platform=web"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "x-access-token": "guest"
    }

    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            print(f"❌ API failed: {r.status_code}")
            return None

        data = r.json()

        episodes = data.get("episodes", [])
        if not episodes:
            print("❌ No episodes found")
            return None

        latest = episodes[0]  # newest episode
        episode_id = latest.get("id")
        title = latest.get("title")

        print(f"✅ Latest: {title}")
        return episode_id, title

    except Exception as e:
        print(f"Error: {e}")
        return None

# ---------------- CHECK ----------------
def check_for_new_episodes():
    print(f"[{time.strftime('%H:%M:%S')}] Checking shows...")

    for key, info in SHOWS.items():
        result = get_latest_episode(info["show_id"])
        if not result:
            continue

        episode_id, title = result
        old_id = last_episodes.get(key)

        if old_id != episode_id:
            last_episodes[key] = episode_id
            save_data()

            message = f"""🚨 *NEW EPISODE ALERT!*

📺 *{info["name"]}*
🎬 {title}

🔥 Watch: https://www.zee5.com/tv-shows/details/{key}/{info["show_id"]}"""

            bot.send_message(ADMIN_CHAT_ID, message, parse_mode="Markdown")
            print("✅ Alert sent")

    print("Done\n")

# ---------------- FLASK ----------------
@app.route('/', methods=['GET'])
def home():
    return "Bot Running ✅", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return '', 200

# ---------------- COMMANDS ----------------
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ Bot running\n/check → manual check")

@bot.message_handler(commands=['check'])
def manual_check(message):
    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Checking...")
        check_for_new_episodes()
        bot.reply_to(message, "✅ Done")
    else:
        bot.reply_to(message, "❌ Owner only")

# ---------------- SCHEDULER ----------------
def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=5, max_instances=1)
    scheduler.start()

# ---------------- MAIN ----------------
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)

    bot.set_webhook(
        url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
    )

    threading.Thread(target=run_scheduler, daemon=True).start()

    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
