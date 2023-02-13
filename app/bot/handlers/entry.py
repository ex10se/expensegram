import logging
from typing import Union

from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.response import send_response
from bot.models import Entry, Account, MessageMap, Category, Subcategory, Transfer
from config.utils import force_decimal

logger = logging.getLogger(__name__)


# todo улучшить работу с исключениями, покрыть тестами
@sync_to_async
def handle_entry_message(message: str) -> Union[Entry, Transfer]:
    parts = message.strip().split(' ')
    if len(parts) == 3:
        logger.info('3 parts')
        if not message.startswith('+') and not message.startswith('-'):
            logger.info(f'message starts with {message[0]}')
            raise ValueError
        amount, account_alias_from, desc = (x.lower() for x in parts)
        logger.info(f'parts (lower): {amount} {account_alias_from} {desc}')

        ten_factor = amount.count('k') + amount.count('к')
        amount = amount.replace('k', '').replace('к', '').replace(',', '.')
        logger.info(f'cleaned amount: {amount}, ten factor: {ten_factor}')
        amount = force_decimal(amount, None)
        if amount is None:
            raise ValueError
        if ten_factor > 0:
            amount *= 10 ** (3 * ten_factor)
        logger.info(f'decimal amount: {amount}')
        try:
            account = MessageMap.objects.get(alias=account_alias_from).find()
            logger.info(f'MessageMap for {account_alias_from}: {type(account)}, id={account.id}')
            if not isinstance(account, Account):
                raise Account.DoesNotExist
        except ObjectDoesNotExist:
            raise ValueError

        entry_kwargs = {
            'amount': amount,
            'account': account,
            'title': desc,
        }

        cat = MessageMap.objects.get(alias=desc).find()
        logger.info(f'MessageMap for {desc}: {type(cat)}, id={cat.id}')
        if isinstance(cat, Category):
            entry_kwargs['category'] = cat
        elif isinstance(cat, Subcategory):
            entry_kwargs['subcategory'] = cat
            entry_kwargs['category'] = cat.category
        else:
            raise ValueError

        return Entry.objects.create(**entry_kwargs)

    elif len(parts) == 4:  # todo проверить, залогировать
        amount_from, account_alias_from, amount_to, account_alias_to = (x.lower() for x in parts)

        amount_from = force_decimal(amount_from, None)
        amount_to = force_decimal(amount_to, None)
        if amount_from is None or amount_to is None:
            raise ValueError

        try:
            account_from = MessageMap.objects.get(alias=account_alias_from).find()
            account_to = MessageMap.objects.get(alias=account_alias_to).find()
            if not isinstance(account_from, Account) or not isinstance(account_to, Account):
                raise Account.DoesNotExist
        except ObjectDoesNotExist:
            raise ValueError

        transfer_kwargs = {
            'amount_from': amount_from,
            'amount_to': amount_to,
            'account_from': account_from,
            'account_to': account_to,
        }
        return Transfer.objects.create(**transfer_kwargs)
    else:
        raise ValueError


async def handle_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return None
    try:
        created_obj = await handle_entry_message(update.message.text)
    except ValueError:
        return await send_response(
            update=update,
            context=context,
            response=f'Не могу распознать, что значит {update.message.text}.\n'
                     f'Пожалуйста, введи команду правильно'
        )
    if isinstance(created_obj, Entry):
        return await add_entry(update=update, context=context, obj=created_obj)
    elif isinstance(created_obj, Transfer):
        return await do_transfer(update=update, context=context)
    # return await remove_entry(update=update, context=context)


async def add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, obj: Entry):
    await send_response(
        update,
        context,
        response=f'изменил сумму на аккаунте "{obj.account.title}" на {obj.amount} {obj.account.currency}',
    )


# todo
# async def remove_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await send_response(update, context, response='')


async def do_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # todo
    user_message = update.message.text
    await send_response(update, context, response=f'перенёс {user_message}')
