import os
import uuid
import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from bson import ObjectId
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatMemberStatus
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web

# ==================== [ CONFIGURATIONS ] ====================
API_ID = int(os.getenv("API_ID", "3335796"))
API_HASH = os.getenv("API_HASH", "138b992a0e672e8346d8439c3f42ea78")
BOT_TOKEN = os.getenv("BOT_TOKEN", "6975247999:AAGr3QKIfax0Tp0GxW38c9mlO1bWKE-cOQU")
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://abirhasan2005:abirhasan@cluster0.i6qzp.mongodb.net/cluster0?retryWrites=true&w=majority")

TEHRAN_TZ = ZoneInfo("Asia/Tehran")
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
MEDIA_CACHE_DIR = "media_cache"
# ============================================================

os.makedirs(MEDIA_CACHE_DIR, exist_ok=True)

bot = Client("Scheduler_Bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["vc_playback_bot"]
channels_col = db["saved_chats"]
scheduled_col = db["scheduled_posts"]

user_states = {}

start_command = """**👋سلام {user_name} 💯❤️**

**🔺به ربات زمان‌بندی پست خوش آمدید!✨**

**از منوی زیر یک کانال/گروه اضافه کنید و سپس برایش پست (متن/عکس/ویدیو) با تاریخ و ساعت دلخواه زمان‌بندی کنید.🌸**


**🖍️ سازنده ربات : [FﾑRSみɨの-BﾑŊの](https://t.me/farshifband)**"""

# ==================== [ WEB SERVER ] ====================

async def health_handler(request):
    return web.Response(text="Scheduler bot is running safely and securely!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8000).start()

# ==================== [ HELPERS ] ====================

async def get_start_keyboard(user_id):
    buttons = [[InlineKeyboardButton("➕ افزودن کانال/گروه", callback_data="add_channel")]]
    cursor = channels_col.find({"user_id": user_id})
    async for doc in cursor:
        cid = doc["chat_id"]
        title = doc["chat_title"]
        buttons.append([InlineKeyboardButton(f"🆔 {title} ({cid})", callback_data=f"manage_{cid}")])
    return InlineKeyboardMarkup(buttons)

def get_manage_keyboard(chat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🕒 افزودن پست زمان‌بندی‌شده", callback_data=f"addpost_{chat_id}")],
        [InlineKeyboardButton("📋 لیست پست‌های زمان‌بندی‌شده", callback_data=f"listposts_{chat_id}")],
        [InlineKeyboardButton("🗑 حذف این چت", callback_data=f"delchat_{chat_id}")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_menu")],
    ])

def format_tehran(dt_utc: datetime) -> str:
    return dt_utc.astimezone(TEHRAN_TZ).strftime("%Y-%m-%d %H:%M")

def content_preview(content: dict) -> str:
    ctype = content.get("type")
    if ctype == "text":
        text = content.get("text", "")
        return text if len(text) <= 40 else text[:40] + "…"
    if ctype == "photo":
        return "🖼 عکس" + (f" - {content.get('caption')[:25]}" if content.get("caption") else "")
    if ctype == "video":
        return "🎬 ویدیو" + (f" - {content.get('caption')[:25]}" if content.get("caption") else "")
    return "نامشخص"

# ==================== [ BOT HANDLERS ] ====================

@bot.on_chat_member_updated()
async def on_bot_admin_status_changed(client: Client, chat_member_updated):
    me = await client.get_me()
    if chat_member_updated.new_chat_member and chat_member_updated.new_chat_member.user.id == me.id:
        if chat_member_updated.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR:
            old_status = chat_member_updated.old_chat_member.status if chat_member_updated.old_chat_member else None
            if old_status != ChatMemberStatus.ADMINISTRATOR:
                try:
                    await client.send_message(
                        chat_id=chat_member_updated.chat.id,
                        text="✅ **ربات با موفقیت در این چت نصب و ادمین شد!**\n\nحالا می‌توانید از پنل خصوصی ربات، پست‌های زمان‌بندی‌شده برای این چت تعریف کنید."
                    )
                except Exception as e:
                    print(f"Error sending welcome message: {e}")

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(_, message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "دوست عزیز"
    user_states[user_id] = None
    kb = await get_start_keyboard(user_id)
    await message.reply_text(
        text=start_command.format(user_name=user_name),
        reply_markup=kb,
        disable_web_page_preview=True
    )

@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(_, message: Message):
    user_id = message.from_user.id
    user_states[user_id] = None
    await message.reply_text("❌ عملیات فعلی لغو شد.")

@bot.on_callback_query(filters.regex("^add_channel$"))
async def add_channel_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    user_states[user_id] = "awaiting_chat_target"
    try:
        await query.message.edit_text(
            "🔗 لطفاً مشخصات چت خود را ارسال کنید.\n\n"
            "می‌توانید آیدی عددی، یوزرنیم عمومی یا لینک کانال را بفرستید.\n"
            "⚠️ توجه: ربات باید قبل از وارد کردن آیدی، در کانال یا گروه شما **ادمین** شده باشد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]])
        )
    except Exception:
        pass
    await query.answer()

@bot.on_callback_query(filters.regex("^manage_"))
async def manage_channel_callback(_, query: CallbackQuery):
    chat_id = query.data.split("_", 1)[1]
    try:
        await query.message.edit_text("⚙️ مدیریت این چت را انتخاب کنید:", reply_markup=get_manage_keyboard(chat_id))
    except Exception:
        pass
    await query.answer()

@bot.on_callback_query(filters.regex("^delchat_"))
async def delchat_callback(_, query: CallbackQuery):
    chat_id = query.data.split("_", 1)[1]
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ بله", callback_data=f"del_yes_{chat_id}"),
            InlineKeyboardButton("❌ خیر", callback_data="del_no")
        ]
    ])
    try:
        await query.message.edit_text("❓ می‌خواهید این چت را حذف کنید؟", reply_markup=keyboard)
    except Exception:
        pass
    await query.answer()

