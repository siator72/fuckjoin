"""Forwarder bot: users forward messages/files, the bot delivers the media back.

Run with: python -m forwarder_bot
Requires BOT_TOKEN in .env (from @BotFather). Optional: ALLOWED_USER_IDS (comma-separated
numeric Telegram IDs) to restrict who can use the bot.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, Message

from .userbot_engine import extract_start_link, run_userbot_engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("forwarder")

MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024  # Telegram bots can download up to 20 MB via API; keep margin
TMP_DIR = Path("downloads")


def load_env(path: str = ".env") -> None:
    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def is_allowed(message: Message) -> bool:
    allowed = os.environ.get("ALLOWED_USER_IDS", "").strip()
    if not allowed:
        return True
    ids = {part.strip() for part in allowed.split(",") if part.strip()}
    return str(message.from_user.id) in ids if message.from_user else False


async def deliver_media(bot: Bot, message: Message) -> None:
    """Send back whatever media the (possibly forwarded) message carries."""
    if message.photo:
        await bot.send_photo(message.chat.id, message.photo[-1].file_id)
    elif message.video:
        if (message.video.file_size or 0) > MAX_DOWNLOAD_BYTES:
            await message.reply("File too large for Bot API delivery (20 MB limit).")
            return
        await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)
        file = await bot.get_file(message.video.file_id)
        TMP_DIR.mkdir(exist_ok=True)
        dest = TMP_DIR / (message.video.file_name or f"{message.video.file_unique_id}.mp4")
        await bot.download_file(file.file_path, destination=dest)
        await message.answer_video(FSInputFile(dest), caption=message.caption)
        dest.unlink(missing_ok=True)
    elif message.document:
        if (message.document.file_size or 0) > MAX_DOWNLOAD_BYTES:
            await message.reply("File too large for Bot API delivery (20 MB limit).")
            return
        file = await bot.get_file(message.document.file_id)
        TMP_DIR.mkdir(exist_ok=True)
        dest = TMP_DIR / (message.document.file_name or message.document.file_unique_id)
        await bot.download_file(file.file_path, destination=dest)
        await message.answer_document(FSInputFile(dest), caption=message.caption)
        dest.unlink(missing_ok=True)
    elif message.audio:
        await bot.send_audio(message.chat.id, message.audio.file_id)
    elif message.voice:
        await bot.send_voice(message.chat.id, message.voice.file_id)
    else:
        await message.reply("No media found in this message.")


async def main() -> None:
    load_env()
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is missing. Create a bot with @BotFather and put BOT_TOKEN=... in .env")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        if not is_allowed(message):
            return
        await message.reply(
            "Send or forward me any file/media and I'll deliver it right back.\n"
            f"Your numeric ID: {message.from_user.id}"
        )

    @dp.message(F.content_type.in_({"text"}))
    async def text(message: Message) -> None:
        if not is_allowed(message):
            return
        link = extract_start_link(message.text)
        if link and os.environ.get("USERBOT_ENABLED") == "1":
            await message.reply(f"Resolving {link} via userbot engine… (this may take a minute)")
            return
        await message.reply("Forward me a message that contains media (video, document, photo…).")

    @dp.message()
    async def any_media(message: Message) -> None:
        if not is_allowed(message):
            return
        await deliver_media(bot, message)

    log.info("Forwarder bot starting (long polling)…")
    if os.environ.get("USERBOT_ENABLED") == "1":
        asyncio.create_task(run_userbot_engine())
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
