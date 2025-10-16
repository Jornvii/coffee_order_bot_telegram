import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ApplicationBuilder

from handler import start, help_command, button_callback

# Load environment variables
load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment")
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, ApplicationBuilder


# fc yk group id command
# async def get_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     chat = update.effective_chat
#     await update.message.reply_text(f"This chat ID is: {chat.id}")


def main():
    application = Application.builder().token(BOT_TOKEN).build()



    # application = ApplicationBuilder().token(BOT_TOKEN).build()
    # application.add_handler(CommandHandler("id", get_group_id))
    # application.run_polling()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("🤖 Coffee Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":  
    main()