@bot.on_callback_query(filters.regex("^del_yes_"))
async def delete_confirm_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    chat_id = int(query.data.split("_", 2)[2])
    await channels_col.delete_one({"user_id": user_id, "chat_id": chat_id})
    await scheduled_col.delete_many({"user_id": user_id, "chat_id": chat_id})
    await query.answer("🗑 با موفقیت حذف شد")
    kb = await get_start_keyboard(user_id)
    try:
        await query.message.edit_text(text=start_command.format(user_name=query.from_user.first_name or "دوست عزیز"), reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        pass

@bot.on_callback_query(filters.regex("^del_no$"))
async def delete_cancel_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    await query.answer("لغو شد")
    kb = await get_start_keyboard(user_id)
    try:
        await query.message.edit_text(text=start_command.format(user_name=query.from_user.first_name or "دوست عزیز"), reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        pass

@bot.on_callback_query(filters.regex("^back_to_menu$"))
async def back_to_menu_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    user_states[user_id] = None
    kb = await get_start_keyboard(user_id)
    try:
        await query.message.edit_text(text=start_command.format(user_name=query.from_user.first_name or "دوست عزیز"), reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        pass
    await query.answer()

@bot.on_callback_query(filters.regex("^addpost_"))
async def addpost_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    chat_id = int(query.data.split("_", 1)[1])
    user_states[user_id] = {"stage": "awaiting_content", "chat_id": chat_id}
    try:
        await query.message.edit_text(
            "✏️ محتوای پست را ارسال کنید (متن، عکس یا ویدیو - می‌توانید کپشن هم بگذارید).\n\n"
            "برای انصراف /cancel را بفرستید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 انصراف", callback_data="back_to_menu")]])
        )
    except Exception:
        pass
    await query.answer()

@bot.on_callback_query(filters.regex("^listposts_"))
async def listposts_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    chat_id = int(query.data.split("_", 1)[1])
    posts = []
    cursor = scheduled_col.find({"user_id": user_id, "chat_id": chat_id, "sent": False}).sort("send_at", 1)
    async for post in cursor:
        posts.append(post)

    if not posts:
        buttons = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"manage_{chat_id}")]]
        try:
            await query.message.edit_text("📭 هیچ پست زمان‌بندی‌شده‌ای برای این چت نیست.", reply_markup=InlineKeyboardMarkup(buttons))
        except Exception:
            pass
        await query.answer()
        return

    buttons = []
    lines = ["📋 **پست‌های زمان‌بندی‌شده:**\n"]
    for post in posts:
        when = format_tehran(post["send_at"])
        preview = content_preview(post["content"])
        lines.append(f"🕒 {when} — {preview}")
        buttons.append([InlineKeyboardButton(f"❌ حذف ({when})", callback_data=f"rmpost_{post['_id']}")])
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"manage_{chat_id}")])

    try:
        await query.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass
    await query.answer()

