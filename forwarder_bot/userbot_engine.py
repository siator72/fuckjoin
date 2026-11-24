"""Optional userbot engine: joins required channels for a bot-start link and ships
the resolved media file to the forwarder bot.

The forwarder bot forwards the user's message to this engine when it sees a
t.me/bot?start=... link; the userbot, running on a real account, joins the
channels and fetches the media. Wire-up lives in run_userbot_engine(); it is
started automatically only when USERBOT_ENABLED=1 in .env.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

log = logging.getLogger("forwarder.userbot")

START_LINK_PREFIXES = ("https://t.me/", "t.me/")


def extract_start_link(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    for word in text.split():
        for prefix in START_LINK_PREFIXES:
            if word.startswith(f"{prefix}bot?start=") or (word.startswith(prefix) and "?start=" in word):
                return word
    return None


async def run_userbot_engine() -> None:
    """Start the fuckjoin userbot as the resolution engine (subprocess)."""
    repo = os.environ.get("USERBOT_DIR", "../fuckjoin")
    log.info("Starting userbot engine from %s", repo)
    proc = await asyncio.create_subprocess_exec(
        "python", "-m", "app", cwd=repo,
        stdout=asyncio.subprocess.InheritHandle if os.name == "nt" else None,
        stderr=asyncio.subprocess.InheritHandle if os.name == "nt" else None,
    )
    await proc.wait()
    log.warning("Userbot engine exited with code %s", proc.returncode)
