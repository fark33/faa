import os
import re
import time
import asyncio
import yt_dlp
import requests

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from shazamio import Shazam


# ================= تنظیمات =================

BOT_TOKEN = os.environ.get(
    "BOT_TOKEN",
    "6964975788:AAG2K-6mucoVOgNTrb3YH4yON4K5Y6vrR_s"
)

BOT_ID = "@ir_ahangdlbot"

API_ID = 3335796
API_HASH = "138b992a0e672e8346d8439c3f42ea78"


app = Client(
    "MusicBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=8,
)

shazam = Shazam()


# ================= سیستم آنتی‌اسپم =================

user_cooldowns = {}
COOLDOWN_SECONDS = 3


# ================= الگوی تشخیص لینک اینستاگرام =================

INSTAGRAM_REGEX = re.compile(
    r'(https?://)?(www\.)?instagram\.com/(reel|reels|p|tv)/[A-Za-z0-9_\-]+'
)

VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/x-matroska",
    "video/quicktime"
}


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

        except Exception as e:
            print(f"❌ iTunes error: {e}")

        return query

    return await asyncio.to_thread(_search)


# ================= دانلود موزیک از یوتیوب =================

async def download_music(query, user_id):

    output_filename = f"music_{user_id}.m4a"

    def _download():

        t0 = time.time()

        try:

            if os.path.exists(output_filename):
                os.remove(output_filename)

            base_opts = {
                "format": (
                    "bestaudio[ext=m4a]/"
                    "bestaudio[acodec^=mp4a]/"
                    "bestaudio/best"
                ),

                "outtmpl": f"music_{user_id}.%(ext)s",

                "noplaylist": True,

                "quiet": True,

                "no_warnings": True,

                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "m4a",
                        "preferredquality": "0",
                    }
                ],

                "concurrent_fragment_downloads": 4,

                "http_chunk_size": 10485760,

                "retries": 3,

                "socket_timeout": 10,
            }

            # تلاش با کلاینت‌های مختلف
            for client_name in (
                ["android"],
                ["ios"],
                ["tv"]
            ):

                try:

                    opts = {
                        **base_opts,
                        "extractor_args": {
                            "youtube": {
                                "player_client": client_name
                            }
                        }
                    }

                    with yt_dlp.YoutubeDL(opts) as ydl:

                        ydl.extract_info(
                            f"ytsearch1:{query}",
                            download=True
                        )

                    if os.path.exists(output_filename):

                        print(
                            f"⏱️ دانلود موزیک در "
                            f"{time.time() - t0:.2f} ثانیه "
                            f"({client_name})"
                        )

                        return output_filename

                except Exception as e:

                    print(
                        f"⚠️ کلاینت {client_name} جواب نداد: {e}"
                    )

                    continue

            # تلاش با کوکی
            if os.path.exists("cookies.txt"):

                try:

                    opts = {
                        **base_opts,
                        "cookiefile": "cookies.txt"
                    }

                    with yt_dlp.YoutubeDL(opts) as ydl:

                        ydl.extract_info(
                            f"ytsearch1:{query}",
                            download=True
                        )

                    if os.path.exists(output_filename):

                        print(
                            f"⏱️ دانلود موزیک در "
                            f"{time.time() - t0:.2f} ثانیه "
                            f"(با کوکی)"
                        )

                        return output_filename

                except Exception as e:

                    print(
                        f"⚠️ دانلود با کوکی هم جواب نداد: {e}"
                    )

        except Exception as e:

            print(
                f"❌ Error during download: {e}"
            )

        return None

    return await asyncio.to_thread(_download)


# ================= دانلود ریلز اینستاگرام =================