@bot.on_callback_query(filters.regex("^rmpost_"))
async def rmpost_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    post_id = query.data.replace("rmpost_", "")
    post = await scheduled_col.find_one({"_id": ObjectId(post_id), "user_id": user_id})
    if not post:
        await query.answer("این پست یافت نشد یا متعلق به شما نیست.", show_alert=True)
        return
    chat_id = post["chat_id"]

    local_path = post.get("content", {}).get("local_path")
    if local_path and os.path.exists(local_path):
        try:
            os.remove(local_path)
        except Exception:
            pass

    await scheduled_col.delete_one({"_id": ObjectId(post_id), "user_id": user_id})
    await query.answer("🗑 پست حذف شد")
    query.data = f"listposts_{chat_id}"
    await listposts_callback(_, query)

@bot.on_callback_query(filters.regex("^editpost_"))
async def editpost_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    post_id = query.data.replace("editpost_", "")
    
    post = await scheduled_col.find_one({"_id": ObjectId(post_id), "user_id": user_id})
    if not post:
        await query.answer("این پست یافت نشد یا دسترسی غیرمجاز است.", show_alert=True)
        return
    
    user_states[user_id] = {"stage": "awaiting_edit_content", "post_id": post_id}
    
    try:
        await query.message.edit_text(
            f"✏️ لطفاً متن اصلاحی جدید را برای پست با شناسه `{post_id}` ارسال کنید:\n\n"
            "برای انصراف /cancel را بفرستید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_post_{post_id}")]])
        )
    except Exception:
        pass
    await query.answer()

@bot.on_callback_query(filters.regex("^back_post_"))
async def back_post_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    post_id = query.data.replace("back_post_", "")
    
    post = await scheduled_col.find_one({"_id": ObjectId(post_id), "user_id": user_id})
    if not post:
        await query.answer("یافت نشد.", show_alert=True)
        return

    user_states[user_id] = None
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖌 ویرایش پست", callback_data=f"editpost_{post_id}"),
            InlineKeyboardButton("🗑 حذف پست", callback_data=f"panel_del_{post_id}")
        ]
    ])
    try:
        await query.message.edit_text(
            f"✅ مدیریت پست\n\n🆔 شناسه پست: `{post_id}`",
            reply_markup=kb
        )
    except Exception:
        pass
    await query.answer()

@bot.on_callback_query(filters.regex("^panel_del_"))
async def panel_del_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    post_id = query.data.replace("panel_del_", "")
    
    post = await scheduled_col.find_one({"_id": ObjectId(post_id), "user_id": user_id})
    if not post:
        await query.answer("یافت نشد.", show_alert=True)
        return

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("بله ✅", callback_data=f"panel_yes_{post_id}"),
            InlineKeyboardButton("لغو ✖️", callback_data=f"panel_cancel_{post_id}")
        ]
    ])
    try:
        await query.message.edit_text("❓ آیا مطمئن هستید پست حذف شود؟", reply_markup=kb)
    except Exception:
        pass
    await query.answer()

@bot.on_callback_query(filters.regex("^panel_cancel_"))
async def panel_cancel_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    post_id = query.data.replace("panel_cancel_", "")
    
    post = await scheduled_col.find_one({"_id": ObjectId(post_id), "user_id": user_id})
    if not post:
        await query.answer("یافت نشد.", show_alert=True)
        return

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖌 ویرایش پست", callback_data=f"editpost_{post_id}"),
            InlineKeyboardButton("🗑 حذف پست", callback_data=f"panel_del_{post_id}")
        ]
    ])
    try:
        await query.message.edit_text(
            f"✅ مدیریت پست\n\n🆔 شناسه پست: `{post_id}`",
            reply_markup=kb
        )
    except Exception:
        pass
    await query.answer()

@bot.on_callback_query(filters.regex("^panel_yes_"))
async def panel_yes_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    post_id = query.data.replace("panel_yes_", "")
    
    post = await scheduled_col.find_one({"_id": ObjectId(post_id), "user_id": user_id})
    
    if post:
        chat_id = post.get("chat_id")
        sent_msg_id = post.get("sent_message_id")
        if chat_id and sent_msg_id:
            try:
                await bot.delete_messages(chat_id, sent_msg_id)
            except Exception as e:
                print(f"Error deleting message from channel: {e}")
        
        await scheduled_col.delete_one({"_id": ObjectId(post_id), "user_id": user_id})
    
    await query.answer("✅ پست موردنظر با موفقیت از کانال حذف شد.", show_alert=False)
    try:
        await query.message.edit_text("🗑 این پست حذف شده است.")
    except Exception:
        pass

