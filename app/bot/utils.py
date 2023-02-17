from typing import Optional

from asgiref.sync import sync_to_async
from django.db import IntegrityError
from telegram import Update
from telegram.ext import ContextTypes

from bot.exceptions import UserAlreadyExistsError
from bot.models import User


def validate_user(handler):
    async def wrapped(update: Update, context: Optional[ContextTypes.DEFAULT_TYPE] = None):
        tg_user = update.effective_user
        try:
            user, is_created = await sync_to_async(User.objects.get_or_create)(
                id=tg_user.id,
                username=tg_user.username,
                defaults={
                    'first_name': tg_user.first_name,
                    'last_name': tg_user.last_name,
                },
            )
        except IntegrityError:
            raise UserAlreadyExistsError

        return await handler(update=update, context=context, user=user, is_created=is_created)
    return wrapped