async def download_instagram(url, user_id):

    output_filename = f"reel_{user_id}.mp4"

    def _download():

        t0 = time.time()

        try:

            if os.path.exists(output_filename):
                os.remove(output_filename)

            ydl_opts = {

                "format": "best[ext=mp4]/best",

                "outtmpl": f"reel_{user_id}.%(ext)s",

                "noplaylist": True,

                "quiet": True,

                "no_warnings": True,

                "retries": 3,

                "socket_timeout": 10,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                info = ydl.extract_info(
                    url,
                    download=True
                )

            if os.path.exists(output_filename):

                print(
                    f"⏱️ دانلود ریلز در "
                    f"{time.time() - t0:.2f} ثانیه انجام شد"
                )

                caption = (
                    info.get("description") or ""
                ).strip()

                return output_filename, caption

        except Exception as e:

            print(
                f"❌ Error downloading instagram reel: {e}"
            )

        return None, None

    return await asyncio.to_thread(_download)


# ================= استخراج تکه کوتاه صدا =================

async def extract_audio_sample(
    video_path,
    user_id,
    duration=25
):

    audio_path = f"sample_{user_id}.m4a"

    def _extract():

        try:

            if os.path.exists(audio_path):
                os.remove(audio_path)

            cmd = (
                f'ffmpeg -y '
                f'-i "{video_path}" '
                f'-t {duration} '
                f'-vn '
                f'-acodec aac '
                f'-ar 44100 '
                f'-ac 1 '
                f'"{audio_path}" '
                f'-loglevel error'
            )

            ret = os.system(cmd)

            print(
                f"🔧 ffmpeg exit code: {ret}"
            )

            if os.path.exists(audio_path):
                return audio_path

        except Exception as e:

            print(
                f"❌ Error extracting audio sample: {e}"
            )

        return None

    return await asyncio.to_thread(_extract)


# ================= تشخیص آهنگ با Shazam =================

async def recognize_song(audio_path):

    try:

        result = await shazam.recognize(
            audio_path
        )

        track = result.get("track")

        if track:

            title = track.get(
                "title",
                ""
            )

            subtitle = track.get(
                "subtitle",
                ""
            )

            if title:

                return (
                    f"{title} - {subtitle}"
                ).strip(" -")

    except Exception as e:

        print(
            f"❌ Shazam error: {e}"
        )

    return None


# ================= START =================

@app.on_message(
    filters.command("start") & filters.private
)
async def start(client, message):

    user_id = message.from_user.id

    current_time = time.time()

    if (
        current_time
        - user_cooldowns.get(user_id, 0)
        < COOLDOWN_SECONDS
    ):
        return

    user_cooldowns[user_id] = current_time

    name = message.from_user.first_name

    text = f"""
<b>👋 سلام {name} عزیز خوش آمدید❤️

🔮 من ربات کاربردی دانلود آهنگ هستم.

هم اکنون نام آهنگ موردنظرتو، لینک ریلز اینستاگرام، یا خود ویدیو رو برام بفرست.
تا برات فایلشو بفرستم💗😍

🖍️ سازنده ربات :
<a href="https://telegram.me/farshidband">FﾑRSみɨo-BﾑŊo</a></b>
"""

    await message.reply(
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )


# ================= تشخیص آهنگ و ارسال =================

async def recognize_and_send(
    message,
    video_path,
    user_id,
    status
):

    sample_path = await extract_audio_sample(
        video_path,
        user_id
    )

    song_name = (
        await recognize_song(sample_path)
        if sample_path
        else None
    )

    print(
        f"🔎 song_name = {song_name}"
    )

    if (
        sample_path
        and os.path.exists(sample_path)
    ):

        try:
            os.remove(sample_path)
        except Exception:
            pass

    if not song_name:

        await status.edit(
            "❌ متاسفانه نتونستم آهنگ این ویدیو رو تشخیص بدم."
        )

        return

    await status.edit(
        f"🎧 آهنگ شناسایی شد: {song_name}\n"
        f"⏳ در حال دانلود..."
    )

    song = await search_song(
        song_name
    )

    file = await download_music(
        song,
        user_id
    )

    if file:

        await message.reply_audio(

            audio=file,

            performer="IR_BOTZ™",

            title=song,

            caption=(
                f"🎵 {song}\n\n"
                f"✅ {BOT_ID}"
            )
        )

        try:
            os.remove(file)
        except Exception:
            pass

        await status.delete()

    else:

        await status.edit(
            f"🎧 آهنگ شناسایی شد: {song_name}\n"
            f"❌ اما دانلودش موفق نبود."
        )


# ================= پردازش ریلز اینستاگرام =================

async def handle_instagram_reel(
    message,
    url
):

    user_id = message.from_user.id

    status = await message.reply(
        "📥 در حال دانلود ریلز..."
    )

    try:

        video_path, caption = (
            await download_instagram(
                url,
                user_id
            )
        )

        if not video_path:

            await status.edit(
                "❌ نتونستم ریلز رو دانلود کنم. لینک رو چک کن."
            )

            return

        await status.edit(
            "📤 در حال ارسال ویدیو و تشخیص آهنگ..."
        )

        send_video_task = asyncio.create_task(

            message.reply_video(

                video=video_path,

                caption=(
                    f"{caption[:900]}\n\n"
                    f"✅ {BOT_ID}"
                    if caption
                    else f"✅ {BOT_ID}"
                ),
            )
        )

        await recognize_and_send(
            message,
            video_path,
            user_id,
            status
        )

        await send_video_task

        if os.path.exists(video_path):

            os.remove(video_path)

    except Exception as e:

        print(
            f"❌ خطا در handle_instagram_reel: {e}"
        )

        try:

            await status.edit(
                f"❌ خطا: {e}"
            )

        except Exception:
            pass


# ================= پردازش ویدیوی ارسالی =================

async def handle_uploaded_video(
    client,
    message
):

    user_id = message.from_user.id

    status = await message.reply(
        "📥 در حال دریافت ویدیو..."
    )

    video_path = None

    try:

        t0 = time.time()

        video_path = await message.download(
            file_name=f"upload_{user_id}_"
        )

        print(
            f"⏱️ دریافت ویدیو در "
            f"{time.time() - t0:.2f} ثانیه "
            f"-> {video_path}"
        )

        if (
            not video_path
            or not os.path.exists(video_path)
        ):

            await status.edit(
                "❌ نتونستم ویدیو رو دریافت کنم."
            )

            return

        await status.edit(
            "🎧 در حال تشخیص آهنگ..."
        )

        await recognize_and_send(
            message,
            video_path,
            user_id,
            status
        )

    except Exception as e:

        print(
            f"❌ خطای کامل در handle_uploaded_video: {e}"
        )

        try:

            await status.edit(
                f"❌ خطا: {e}"
            )

        except Exception:
            pass

    finally:

        if (
            video_path
            and os.path.exists(video_path)
        ):

            try:
                os.remove(video_path)
            except Exception:
                pass


# ================= دریافت پیام متنی =================

@app.on_message(
    filters.private & filters.text
)
async def music(client, message):

    query = message.text.strip()

    user_id = message.from_user.id

    if query.startswith("/"):
        return

    current_time = time.time()

    if (
        current_time
        - user_cooldowns.get(user_id, 0)
        < COOLDOWN_SECONDS
    ):
        return

    user_cooldowns[user_id] = current_time

    # بررسی لینک اینستاگرام

    if INSTAGRAM_REGEX.search(query):

        await handle_instagram_reel(
            message,
            query
        )

        return

    # جستجوی آهنگ

    status = await message.reply(
        "🔎 در حال پیدا کردن آهنگ..."
    )

    try:

        song = await search_song(
            query
        )

        await status.edit(
            "⏳ در حال دانلود..."
        )

        file = await download_music(
            song,
            user_id
        )

        if file:

            await message.reply_audio(

                audio=file,

                performer="IR_BOTZ™",

                title=song,

                caption=(
                    f"🎵 {song}\n\n"
                    f"✅ {BOT_ID}"
                )
            )

            try:
                os.remove(file)
            except Exception:
                pass

            await status.delete()

        else:

            await status.edit(
                "❌ متاسفانه خطایی در دانلود پیش آمد. "
                "لطفاً دوباره تلاش کنید."
            )

    except Exception as e:

        print(
            f"❌ music handler error: {e}"
        )

        try:

            await status.edit(
                f"❌ خطا: {e}"
            )

        except Exception:
            pass


# ================= دریافت ویدیو =================

@app.on_message(
    filters.private
    & (filters.video | filters.document)
)
async def video_handler(
    client,
    message
):

    print(
        "📩 پیام ویدیویی/سند دریافت شد"
    )

    user_id = message.from_user.id

    current_time = time.time()

    if (
        current_time
        - user_cooldowns.get(user_id, 0)
        < COOLDOWN_SECONDS
    ):

        print(
            "⏳ در کول‌داون، رد شد"
        )

        return

    # بررسی document

    if message.document:

        mime = (
            message.document.mime_type
            or ""
        ).lower()

        file_name = (
            message.document.file_name
            or ""
        ).lower()

        is_video = (
            mime in VIDEO_MIME_TYPES
            or file_name.endswith(
                (
                    ".mp4",
                    ".mkv",
                    ".mov"
                )
            )
        )

        print(
            f"📄 document "
            f"mime={mime} "
            f"file_name={file_name} "
            f"is_video={is_video}"
        )

        if not is_video:
            return

    user_cooldowns[user_id] = current_time

    try:

        await handle_uploaded_video(
            client,
            message
        )

    except Exception as e:

        print(
            f"❌ خطا در video_handler: {e}"
        )

        try:

            await message.reply(
                f"❌ خطایی پیش اومد: {e}"
            )

        except Exception:
            pass


# ================= اجرای پروژه =================

if __name__ == "__main__":

    print(
        "🚀 Starting Music Bot..."
    )

    print(
        "✅ Music Bot is running successfully!"
    )

    app.run()
