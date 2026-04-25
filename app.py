import os
import time
import json
import requests
from bs4 import BeautifulSoup
from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import threading

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

SHOWS = {
    "tumm-se-tumm-tak": {
        "name": "Tumm Se Tum Tak",
        "url": "https://www.zee5.com/tv-shows/details/tumm-se-tumm-tak/0-6-4z5727104",
        "mobile_url": "https://www.zee5.com/tv-shows/details/tumm-se-tumm-tak/0-6-4z5727104?isMobile=true"
    }
}

DATA_FILE = "last_episodes.json"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# ================= LOAD/SAVE =================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        last_episodes = json.load(f)
else:
    last_episodes = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(last_episodes, f)

# ================= LOGGER =================
def tg_log(chat_id, text):
    try:
        bot.send_message(chat_id, text[:3500])
    except:
        pass

# ================= FETCH =================
def fetch_html(url, mobile=False):
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 "
                "(KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
                if mobile else
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.zee5.com/",
            "Connection": "keep-alive",
        }

        session = requests.Session()
        session.headers.update(headers)

        r = session.get(url, timeout=20)

        if r.status_code != 200 or len(r.text) < 1000:
            return None, f"❌ Status {r.status_code} or blocked"

        return r.text, "✅ Page loaded"

    except Exception as e:
        return None, f"❌ Error: {e}"

# ================= PARSER =================
def extract_latest_episode(html):
    soup = BeautifulSoup(html, "html.parser")

    # try known class
    latest = soup.find("a", class_="iconsWrap latest")

    if latest and latest.get("href"):
        return "https://www.zee5.com" + latest.get("href")

    # fallback: find ANY episode link
    for a in soup.find_all("a", href=True):
        if "/tv-shows/details/" in a["href"] and "/0-1-" in a["href"]:
            return "https://www.zee5.com" + a["href"]

    return None

# ================= MAIN LOGIC =================
def get_latest_episode(show):
    # try desktop
    html, status = fetch_html(show["url"], mobile=False)

    if html:
        ep = extract_latest_episode(html)
        if ep:
            return ep, "✅ Found (desktop)"

    # fallback mobile
    html, status = fetch_html(show["mobile_url"], mobile=True)

    if html:
        ep = extract_latest_episode(html)
        if ep:
            return ep, "✅ Found (mobile)"

    return None, "❌ Could not extract"

# ================= CHECK =================
def check_for_new_episodes(debug_chat=None):
    chat_id = debug_chat if debug_chat else ADMIN_CHAT_ID

    tg_log(chat_id, "🔥 FUNCTION STARTED")

    for key, info in SHOWS.items():
        tg_log(chat_id, f"📺 Checking: {info['name']}")

        latest, status = get_latest_episode(info)
        tg_log(chat_id, f"🧾 Status: {status}")

        if latest:
            tg_log(chat_id, f"🎬 Latest:\n{latest}")

            old = last_episodes.get(key)

            if old != latest:
                last_episodes[key] = latest
                save_data()

                msg = f"""🚨 *NEW EPISODE ALERT!*

📺 {info["name"]}

🔥 [Watch Now]({latest})
"""
                bot.send_message(ADMIN_CHAT_ID, msg, parse_mode="Markdown")
                tg_log(chat_id, "✅ Alert sent")
            else:
                tg_log(chat_id, "ℹ️ No new episode")
        else:
            tg_log(chat_id, "⚠️ No result returned")

    tg_log(chat_id, "✅ CHECK DONE")

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
    bot.reply_to(message, "✅ Bot running\nUse /check")

@bot.message_handler(commands=['check'])
def manual_check(message):
    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Checking...")
        check_for_new_episodes(debug_chat=message.chat.id)
    else:
        bot.reply_to(message, "❌ Owner only")

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
