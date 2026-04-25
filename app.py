import os
import time
import json
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
        "content_id": "0-6-4z5727104"
    }
}

DATA_FILE = "last_episodes.json"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# ================= LOAD =================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        last_episodes = json.load(f)
else:
    last_episodes = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(last_episodes, f)

# ================= API FETCH =================
def get_latest_episode(show):
    try:
        url = f"https://gwapi.zee5.com/content/tvshow/{show['content_id']}?translation=en&country=IN"

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.zee5.com/"
        }

        r = requests.get(url, headers=headers, timeout=15)

        if r.status_code != 200:
            return None, f"❌ API status {r.status_code}"

        data = r.json()

        # 🔥 Navigate to episodes
        seasons = data.get("seasons", [])

        if not seasons:
            return None, "❌ No seasons"

        latest_episode = None

        for season in seasons:
            for ep in season.get("episodes", []):
                if not latest_episode or ep.get("episode_number", 0) > latest_episode.get("episode_number", 0):
                    latest_episode = ep

        if not latest_episode:
            return None, "❌ No episodes"

        ep_num = latest_episode.get("episode_number")
        ep_id = latest_episode.get("id")

        ep_url = f"https://www.zee5.com/tv-shows/details/{show['name'].lower().replace(' ', '-')}/{ep_id}"

        return ep_url, f"✅ Episode {ep_num}"

    except Exception as e:
        return None, f"❌ Error: {e}"

# ================= CHECK =================
def check_for_new_episodes(debug_chat=None):
    chat_id = debug_chat if debug_chat else ADMIN_CHAT_ID

    bot.send_message(chat_id, "🔥 FUNCTION STARTED")

    for key, info in SHOWS.items():
        bot.send_message(chat_id, f"📺 Checking: {info['name']}")

        latest, status = get_latest_episode(info)

        bot.send_message(chat_id, f"🧾 Status: {status}")

        if latest:
            bot.send_message(chat_id, f"🎬 {latest}")

            old = last_episodes.get(key)

            if old != latest:
                last_episodes[key] = latest
                save_data()

                msg = f"""🚨 *NEW EPISODE*

📺 {info["name"]}

🔥 [Watch Now]({latest})
"""
                bot.send_message(ADMIN_CHAT_ID, msg, parse_mode="Markdown")
                bot.send_message(chat_id, "✅ Alert sent")
            else:
                bot.send_message(chat_id, "ℹ️ No new episode")
        else:
            bot.send_message(chat_id, "⚠️ No result")

    bot.send_message(chat_id, "✅ CHECK DONE")

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
@bot.message_handler(commands=['check'])
def manual_check(message):
    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Checking...")
        check_for_new_episodes(debug_chat=message.chat.id)

# ================= SCHEDULER =================
def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=5)
    scheduler.start()

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
