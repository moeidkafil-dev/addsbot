import os
import json
import logging
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# ---------- تنظیمات ----------
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN در متغیرهای محیطی تنظیم نشده است.")

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))  # عددیِ ادمین (اختیاری ولی بهتره)
DB_FILE = "media_db.json"

# آیدیِ یوزرنیم کانال‌ها (Public). ربات باید داخل این کانال‌ها ادمین یا حداقل عضو باشد.
CHANNELS = [
    "@Araksemnan1",
    "@Araksemnan1",
    "@Araksemnan1",
    "@Araksemnan1",
    "@Araksemnan1",
]

# ---------- لاگ ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("GateBot")

# ---------- دیتابیس ساده روی فایل JSON ----------
if os.path.exists(DB_FILE):
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            media_db: Dict[str, Dict[str, Any]] = json.load(f)
    except Exception:
        media_db = {}
else:
    media_db = {}

def save_db() -> None:
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(media_db, f, ensure_ascii=False, indent=2)

# درخواست‌های در حال انتظار (user_id -> media_id)
pending_requests: Dict[int, str] = {}


def is_admin(user_id: int) -> bool:
    return ADMIN_ID != 0 and user_id == ADMIN_ID


# ---------- دستورات ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام ✌️\n"
        "برای دریافت فایل، کُدش رو بزن: مثال: /get 12\n"
        "برای دیدن کانال‌ها: /channels\n"
        "گرفتن آیدی عددی: /whoami\n"
        "افزودن فایل (ادمین): همراه فایل بزن /save 12"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - شروع\n"
        "/help - راهنما\n"
        "/channels - لیست کانال‌ها برای عضویت اجباری\n"
        "/whoami - نمایش آیدی عددی شما\n"
        "/get <کُد> - دریافت فایل با کُد\n"
        "/save <کُد> - (ادمین) ذخیره فایل همراه پیام"
    )

async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Numeric user id: `{update.effective_user.id}`", parse_mode="Markdown")

async def channels_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not CHANNELS:
        await update.message.reply_text("هیچ کانالی تنظیم نشده.")
        return

    buttons = [[InlineKeyboardButton(ch, url=f"https://t.me/{ch.lstrip('@')}")] for ch in CHANNELS]
    await update.message.reply_text(
        "برای استفاده باید در همه‌ی کانال‌های زیر عضو باشید:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def get_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("لطفاً کُد فایل را وارد کن. مثال: /get 2")
        return

    media_id = context.args[0].strip()
    info = media_db.get(media_id)
    if not info:
        await update.message.reply_text("⛔ چنین کُدی ذخیره نشده.")
        return

    user_id = update.effective_user.id
    pending_requests[user_id] = media_id

    # دکمه‌های عضویت + دکمه بررسی
    buttons = [[InlineKeyboardButton(f"عضویت در {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in CHANNELS]
    buttons.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_subs")])

    await update.message.reply_text(
        "برای دریافت فایل، اول در همه کانال‌ها عضو شو و بعد «عضو شدم» رو بزن.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def save_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        # برای امنیت چیزی نگیم
        return

    if not context.args:
        await update.message.reply_text("باید کُد فایل را بدهی. مثال: همراه فایل بفرست: /save 3")
        return
    media_id = context.args[0].strip()

    file_id, file_type = None, None
    msg = update.message

    if msg.animation:
        file_id = msg.animation.file_id
        file_type = "animation"
    elif msg.video:
        file_id = msg.video.file_id
        file_type = "video"
    elif msg.photo:
        file_id = msg.photo[-1].file_id
        file_type = "photo"
    else:
        await update.message.reply_text("❌ باید همراه دستور، ویدیو/گیف/عکس ارسال کنی.")
        return

    media_db[media_id] = {"file_id": file_id, "type": file_type}
    save_db()
    await update.message.reply_text(f"✅ فایل با کُد {media_id} ذخیره شد. نوع: {file_type}")

async def check_subs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # بررسی عضویت همه کانال‌ها
    for ch in CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status not in ("member", "administrator", "creator"):
                await query.edit_message_text("⛔ باید در همه کانال‌ها عضو باشی. بعد دوباره امتحان کن.")
                return
        except Exception as e:
            logger.warning("Membership check error on %s: %s", ch, e)
            await query.edit_message_text(
                f"❌ خطا در بررسی عضویت در {ch}. کانال باید پابلیک باشد و ربات داخل آن عضو باشد."
            )
            return

    # تحویل فایل
    media_id = pending_requests.pop(user_id, None)
    if not media_id:
        await query.edit_message_text("درخواستی برای فایل ثبت نشده.")
        return

    info = media_db.get(media_id)
    if not info:
        await query.edit_message_text("⛔ فایل مورد نظر پیدا نشد.")
        return

    await query.edit_message_text("✅ تایید شد! در حال ارسال فایل...")

    try:
        if info["type"] == "animation":
            await context.bot.send_animation(chat_id=user_id, animation=info["file_id"])
        elif info["type"] == "video":
            await context.bot.send_video(chat_id=user_id, video=info["file_id"])
        elif info["type"] == "photo":
            await context.bot.send_photo(chat_id=user_id, photo=info["file_id"])
        else:
            await context.bot.send_message(chat_id=user_id, text="Unknown media type.")
    except Exception as e:
        logger.exception("Send media error: %s", e)
        await context.bot.send_message(chat_id=user_id, text="❌ خطا در ارسال فایل.")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("دستور نامعتبر است. /help را بزنید.")


def main():
    app = Application.builder().token(TOKEN).build()

    # دستورات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("channels", channels_cmd))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("get", get_media))
    # ادمین: همراه فایل بفرستید: /save 123
    app.add_handler(CommandHandler("save", save_media))
    # بررسی دکمه "عضو شدم"
    app.add_handler(CallbackQueryHandler(check_subs, pattern=r"^check_subs$"))
    # ناشناخته‌ها
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    # ---- اجرا روی Render با Webhook ----
    port = int(os.environ.get("PORT", "10000"))
    external = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if not external:
        raise RuntimeError("RENDER_EXTERNAL_HOSTNAME روی Render ست نشده. سرویس رو دوباره Deploy کن.")

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TOKEN,
        webhook_url=f"https://{external}/{TOKEN}",
    )


if __name__ == "__main__":
    main()
