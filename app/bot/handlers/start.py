from typing import Optional

from asgiref.sync import sync_to_async
from django.template.loader import render_to_string
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.response import send_response
from bot.utils import validate_user


@validate_user
async def start(update: Update, context: Optional[ContextTypes.DEFAULT_TYPE] = None, **kwargs):
    user = kwargs.get('user')
    if user is None:
        return await send_response(update=update, context=context, response='')
    is_created = kwargs.get('is_created') or True

    response = await sync_to_async(render_to_string)(
        template_name='start.html',
        context={
            'user': user,
            'is_created': is_created,
        },
    )
    await send_response(update=update, context=context, response=response)
