import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, cast, Union

import telegram
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from telegram import (
    Update,
    Chat,
    ReplyKeyboardRemove,
    Message,
)
# noinspection PyProtectedMember
from telegram._utils.types import ReplyMarkup
from telegram.ext import ContextTypes, ConversationHandler

from common.constants import COMMAND_HELP
from config import settings
from db import UserModel
from db.base import async_session


def render_template(template_name: str, **context) -> str:
    return settings.JINJA_ENVIRONMENT.get_template(template_name).render(**context)


async def get_or_create_user(update: Update) -> UserModel:
    tg_user = update.effective_user
    async with async_session() as session:
        try:
            user = (await session.execute(select(UserModel).filter_by(id=tg_user.id))).scalars().one()
        except NoResultFound:
            user = UserModel(id=tg_user.id)
            session.add(user)

            await session.commit()
    return user


async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    user_id = context.user_data.get('user_id')
    if not user_id:
        user_id = (await get_or_create_user(update=update)).id
        context.user_data['user_id'] = user_id
    return user_id


def force_int(num: Any, default=0) -> int:
    """Форсированный перевод в int.

    Returns:
        число
    """
    try:
        return int(num)
    except (TypeError, ValueError):
        return default


def force_decimal(value, default_value: Any = Decimal('0')) -> Union[Decimal, Any]:
    """
    Изменение типа данных для value на Decimal
    - Если в ходе вычислений произошла ошибка, то вернется дефолтное значение

    :param value: Значение для каста
    :param default_value: Дефолтное значение
    :return: Decimal
    """
    if isinstance(value, Decimal):
        return value

    try:
        if isinstance(value, (int, float)):
            return Decimal(str(value))

        value = re.sub(r'[^0-9.,]+', '', str(value))
        value = value.replace(',', '.')
        value = Decimal(value)
    except (ValueError, TypeError, InvalidOperation):
        value = default_value
    return value


async def delete_last_message(update: Update):
    if update.callback_query:
        await update.callback_query.delete_message()
    else:
        await update.message.delete()


async def edit_last_message(update: Update, text: str, reply_markup: Optional[ReplyMarkup] = None):
    if update.callback_query:
        return await update.callback_query.edit_message_text(
            text=text, parse_mode=telegram.constants.ParseMode.HTML, reply_markup=reply_markup,
        )
    if update.message:
        return await update.message.edit_text(
            text=text, parse_mode=telegram.constants.ParseMode.HTML, reply_markup=reply_markup,
        )


async def send_response(
    update: Update,
    context: Optional[ContextTypes.DEFAULT_TYPE],
    response: str,
    reply_markup: Optional[ReplyMarkup] = None,
) -> Message:

    if update.message:
        return await update.message.reply_text(
            text=response, parse_mode=telegram.constants.ParseMode.HTML, reply_markup=reply_markup,
        )

    args = {
        "chat_id": cast(Chat, update.effective_chat).id,
        "disable_web_page_preview": True,
        "text": response,
        "parse_mode": telegram.constants.ParseMode.HTML,
    }
    if reply_markup:
        args["reply_markup"] = reply_markup

    return await context.bot.send_message(**args)


async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'msg' in context.user_data:
        msg: Message = context.user_data['msg']
        await msg.delete()
        del context.user_data['msg']
    return ConversationHandler.END


def flush_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = get_user_id(update, context)
    context.user_data = {'user_id': user_id}


def user_amount_to_db_amount(user_amount: str) -> Decimal:
    thousands_factor = user_amount.count('k') + user_amount.count('к')
    amount_to_dec = force_decimal(user_amount.replace('k', '').replace('к', ''))
    amount = amount_to_dec * 10 ** (3 * thousands_factor)
    return amount


def sep_titles(message: str) -> list:
    return list(set(message.replace('/', '').replace('\n', ', ').strip().split(', ')))


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        # удаляет последнее отправленное ботом сообщение, в т.ч. Inline Keyboard
        await update.callback_query.delete_message()
    await close(update, context)
    await send_response(
        update=update,
        context=context,
        response=f'Отмена операции.\nСправка тут: /{COMMAND_HELP}',
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END
