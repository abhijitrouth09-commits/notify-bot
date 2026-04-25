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
from playwright.sync_api import sync_playwright

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

last_episodes = {}

def get_latest_episode(show_url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(show_url, timeout=60000)
            page.wait_for_timeout(8000)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            for img in soup.find_all("img"):
                title = img.get("title") or img.get("alt")
                if title and "Episode" in title:
                    match = re.search(r"Episode\s*(\d+)", title)
                    if match:
                        episode_text = f"E{match.group(1)}"
                        browser.close()
                        return episode_text

            browser.close()
            return None
    except Exception as e:
        print(f"Playwright Error: {e}")
        return None

def check_for_new_episodes():
    global last_episodes
    print(f"[{time.strftime('%H:%M:%S')}] Checking with Playwright...")

    for show_key, info in SHOWS.items():
        latest = get_latest_episode(info["url"])
        if not latest:
            continue

        old = last_episodes.get(show_key)
        if old != latest:
            last_episodes[show_key] = latest
            message = f"""🚨 **NEW EPISODE ALERT!** 🎉

📺 Show: {info["name"]}
🎬 Latest: {latest}

🔥 [Watch Now]({info["url"]})"""
            bot.send_message(ADMIN_CHAT_ID, message, parse_mode='Markdown')
            print(f"✅ Alert sent for {info['name']}")

@app.route('/', methods=['GET'])
def home():
    return "Playwright Bot Running ✅", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return '', 200

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ Playwright Bot is alive!\n\n/check → manual check")

@bot.message_handler(commands=['check'])
def manual_check(message):
    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Checking with Playwright...")
        check_for_new_episodes()
        bot.reply_to(message, "✅ Check done!")
    else:
        bot.reply_to(message, "❌ Only owner can use.")

def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=8)
    scheduler.start()
    print("🚀 Playwright scheduler started")

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}")
    threading.Thread(target=run_scheduler, daemon=True).start()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
