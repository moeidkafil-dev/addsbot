import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
DB_FILE = "media_db.json"

CHANNELS = [
    "@channel1",
    "@channel2",
    "@channel3",
    "@channel4",
    "@channel5",
]

if os.path.exists(DB_FILE):
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            media_db = json.load(f)
        except json.JSONDecodeError:
            media_db = {}
else:
    media_db = {}

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(media_db, f, ensure_ascii=False, indent=2)

pending_requests = {}

def is_admin(user_id: int) -> bool:
    return ADMIN_ID != 0 and user_id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! ✌️\n"
        "برای دریافت فایل، شماره‌اش را بزن: /get 1\n"
        "برای دیدن کانال‌ها: /channels\n"
        "برای گرفتن آیدی عددی خودت: /whoami"
    )

async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your numeric user id: {update.effective_user.id}")

async def channels_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not CHANNELS:
        await update.message.reply_text("هیچ کانالی تنظیم نشده.")
        return
    buttons = [[InlineKeyboardButton(ch, url=f"https://t.me/{ch.strip('@')}")] for ch in CHANNELS]
    await update.message.reply_text(
        "برای استفاده باید در همه کانال‌های زیر عضو باشید:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def get_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("لطفاً شماره فایل را وارد کن. مثال: /get 2")
        return
    media_id = context.args[0].strip()
    if media_id not in media_db:
        await update.message.reply_text("⛔ چنین شماره‌ای ذخیره نشده.")
        return
    user_id = update.effective_user.id
    pending_requests[user_id] = media_id

    buttons = [[InlineKeyboardButton(f"عضویت در {ch}", url=f"https://t.me/{ch.strip('@')}")] for ch in CHANNELS]
    buttons.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_subs")])

    await update.message.reply_text(
        "برای دریافت فایل، اول در همه کانال‌ها عضو شو و بعد روی «عضو شدم» بزن.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def save_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    if not context.args:
        await update.message.reply_text("باید شماره فایل را بدهی. مثال: همراه فایل بفرست: /save 3")
        return
    media_id = context.args[0].strip()
    file_id, file_type = None, None

    if update.message.animation:
        file_id = update.message.animation.file_id
        file_type = "animation"
    elif update.message.video:
        file_id = update.message.video.file_id
        file_type = "video"
    elif update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_type = "photo"

    if not file_id:
        await update.message.reply_text("❌ باید همراه دستور، ویدیو/گیف/عکس ارسال کنی.")
        return

    media_db[media_id] = {"file_id": file_id, "type": file_type}
    save_db()
    await update.message.reply_text(f"✅ فایل با شماره {media_id} ذخیره شد. نوع: {file_type}")

async def check_subs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    for ch in CHANNELS:
        try:
            member = await context.bot.get_chat_member(ch, user_id)
            if member.status not in ("member", "administrator", "creator"):
                await query.edit_message_text("⛔ باید در همه کانال‌ها عضو باشی. بعد دوباره امتحان کن.")
                return
        except Exception:
            await query.edit_message_text(f"❌ خطا در بررسی عضویت در {ch}. کانال باید پابلیک باشد و من عضو باشم.")
            return

    if user_id in pending_requests:
        media_id = pending_requests.pop(user_id)
        info = media_db.get(media_id)
        if not info:
            await query.edit_message_text("⛔ فایل مورد نظر پیدا نشد.")
            return
        await query.edit_message_text("✅ تایید شد! در حال ارسال فایل...")
        if info["type"] == "animation":
            await context.bot.send_animation(chat_id=user_id, animation=info["file_id"])
        elif info["type"] == "video":
            await context.bot.send_video(chat_id=user_id, video=info["file_id"])
        elif info["type"] == "photo":
            await context.bot.send_photo(chat_id=user_id, photo=info["file_id"])
        else:
            await context.bot.send_message(chat_id=user_id, text="Unknown media type.")
    else:
        await query.edit_message_text("درخواستی برای فایل ثبت نشده.")

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN env var is not set.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("channels", channels_cmd))
    app.add_handler(CommandHandler("get", get_media))
    app.add_handler(CommandHandler("save", save_media))
    app.add_handler(CallbackQueryHandler(check_subs, pattern="^check_subs$"))
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
