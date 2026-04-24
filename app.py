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

last_episodes = {}

def get_latest_episode(show_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.zee5.com/",
        "DNT": "1",
        "Connection": "keep-alive",
    }
    try:
        r = requests.get(show_url, headers=headers, timeout=20)
        print(f"Status: {r.status_code} | Length: {len(r.text)} chars")

        if len(r.text) < 1000:
            print("⚠️ Blocked - page too small")
            return None

        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text(separator=" | ")

        # Strong pattern for today's episode
        match = re.search(r'E\d+\s+\d+m?\s+\d+\s+[A-Za-z]+', text)
        if match:
            print(f"✅ Found: {match.group(0)}")
            return match.group(0)

        match = re.search(r'E\d+', text)
        if match:
            print(f"✅ Basic match: {match.group(0)}")
            return match.group(0)

        print("❌ No episode found")
        return None

    except Exception as e:
        print(f"Error: {e}")
        return None

def check_for_new_episodes():
    print(f"[{time.strftime('%H:%M:%S')}] Checking shows...")
    for show_key, info in SHOWS.items():
        latest = get_latest_episode(info["url"])
        if latest:
            old = last_episodes.get(show_key)
            if old != latest:
                last_episodes[show_key] = latest
                message = f"""🚨 **NEW EPISODE ALERT!** 🎉

📺 Show: {info["name"]}
🎬 Latest: {latest}

🔥 [Watch Now]({info["url"]})"""
                bot.send_message(ADMIN_CHAT_ID, message, parse_mode='Markdown')
                print("✅ Alert sent!")
    print("Check finished.\n")

# ====================== SETUP ======================
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
    bot.reply_to(message, "✅ Bot is alive!\n\n/check → test")

@bot.message_handler(commands=['check'])
def manual_check(message):
    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Checking now...")
        check_for_new_episodes()
        bot.reply_to(message, "✅ Check done!")
    else:
        bot.reply_to(message, "❌ Owner only")

def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=5)
    scheduler.start()

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}")
    threading.Thread(target=run_scheduler, daemon=True).start()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
