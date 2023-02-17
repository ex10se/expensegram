from typing import Optional

from asgiref.sync import sync_to_async
from django.template.loader import render_to_string
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.response import send_response


async def help_(update: Update, context: Optional[ContextTypes.DEFAULT_TYPE] = None):
    response = await sync_to_async(render_to_string)(
        template_name='help.html',
    )
    return await send_response(update=update, context=context, response=response)
