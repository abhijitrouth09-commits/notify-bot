import os
import json
import time
import requests
from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import re
from bs4 import BeautifulSoup

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
BROWSERLESS_TOKEN = os.getenv("BROWSERLESS_TOKEN")

SHOWS = {
    "tumm-se-tumm-tak": {
        "name": "Tumm Se Tum Tak",
        "url": "https://www.zee5.com/tv-shows/details/tumm-se-tumm-tak/0-6-4z5727104"
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

# ================= BROWSERLESS FETCH =================
def fetch_rendered_html(url):
    try:
        api_url = f"https://chrome.browserless.io/function?token={BROWSERLESS_TOKEN}"

        payload = {
            "code": f"""
                async ({'{'} page {'}'}) => {{
                    await page.goto("{url}", {{ waitUntil: 'networkidle2' }});
                    await new Promise(r => setTimeout(r, 5000));
                    return await page.content();
                }}
            """
        }

        tg_log("🌐 Loading via Browserless (advanced)...")

        r = requests.post(api_url, json=payload, timeout=40)

        if r.status_code != 200:
            tg_log(f"❌ Browserless error: {r.status_code} | {r.text[:200]}")
            return None

        tg_log("✅ Full page loaded")

        return r.text

    except Exception as e:
        tg_log(f"❌ Fetch error: {e}")
        return None

# ================= PARSE =================
def get_latest_episode(url):
    html = fetch_rendered_html(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()

    # now JS-loaded content is present
    matches = re.findall(r'Episode\s*\d+', text, re.IGNORECASE)

    if not matches:
        tg_log("❌ No episode found after JS load")
        return None

    numbers = [int(re.search(r'\d+', m).group()) for m in matches]
    latest = max(numbers)

    episode_text = f"Episode {latest}"

    tg_log(f"🎬 Found: {episode_text}")

    return {
        "id": episode_text,
        "title": episode_text
    }
# ================= CHECK =================
def check_for_new_episodes():
    tg_log("🔥 FUNCTION STARTED")

    for key, info in SHOWS.items():
        result = get_latest_episode(info["url"])
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

🔥 {info["url"]}
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
    bot.reply_to(message, "✅ Bot running\nUse /check")

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
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=10)
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
