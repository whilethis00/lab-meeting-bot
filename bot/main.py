"""랩미팅 봇 엔트리포인트"""
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.config import TELEGRAM_BOT_TOKEN, LOG_LEVEL
from bot.handlers.message_handler import handle_message, handle_document, handle_lang_callback
from bot.handlers.command_handler import (
    cmd_start,
    cmd_help,
    cmd_tasks,
    cmd_done,
    cmd_meetings,
    cmd_setname,
    cmd_names,
    cmd_setlang,
    cmd_lang,
)
from storage.database import init_db

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    await init_db()
    logger.info("DB 초기화 완료")


def main():
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # 명령어 핸들러
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(CommandHandler("meetings", cmd_meetings))
    app.add_handler(CommandHandler("setname", cmd_setname))
    app.add_handler(CommandHandler("names", cmd_names))
    app.add_handler(CommandHandler("setlang", cmd_setlang))
    app.add_handler(CommandHandler("lang", cmd_lang))

    # 언어 선택 버튼 콜백
    app.add_handler(CallbackQueryHandler(handle_lang_callback, pattern="^lang:"))

    # 파일 업로드 핸들러 (.txt 등)
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # 일반 메시지 핸들러
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 랩미팅 봇 시작!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
