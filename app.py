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
    "saru": {"name": "Saru", "url": "https://www.zee5.com/tv-shows/details/saru/0-6-4z5727070"},
    "vasudha": {"name": "Vasudha", "url": "https://www.zee5.com/tv-shows/details/vasudha/0-6-4z5612471"},
    "jagadhatri": {"name": "Jagadhatri", "url": "https://www.zee5.com/tv-shows/details/jagadhatri/0-6-4z5853175"},
    "lakshmi-nivas": {"name": "Lakshmi Nivas", "url": "https://www.zee5.com/tv-shows/details/lakshmi-nivas/0-6-4z5891598"},
    "ganga-mai-ki-betiyan": {"name": "Ganga Mai Ki Betiyan", "url": "https://www.zee5.com/tv-shows/details/ganga-mai-ki-betiyan/0-6-4z5793364"},
    "jaane-anjaane-hum-mile": {"name": "Jaane Anjaane Hum Mile", "url": "https://www.zee5.com/tv-shows/details/jaane-anjaane-hum-mile/0-6-4z5646159"}
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
        raw_text = soup.get_text(separator=" | ", strip=True)

        print(f"\n🔍 DEBUG - Page length: {len(raw_text)} characters")
        print(f"🔍 First 500 chars: {raw_text[:500]}...")

        # Very aggressive search for episode numbers
        patterns = [
            r'E\d+\s*[\d]*m?\s*[\d]*\s*[A-Za-z]+',   # E289 32m 24 Apr
            r'E\d+',                                 # Any E number
        ]

        all_matches = []
        for pattern in patterns:
            matches = re.findall(pattern, raw_text)
            if matches:
                all_matches.extend(matches)

        print(f"🔍 All potential episode matches found: {all_matches}")

        if all_matches:
            latest = all_matches[0]   # first one is usually newest
            print(f"✅ SELECTED LATEST: {latest}")
            return latest[:250]

        print("❌ No episode pattern matched")
        return None

    except Exception as e:
        print(f"❌ Error fetching page: {e}")
        return None

def check_for_new_episodes():
    global last_episodes
    print(f"[{time.strftime('%H:%M:%S')}] === STARTING FULL CHECK ===")

    for show_key, info in SHOWS.items():
        print(f"\n📡 Checking {info['name']} ...")
        latest = get_latest_episode(info["url"])
        
        if not latest:
            print(f"   → No episode detected")
            continue

        old = last_episodes.get(show_key)
        print(f"   Old saved: {old}")
        print(f"   New found: {latest}")

        if old != latest:
            last_episodes[show_key] = latest
            save_data(last_episodes)
            print(f"   → NEW EPISODE DETECTED! Sending alert...")

            message = f"""🚨 **NEW EPISODE ALERT!** 🎉

📺 **Show:** {info["name"]}
🎬 **Latest:** {latest}

🔥 [Watch Now]({info["url"]})"""

            bot.send_message(ADMIN_CHAT_ID, message, parse_mode='Markdown')
            print(f"   ✅ Alert sent for {info['name']}")
        else:
            print(f"   → No change")

    print(f"[{time.strftime('%H:%M:%S')}] === CHECK COMPLETED ===\n")

# ====================== ROUTES & COMMANDS ======================
@app.route('/', methods=['GET'])
def home():
    return "Notification Bot Running ✅", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return '', 200

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ Notification Bot is alive!\n\n/check → manual check\n/reset → clear saved episodes")

@bot.message_handler(commands=['check'])
def manual_check(message):
    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Checking all shows now...")
        check_for_new_episodes()
        bot.reply_to(message, "✅ Check done!")
    else:
        bot.reply_to(message, "❌ Only owner can use.")

@bot.message_handler(commands=['reset'])
def reset_data(message):
    if message.chat.id == ADMIN_CHAT_ID:
        global last_episodes
        last_episodes = {}
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        bot.reply_to(message, "✅ All saved episodes cleared.")
    else:
        bot.reply_to(message, "❌ Only owner can use.")

# ====================== SCHEDULER ======================
def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=5)
    scheduler.start()
    print("🚀 Scheduler started - checking every 5 minutes")

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}")
    
    threading.Thread(target=run_scheduler, daemon=True).start()
    
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
