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
    "tumm-se-tumm-tak": {"name": "Tumm Se Tum Tak", "id": "0-6-4z5727104"},
    "saru": {"name": "Saru", "id": "0-6-4z5727070"},
    "vasudha": {"name": "Vasudha", "id": "0-6-4z5612471"},
    "jagadhatri": {"name": "Jagadhatri", "id": "0-6-4z5853175"},
    "lakshmi-nivas": {"name": "Lakshmi Nivas", "id": "0-6-4z5891598"},
    "ganga-mai-ki-betiyan": {"name": "Ganga Mai Ki Betiyan", "id": "0-6-4z5793364"},
    "jaane-anjaane-hum-mile": {"name": "Jaane Anjaane Hum Mile", "id": "0-6-4z5646159"}
}

DATA_FILE = "last_episodes.json"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

last_episodes = {}

def get_latest_episode(show_id):
    url = f"https://catalogapi.zee5.com/v1/show/{show_id}?translation=en&country=IN"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://www.zee5.com/"
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()

        # Get latest episode from episodes list
        episodes = data.get("episodes", [])
        if episodes:
            latest = episodes[0]  # first one is newest
            title = latest.get("title", "")
            episode_no = latest.get("episode_no", "")
            release_date = latest.get("release_date", "") or latest.get("publish_date", "")
            return f"E{episode_no} {title} {release_date}"

        return None

    except Exception as e:
        print(f"API Error for {show_id}: {e}")
        return None

def check_for_new_episodes():
    global last_episodes
    print(f"[{time.strftime('%H:%M:%S')}] Checking {len(SHOWS)} shows using Catalog API...")

    for show_key, info in SHOWS.items():
        latest = get_latest_episode(info["id"])
        if not latest:
            continue

        old = last_episodes.get(show_key)
        if old != latest:
            last_episodes[show_key] = latest
            message = f"""🚨 **NEW EPISODE ALERT!** 🎉

📺 Show: {info["name"]}
🎬 Latest: {latest}

🔥 [Watch Now](https://www.zee5.com/tv-shows/details/{show_key}/{info["id"]})"""
            bot.send_message(ADMIN_CHAT_ID, message, parse_mode='Markdown')
            print(f"✅ Alert sent for {info['name']}")

# ====================== BASIC SETUP ======================
@app.route('/', methods=['GET'])
def home():
    return "Catalog API Bot Running ✅", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return '', 200

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ Catalog API Bot is alive!\n\n/check → manual check")

@bot.message_handler(commands=['check'])
def manual_check(message):
    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Checking using Catalog API...")
        check_for_new_episodes()
        bot.reply_to(message, "✅ Check done!")
    else:
        bot.reply_to(message, "❌ Only owner can use.")

def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=5)
    scheduler.start()
    print("🚀 Catalog API Scheduler started")

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}")
    threading.Thread(target=run_scheduler, daemon=True).start()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
