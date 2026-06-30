import asyncio
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
from rutracker import RutrackerClient, playwright_login

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = RutrackerClient(config.RUTRACKER_USERNAME, config.RUTRACKER_PASSWORD)


async def start(update: Update, context) -> None:
    await update.message.reply_text(
        "Отправь мне название фильма, сериала или игры — найду торрент на rutracker"
    )


async def _do_login(update: Update, context) -> bool:
    """Login via Playwright. Returns True if successful."""
    chat_id = update.effective_chat.id
    context.user_data["login_in_progress"] = True
    await context.bot.send_message(chat_id=chat_id, text="Авторизуюсь на rutracker...")

    async def captcha_callback(screenshot: bytes) -> str:
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        context.user_data["captcha_future"] = future
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=io.BytesIO(screenshot),
            caption="Братан, без проблем, но помоги с капчей — напиши что написано на картинке",
        )
        return await future

    try:
        cookies = await playwright_login(config.RUTRACKER_USERNAME, config.RUTRACKER_PASSWORD, captcha_callback)
    except TimeoutError:
        await context.bot.send_message(chat_id=chat_id, text="Время ожидания истекло — отправь запрос заново")
        return False
    except Exception:
        logger.exception("Playwright login failed")
        await context.bot.send_message(chat_id=chat_id, text="Не удалось войти на rutracker")
        return False
    finally:
        context.user_data.pop("captcha_future", None)
        context.user_data.pop("login_in_progress", None)

    if "bb_session" not in cookies:
        await context.bot.send_message(chat_id=chat_id, text="Не удалось войти на rutracker — проверь логин/пароль")
        return False

    client.set_session_cookies(cookies)
    return True


async def _do_search(update: Update, context, query: str) -> None:
    status_msg = await update.message.reply_text("Ищу...")
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, client.search, query)
    except RuntimeError:
        await status_msg.delete()
        ok = await _do_login(update, context)
        if ok:
            await _do_search(update, context, query)
        return
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


async def handle_search(update: Update, context) -> None:
    # If user is solving a captcha — pop atomically so old queued messages don't double-fire
    if "captcha_future" in context.user_data:
        future: asyncio.Future = context.user_data.pop("captcha_future")
        if not future.done():
            future.set_result(update.message.text.strip())
        return

    # Prevent search while login is already in progress
    if context.user_data.get("login_in_progress"):
        await update.message.reply_text("Подождите, идёт авторизация...")
        return

    query = update.message.text.strip()
    if len(query) < 3:
        await update.message.reply_text("Введи не менее 3 символов для поиска")
        return
    await _do_search(update, context, query)


async def handle_selection(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    topic_id = query.data

    await query.edit_message_text("Скачиваю...")

    try:
        loop = asyncio.get_event_loop()
        torrent_bytes = await loop.run_in_executor(None, client.get_torrent, topic_id)
        magnet = await loop.run_in_executor(None, client.get_magnet, topic_id)
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
    app = Application.builder().token(config.BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_selection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    app.run_polling()


if __name__ == "__main__":
    main()