@bot.on_message(filters.private & (filters.text | filters.photo | filters.video) & ~filters.command(["start", "cancel"]))
async def stateful_input_handler(_, message: Message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not state:
        return

    if isinstance(state, dict) and state.get("stage") == "awaiting_edit_content":
        if not message.text:
            await message.reply_text("لطفاً متن اصلاحی را به صورت متن ارسال کنید.")
            return

        post_id = state["post_id"]
        new_text = message.text.strip()
        
        post = await scheduled_col.find_one({"_id": ObjectId(post_id), "user_id": user_id})
        if not post:
            await message.reply_text("❌ پست مورد نظر یافت نشد یا متعلق به شما نیست.")
            user_states[user_id] = None
            return

        chat_id = post.get("chat_id")
        sent_msg_id = post.get("sent_message_id")
        ctype = post.get("content", {}).get("type")

        try:
            if chat_id and sent_msg_id:
                if ctype == "text":
                    await bot.edit_message_text(chat_id=chat_id, message_id=sent_msg_id, text=new_text)
                    await scheduled_col.update_one({"_id": ObjectId(post_id), "user_id": user_id}, {"$set": {"content.text": new_text}})
                else:
                    await bot.edit_message_caption(chat_id=chat_id, message_id=sent_msg_id, caption=new_text)
                    await scheduled_col.update_one({"_id": ObjectId(post_id), "user_id": user_id}, {"$set": {"content.caption": new_text}})

            user_states[user_id] = None
            
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🖌 ویرایش پست", callback_data=f"editpost_{post_id}"),
                    InlineKeyboardButton("🗑 حذف پست", callback_data=f"panel_del_{post_id}")
                ]
            ])
            await message.reply_text(
                f"✅ با موفقیت اصلاح شد.\n\n🆔 شناسه پست: `{post_id}`",
                reply_markup=kb
            )
        except Exception as e:
            await message.reply_text(f"❌ خطا در ویرایش پست: {e}")
        return

    if state == "awaiting_chat_target":
        if not message.text:
            await message.reply_text("لطفاً آیدی/یوزرنیم/لینک را به صورت متن ارسال کنید.")
            return

        raw_input = message.text.strip()
        if "t.me/" in raw_input and "+" not in raw_input:
            raw_input = raw_input.split("t.me/")[-1].replace("@", "")

        status_checking = await message.reply_text("🔍 در حال بررسی اعتبار شناسه و دسترسی ادمین...")
        try:
            if raw_input.lstrip('-').isdigit():
                raw_input = int(raw_input)
                
            chat = await bot.get_chat(raw_input)
            chat_id = chat.id
            chat_title = chat.title or chat.first_name or str(chat.id)

            await channels_col.update_one(
                {"user_id": user_id, "chat_id": chat_id},
                {"$set": {"chat_title": chat_title}},
                upsert=True
            )
            user_states[user_id] = None

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🆔 {chat_title} ({chat_id})", callback_data=f"manage_{chat_id}")],
                [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_menu")]
            ])
            await status_checking.delete()
            await message.reply_text(f"✅ چت شما اضافه شد.\n\nنام: **{chat_title}**", reply_markup=keyboard)
        except Exception as e:
            await status_checking.edit_text(
                f"❌ خطا در یافتن چت: {e}\n\n"
                "**راه حل:** مطمئن شوید ربات در گروه یا کانال مورد نظر ادمین است و سپس دوباره شناسه را بفرستید."
            )
        return

    if isinstance(state, dict) and state.get("stage") == "awaiting_content":
        chat_id = state["chat_id"]

        unique_prefix = str(uuid.uuid4())
        if message.photo:
            local_path = await message.download(file_name=os.path.join(MEDIA_CACHE_DIR, f"{unique_prefix}.jpg"))
            content = {"type": "photo", "local_path": local_path, "caption": message.caption or ""}
        elif message.video:
            local_path = await message.download(file_name=os.path.join(MEDIA_CACHE_DIR, f"{unique_prefix}.mp4"))
            content = {"type": "video", "local_path": local_path, "caption": message.caption or ""}
        elif message.text:
            content = {"type": "text", "text": message.text}
        else:
            await message.reply_text("❌ فقط متن، عکس یا ویدیو پشتیبانی می‌شود.")
            return

        user_states[user_id] = {"stage": "awaiting_datetime", "chat_id": chat_id, "content": content}
        now_tehran = datetime.now(TEHRAN_TZ).strftime(DATETIME_FORMAT)
        await message.reply_text(
            "🕒 حالا تاریخ و ساعت ارسال را به وقت تهران و با این فرمت بفرستید:\n"
            "`YYYY-MM-DD HH:MM`\n\n"
            f"مثال: `{now_tehran}`\n\nبرای انصراف /cancel را بفرستید."
        )
        return

    if isinstance(state, dict) and state.get("stage") == "awaiting_datetime":
        if not message.text:
            await message.reply_text("لطفاً تاریخ و ساعت را به صورت متن ارسال کنید.")
            return

        chat_id = state["chat_id"]
        content = state["content"]
        text = message.text.strip()

        try:
            naive_dt = datetime.strptime(text, DATETIME_FORMAT)
            send_at_tehran = naive_dt.replace(tzinfo=TEHRAN_TZ)
            send_at_utc = send_at_tehran.astimezone(timezone.utc)
        except ValueError:
            await message.reply_text(
                f"❌ فرمت نامعتبر است. لطفاً دقیقاً مثل این بفرستید:\n`{DATETIME_FORMAT}`\nمثال: `2026-09-05 21:30`"
            )
            return

        if send_at_utc <= datetime.now(timezone.utc):
            await message.reply_text("❌ زمان وارد شده در گذشته است. لطفاً یک زمان آینده وارد کنید.")
            return

        await scheduled_col.insert_one({
            "user_id": user_id,
            "chat_id": chat_id,
            "content": content,
            "send_at": send_at_utc,
            "sent": False,
            "created_at": datetime.now(timezone.utc),
        })
        user_states[user_id] = None

        await message.reply_text(
            f"✅ پست با موفقیت زمان‌بندی شد.\n"
            f"🕒 زمان ارسال (تهران): **{format_tehran(send_at_utc)}**\n"
            f"📌 پیش‌نمایش: {content_preview(content)}"
        )
        return

