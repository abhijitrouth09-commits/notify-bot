import os
import json
import time
import requests
from bs4 import BeautifulSoup
from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import re

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

SHOWS = {
    "tumm-se-tumm-tak": {"name": "Tumm Se Tum Tak", "url": "https://www.zee5.com/tv-shows/details/tumm-se-tumm-tak/0-6-4z5727104"},
}

DATA_FILE = "last_episodes.json"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

last_episodes = load_data()

def get_latest_episode(show_url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(show_url, headers=headers, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        raw_text = soup.get_text(separator=" | ")

        print("\n" + "="*80)
        print("DEBUG - FULL PAGE TEXT (first 800 chars):")
        print(raw_text[:800])
        print("="*80)

        # Super aggressive patterns for today's episode
        patterns = [
            r'E\d+\s+\d+m?\s+\d+\s+[A-Za-z]+',   # E289 32m 24 Apr
            r'E\d+',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, raw_text)
            if matches:
                latest = matches[0]
                print(f"✅ MATCH FOUND: {latest}")
                return latest[:250]

        print("❌ NO MATCH FOUND")
        return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def check_for_new_episodes():
    global last_episodes
    print(f"[{time.strftime('%H:%M:%S')}] === CHECK STARTED ===")

    for show_key, info in SHOWS.items():
        print(f"Checking {info['name']}...")
        latest = get_latest_episode(info["url"])

        if latest:
            old = last_episodes.get(show_key)
            print(f"Old: {old} | New: {latest}")

            if old != latest:
                last_episodes[show_key] = latest
                save_data(last_episodes)
                message = f"""🚨 **NEW EPISODE ALERT!** 🎉

📺 Show: {info["name"]}
🎬 Latest: {latest}

🔥 [Watch Now]({info["url"]})"""
                bot.send_message(ADMIN_CHAT_ID, message, parse_mode='Markdown')
                print("✅ ALERT SENT!")

    print("=== CHECK FINISHED ===\n")

# ====================== ROUTES ======================
@app.route('/', methods=['GET'])
def home():
    return "Bot Running ✅", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return '', 200

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ Bot is alive!\n\n/check → test\n/reset → clear data")

@bot.message_handler(commands=['check'])
def manual_check(message):
    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Checking now...")
        check_for_new_episodes()
        bot.reply_to(message, "✅ Check done!")
    else:
        bot.reply_to(message, "❌ Only owner can use.")

@bot.message_handler(commands=['reset'])
def reset(message):
    if message.chat.id == ADMIN_CHAT_ID:
        global last_episodes
        last_episodes = {}
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        bot.reply_to(message, "✅ Data cleared. Next check will see everything as new.")

# ====================== SCHEDULER ======================
def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=5)
    scheduler.start()
    print("🚀 Scheduler started")

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}")
    
    threading.Thread(target=run_scheduler, daemon=True).start()
    
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
