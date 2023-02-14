from typing import Tuple

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User as BaseUser
from telegram import Update
from telegram import User as TGUser
from telegram.ext import ContextTypes

from bot.handlers.response import send_response

User: BaseUser = get_user_model()


@sync_to_async
def get_or_create_user(tg_user: TGUser) -> Tuple[BaseUser, bool]:
    user, is_created = User.objects.get_or_create(
        id=tg_user.id, first_name=tg_user.first_name, last_name=tg_user.last_name, username=tg_user.username,
    )
    return user, is_created


def validate_user(handler):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user, is_created = await get_or_create_user(update.effective_user)
        await handler(update, context, user, is_created)

    return wrapped


@validate_user
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, user: BaseUser, is_created: bool):
    text = f'Привет, {user.username}'
    if is_created:
        text += '\nВижу, ты впервые у нас! Сейчас я тебя зарегистрирую в системе.'
    else:
        text += '\nВижу, ты у нас уже был, рад тебя видеть вновь!'
    await send_response(update=update, context=context, response=text)
