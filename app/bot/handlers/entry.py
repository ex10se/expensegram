import logging
from decimal import Decimal
from typing import (
    Union,
    Optional,
)

from asgiref.sync import (
    sync_to_async,
)
from django.db.utils import DataError
from telegram import Update
from telegram.ext import ContextTypes

from bot.exceptions import (
    BadFirstCharForEntryError,
    CantRecognizeAmountError,
    CantFindAccountError,
    BaseError,
    CantFindCategoryError,
    WrongPartsCountError,
    TooBigAmountError,
)
from bot.handlers.response import (
    send_response,
    done,
)
from bot.models import (
    Entry,
    Account,
    MessageMap,
    Category,
    Subcategory,
    Transfer,
)
from config.utils import force_decimal

logger = logging.getLogger(__name__)


def amount_to_decimal(amount: str) -> Decimal:
    amount = amount.lower()
    ten_factor = amount.count('k') + amount.count('к')
    amount = amount.replace('k', '').replace('к', '').replace(',', '.')
    logger.info(f'cleaned amount: {amount}, ten factor: {ten_factor}')
    amount = force_decimal(amount, None)
    if amount is None:
        raise CantRecognizeAmountError
    if ten_factor > 0:
        amount *= 10 ** (3 * ten_factor)
    logger.info(f'decimal amount: {amount}')
    return amount


def find_account(account_alias: str) -> Account:
    account_alias = account_alias.lower()
    message_map = MessageMap.objects.filter(alias=account_alias).first()
    logger.info(f'no message_map for alias={account_alias}')
    if message_map is None:
        account = Account.objects.title_lower(title=account_alias).first()
        if account is None:
            logger.info(f'no account for title={account_alias}')
            raise CantFindAccountError
    else:
        account = message_map.find_account()
    if account is None:
        raise CantFindAccountError
    logger.info(f'MessageMap for {account_alias}: id = {account.id}')
    return account


def resolve_desc(desc: str) -> Union[Category, Subcategory]:
    desc = desc.lower()
    message_map = MessageMap.objects.filter(alias=desc).first()
    if message_map is None:
        category = Category.objects.title_lower(title=desc).first()
        if category is None:
            subcategory = Subcategory.objects.title_lower(title=desc).first()
            if subcategory is None:
                raise CantFindCategoryError
            else:
                return subcategory
        else:
            return category
    else:
        cat = message_map.find()
        if isinstance(cat, (Category, Subcategory)):
            logger.info(f'MessageMap for {desc}: {type(cat)}, id = {cat.id}')
            return cat


def handle_entry_message(amount: str, account: Account, desc: str) -> Union[Entry, Transfer]:
    amount = amount_to_decimal(amount)

    entry_kwargs = {
        'amount': amount,
        'account': account,
        'title': desc,
    }

    cat = resolve_desc(desc)
    if isinstance(cat, Category):
        entry_kwargs['category'] = cat
    elif isinstance(cat, Subcategory):
        entry_kwargs['subcategory'] = cat
        entry_kwargs['category'] = cat.category
    try:
        return Entry.objects.create(**entry_kwargs)
    except DataError:
        raise TooBigAmountError


def handle_transfer_message(
        account_alias_from: str, account_alias_to: str, amount_from: str, amount_to: Optional[str] = None,
):
    amount_from = amount_to_decimal(amount_from)
    if amount_to is None:
        amount_to = amount_from
    else:
        amount_to = amount_to_decimal(amount_to)

    account_from = find_account(account_alias_from)
    account_to = find_account(account_alias_to)

    transfer_kwargs = {
        'amount_from': amount_from,
        'amount_to': amount_to,
        'account_from': account_from,
        'account_to': account_to,
    }
    try:
        return Transfer.objects.create(**transfer_kwargs)
    except DataError:
        raise TooBigAmountError


async def handle_message(update: Update, context: Optional[ContextTypes.DEFAULT_TYPE] = None):
    if update.message is None:
        return None
    message = update.message.text
    try:
        parts = message.strip().split(' ')
        if len(parts) == 3:
            logger.info('3 parts')
            try:
                await sync_to_async(find_account)(parts[-1])
            except CantFindAccountError:
                if message.startswith('+') or message.startswith('-'):
                    amount, account_alias, desc = parts
                    account = await sync_to_async(find_account)(account_alias)
                    await sync_to_async(handle_entry_message)(amount=amount, account=account, desc=desc)
                    return await done(update=update, context=context)
                raise BadFirstCharForEntryError

            amount, account_alias_from, account_alias_to = parts
            logger.info(f'parts (lower): {amount} {account_alias_from} {account_alias_to}')
            await sync_to_async(handle_transfer_message)(
                account_alias_from=account_alias_from, account_alias_to=account_alias_to, amount_from=amount,
            )
            return await done(update=update, context=context)

        elif len(parts) == 4:
            logger.info('4 parts')
            amount_from, account_alias_from, amount_to, account_alias_to = parts
            await sync_to_async(handle_transfer_message)(
                account_alias_from=account_alias_from,
                account_alias_to=account_alias_to,
                amount_from=amount_from,
                amount_to=amount_to,
            )
            return await done(update=update, context=context)
        else:
            raise WrongPartsCountError
    except BaseError as e:
        logger.warning(f'error {type(e)}: {e}')
        return await send_response(
            update=update,
            context=context,
            response=str(e),
        )
