from django.template.loader import render_to_string
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.response import send_response


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_response(update, context, response=render_to_string("start.html", context={'test_var': 'HELLO WORLD'}))
