from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from common.utils import render_template, send_response


async def start(update: Update, context: Optional[ContextTypes.DEFAULT_TYPE]):
    """
    /start
    """
    await send_response(update=update, context=context, response=render_template('help.html'))


async def help_(update: Update, context: Optional[ContextTypes.DEFAULT_TYPE]):
    """
    /help
    """
    await send_response(update=update, context=context, response=render_template('help.html'))
