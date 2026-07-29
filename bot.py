برای تبدیل این کد از حالت کولب (Jupyter Notebook) به یک فایل پایتون استاندارد (bot.py)، دو تغییر اصلی انجام شده است:
 * دستورات علامت تعجب (!pip و !apt) که مربوط به محیط نوت‌بوک بودند حذف شدند (این موارد باید در ترمینال یا داکر نصب شوند).
 * دستور await main() که در فایل‌های معمولی پایتون باعث خطای Syntax می‌شود، با روش استاندارد app.run() جایگزین شد.
کد کامل و آماده برای فایل bot.py:
import os
import time
import asyncio
import yt_dlp
import requests

from pyrogram import Client, filters
from pyrogram.enums import ParseMode


# ================= تنظیمات =================

BOT_TOKEN = "5098580833:AAEzriKZYpbJOljEwP-8KrOsYlGY-hRyDXA"
BOT_ID = "@YOUR_BOT_ID"

API_ID = 3335796
API_HASH = "138b992a0e672e8346d8439c3f42ea78"


app = Client(
    "MusicBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=8,
)


# ================= سیستم آنتی‌اسپم (Cooldown) =================

user_cooldowns = {}
COOLDOWN_SECONDS = 3


# ================= جستجوی آهنگ (iTunes API) =================

async def search_song(query):

    def _search():
        try:
            data = requests.get(
                "https://itunes.apple.com/search",
                params={
                    "term": query,
                    "media": "music",
                    "limit": 1
                },
                timeout=5
            ).json()

            if data.get("resultCount"):
                item = data["results"][0]
                return (
                    item.get("trackName", "")
                    + " - "
                    + item.get("artistName", "")
                )
        except Exception:
            pass
        return query

    return await asyncio.to_thread(_search)


# ================= دانلود هوشمند و سریع =================

async def download_music(query, user_id):

    output_filename = f"music_{user_id}.m4a"

    def _download():
        t0 = time.time()
        try:
            if os.path.exists(output_filename):
                os.remove(output_filename)

            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]/bestaudio/best',
                'outtmpl': f'music_{user_id}.%(ext)s',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,

                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                    'preferredquality': '0',
                }],

                'extractor_args': {
                    'youtube': {
                        'player_client': ['android'],
                    }
                },

                'concurrent_fragment_downloads': 4,
                'http_chunk_size': 10485760,  # 10MB
                'retries': 3,
                'socket_timeout': 10,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(f"ytsearch1:{query}", download=True)

            if os.path.exists(output_filename):
                print(f"⏱️ دانلود در {time.time() - t0:.2f} ثانیه انجام شد")
                return output_filename

        except Exception as e:
            print(f"❌ Error during download: {e}")

        return None

    return await asyncio.to_thread(_download)


# ================= START =================

@app.on_message(filters.command("start") & filters.private)
async def start(client, message):

    user_id = message.from_user.id
    current_time = time.time()

    if current_time - user_cooldowns.get(user_id, 0) < COOLDOWN_SECONDS:
        return

    user_cooldowns[user_id] = current_time

    name = message.from_user.first_name

    text = f"""
<b>👋 سلام {name} عزیز خوش آمدید❤️

🔮 من ربات کاربردی دانلود آهنگ هستم.

هم اکنون نام آهنگ موردنظرتو برام بفرست.
تا برات فایلشو بفرستم💗😍

🖍️ سازنده ربات :
<a href="https://telegram.me/farshidband">FﾑRSみɨo-BﾑŊo</a></b>
"""

    await message.reply(
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )


# ================= دریافت آهنگ =================

@app.on_message(filters.private & filters.text)
async def music(client, message):

    query = message.text.strip()
    user_id = message.from_user.id

    if query.startswith("/"):
        return

    current_time = time.time()

    if current_time - user_cooldowns.get(user_id, 0) < COOLDOWN_SECONDS:
        return

    user_cooldowns[user_id] = current_time

    status = await message.reply("🔎 در حال پیدا کردن آهنگ...")

    song = await search_song(query)

    await status.edit("⏳ در حال دانلود...")

    file = await download_music(song, user_id)

    if file:
        await message.reply_audio(
            audio=file,
            performer="IR_BOTZ™",
            title=song,
            caption=f"""
🎵 {song}

✅ {BOT_ID}
"""
        )

        try:
            os.remove(file)
        except Exception:
            pass

        await status.delete()

    else:
        await status.edit(
            "❌ متاسفانه خطایی در دانلود پیش آمد. لطفاً دوباره تلاش کنید."
        )


# ================= اجرای پروژه =================

if __name__ == "__main__":
    print("✅ Music Bot is running successfully!")
    app.run()

