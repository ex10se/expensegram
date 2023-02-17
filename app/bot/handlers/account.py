from typing import Optional

from asgiref.sync import sync_to_async
from django.db.models import QuerySet
from django.template.loader import render_to_string
from telegram import Update
from telegram.ext import ContextTypes

from bot.constants import TEXT__ERROR__UNKNOWN, TEXT__ERROR__ACCOUNTS_NOT_FOUND
from bot.handlers.response import send_response
from bot.utils import validate_user
from bot.models import Account, User


@sync_to_async
def get_accounts(user: User):
    return Account.objects.select_related('currency').filter(user=user)


@validate_user
async def account_list(update: Update, context: Optional[ContextTypes.DEFAULT_TYPE] = None, **kwargs):
    user = kwargs.get('user')
    if user is None:
        return await send_response(update=update, context=context, response=TEXT__ERROR__UNKNOWN)

    accounts: QuerySet[Account] = await get_accounts(user=user)
    has_accounts: bool = await sync_to_async(bool)(accounts)
    if not has_accounts:
        return await send_response(update=update, context=context, response=TEXT__ERROR__ACCOUNTS_NOT_FOUND)

    response = await sync_to_async(render_to_string)(
        template_name='account_list.html',
        context={'accounts': accounts.values('id', 'title', 'amount', 'currency__designation')},
    )
    return await send_response(update=update, context=context, response=response)
