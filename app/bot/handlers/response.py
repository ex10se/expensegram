from typing import (
    cast,
    Optional,
    Dict,
    Any,
)

import telegram
from telegram import Chat, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes


async def send_response(
    update: Update,
    response: str,
    context: Optional[ContextTypes.DEFAULT_TYPE] = None,
    keyboard: Optional[InlineKeyboardMarkup] = None,
) -> Optional[Dict[str, Any]]:
    args = {
        "chat_id": _get_chat_id(update),
        "disable_web_page_preview": True,
        "text": response,
        "parse_mode": telegram.constants.ParseMode.HTML,
    }
    if keyboard:
        args["reply_markup"] = keyboard

    if context is None:
        return args
    await context.bot.send_message(**args)


def _get_chat_id(update: Update) -> int:
    return cast(Chat, update.effective_chat).id


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_response(
        update=update,
        context=context,
        response='Готово',
    )