async def send_scheduled_post(post: dict):
    chat_id = post["chat_id"]
    content = post["content"]
    ctype = content.get("type")

    sent_msg = None
    if ctype == "text":
        sent_msg = await bot.send_message(chat_id, content["text"])
    elif ctype == "photo":
        sent_msg = await bot.send_photo(chat_id, content["local_path"], caption=content.get("caption") or None)
    elif ctype == "video":
        sent_msg = await bot.send_video(chat_id, content["local_path"], caption=content.get("caption") or None)
    return sent_msg

async def scheduler_loop():
    while True:
        try:
            now = datetime.now(timezone.utc)
            while True:
                post = await scheduled_col.find_one_and_update(
                    {"sent": False, "send_at": {"$lte": now}},
                    {"$set": {"sent": True}}
                )
                if not post:
                    break

                try:
                    sent_msg = await send_scheduled_post(post)
                    sent_msg_id = sent_msg.id if sent_msg else None
                    
                    await scheduled_col.update_one(
                        {"_id": post["_id"]}, 
                        {"$set": {"sent_message_id": sent_msg_id}}
                    )
                    
                    user_id = post["user_id"]
                    post_id_str = str(post["_id"])
                    kb = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🖌 ویرایش پست", callback_data=f"editpost_{post_id_str}"),
                            InlineKeyboardButton("🗑 حذف پست", callback_data=f"panel_del_{post_id_str}")
                        ]
                    ])
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"✅ باموفقیت ارسال شد.\n\n🆔 شناسه پست: `{post_id_str}`",
                            reply_markup=kb
                        )
                    except Exception as ex:
                        print(f"Error sending success notification to user: {ex}")

                    print(f"✅ Sent scheduled post {post['_id']} to {post['chat_id']}")
                except Exception as e:
                    print(f"❌ Failed to send scheduled post {post['_id']}: {e}")
                    await scheduled_col.update_one({"_id": post["_id"]}, {"$set": {"error": str(e)}})
                finally:
                    local_path = post.get("content", {}).get("local_path")
                    if local_path and os.path.exists(local_path):
                        try:
                            os.remove(local_path)
                        except Exception:
                            pass
        except Exception as e:
            print(f"❌ Scheduler loop error: {e}")

        await asyncio.sleep(10)

async def main():
    await start_web_server()
    await bot.start()

    asyncio.create_task(scheduler_loop())
    print("🚀 Safe Multi-User Scheduler bot online!")
    await idle()
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
