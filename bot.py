import io
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
from rutracker import RutrackerClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = RutrackerClient(config.RUTRACKER_USERNAME, config.RUTRACKER_PASSWORD)


async def start(update: Update, context) -> None:
    await update.message.reply_text(
        "Отправь мне название фильма, сериала или игры — найду торрент на rutracker"
    )


async def handle_search(update: Update, context) -> None:
    query = update.message.text.strip()
    status_msg = await update.message.reply_text("Ищу...")

    try:
        results = client.search(query)
    except Exception:
        logger.exception("Search failed for query: %s", query)
        await status_msg.edit_text("Rutracker временно недоступен")
        return

    if not results:
        await status_msg.edit_text("По запросу ничего не найдено")
        return

    keyboard = [
        [InlineKeyboardButton(
            f"{r.title[:55]} | {r.size} | {r.seeders} сид",
            callback_data=r.topic_id,
        )]
        for r in results
    ]
    await status_msg.edit_text(
        f"Найдено {len(results)} результатов:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_selection(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    topic_id = query.data

    await query.edit_message_text("Скачиваю...")

    try:
        torrent_bytes = client.get_torrent(topic_id)
        magnet = client.get_magnet(topic_id)
    except Exception:
        logger.exception("Download failed for topic_id: %s", topic_id)
        await query.edit_message_text("Rutracker временно недоступен")
        return

    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=io.BytesIO(torrent_bytes),
        filename=f"{topic_id}.torrent",
    )
    if magnet:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"`{magnet}`",
            parse_mode="Markdown",
        )


def main() -> None:
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_selection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    app.run_polling()


if __name__ == "__main__":
    main()
