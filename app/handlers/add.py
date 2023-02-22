from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy import select
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
)

from common import constants
from common.utils import (
    cancel,
    send_response,
    delete_last_message,
    edit_last_message,
    force_decimal,
    get_user_id,
    force_int,
)
from db import CategoryModel, AccountModel, EntryModel
from db.base import async_session


class AddConversation:

    STATE__CHOOSE_ENTRY_TYPE = 0
    STATE__ENTRY_ACCOUNT_CHOOSE = 1
    STATE__ENTRY_CATEGORY_CHOOSE = 2
    STATE__CREATE_ACCOUNT = 3
    STATE__CREATE_CATEGORY = 4
    STATE__WRITE_CHANGES = 5

    ACTION__CLOSE = 'close'
    ACTION__EXPENSE = 'expense'
    ACTION__INCOME = 'income'
    ACTION__TRANSFER = 'transfer'
    ACTION__ADD = 'add'

    @classmethod
    def handler(cls):
        return ConversationHandler(
            entry_points=[CommandHandler(cls.add.__name__, cls.add)],
            states={
                cls.STATE__CHOOSE_ENTRY_TYPE: [CallbackQueryHandler(cls.choose_entry_type)],
                cls.STATE__ENTRY_ACCOUNT_CHOOSE: [
                    MessageHandler(filters.Regex('^/cancel$'), cancel),
                    MessageHandler(filters.TEXT, cls.entry_account_choose),
                ],
                # cls.STATE__TRANSFER: [
                #     MessageHandler(filters.Regex('^/cancel$'), cancel),
                #     MessageHandler(filters.TEXT, cls.transfer),
                # ],
                cls.STATE__CREATE_ACCOUNT: [],  # todo
                cls.STATE__CREATE_CATEGORY: [],
                cls.STATE__ENTRY_CATEGORY_CHOOSE: [CallbackQueryHandler(cls.entry_category_choose)],
                cls.STATE__WRITE_CHANGES: [CallbackQueryHandler(cls.write_changes)]
            },
            fallbacks=[CommandHandler(constants.COMMAND_CANCEL, cancel)],
            allow_reentry=True,
        )

    @classmethod
    async def add(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = await get_user_id(update, context)

        async with async_session() as session:
            accounts = (await session.execute(select(AccountModel).filter_by(user_id=user_id))).scalars().all()

        if not accounts:
            text = 'У вас нет ни одного счёта, введите название нового (/cancel для отмены):'
            await send_response(update=update, context=context, response=text)
            return cls.STATE__CREATE_ACCOUNT

        accounts = {account.id: account for account in accounts}
        context.user_data['accounts'] = accounts

        async with async_session() as session:
            categories = (await session.execute(select(CategoryModel).filter_by(user_id=user_id))).scalars().all()

        if not categories:
            text = 'У вас нет ни одной категории, введите название новой (/cancel для отмены):'
            await send_response(update=update, context=context, response=text)
            return cls.STATE__CREATE_CATEGORY

        categories = {category.id: category for category in categories if not category.disabled}
        context.user_data['categories'] = categories

        reply_markup = InlineKeyboardMarkup([
            [
                # InlineKeyboardButton('Перевод', callback_data=cls.ACTION__TRANSFER),
                InlineKeyboardButton('Закрыть', callback_data=cls.ACTION__CLOSE),
            ],
            [
                InlineKeyboardButton('Доход', callback_data=cls.ACTION__INCOME),
                InlineKeyboardButton('Расход', callback_data=cls.ACTION__EXPENSE),
            ],
        ])
        await send_response(update=update, context=context, response='Выберите тип записи', reply_markup=reply_markup)
        return cls.STATE__CHOOSE_ENTRY_TYPE

    @classmethod
    async def choose_entry_type(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()

        entry_text = (
            'Введите сумму %s с заметкой, если нужно, например:\n\n'
            '    <code>100</code>\n\n'
            '    <code>10k</code>\n\n'
            '    <code>1,5к</code>\n\n'
            '    <code>1.6кк работа</code>\n\n'
            '    <code>100\n  вода</code>\n\n'
            '/cancel для отмены'
        )

        query_data = update.callback_query.data
        if query_data == cls.ACTION__CLOSE:
            await delete_last_message(update)
            return ConversationHandler.END
        if query_data == cls.ACTION__INCOME:
            await edit_last_message(update, entry_text % 'дохода')
            context.user_data['entry_type'] = cls.ACTION__INCOME
            return cls.STATE__ENTRY_ACCOUNT_CHOOSE
        if query_data == cls.ACTION__EXPENSE:
            await edit_last_message(update, entry_text % 'расхода')
            context.user_data['entry_type'] = cls.ACTION__EXPENSE
            return cls.STATE__ENTRY_ACCOUNT_CHOOSE
        # if query_data == cls.ACTION__TRANSFER:
        #     await edit_last_message(update, 'Введите сумму перевода (/cancel для отмены)')
        #     return cls.STATE__TRANSFER

    @classmethod
    async def entry_account_choose(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        amount, title = cls._prepare_entry_amount(update.message.text)
        if amount is None:
            await send_response(update=update, context=context, response='Неверный формат ввода')
            return await cls.add(update, context)

        context.user_data['amount'] = amount
        context.user_data['title'] = title
        accounts = context.user_data['accounts']

        # распределяем кнопки по 2 в ряд
        keyboard_map = []
        for i, account in enumerate(accounts.values()):
            button = InlineKeyboardButton(account.title, callback_data=account.id)
            if not i % 2:
                keyboard_map.append([button])
            else:
                keyboard_map[-1].append(button)

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton('Добавить', callback_data=cls.ACTION__ADD)],
            [InlineKeyboardButton('Закрыть', callback_data=cls.ACTION__CLOSE)],
            *keyboard_map,
        ])
        await send_response(update=update, context=context, response='Выберите счёт', reply_markup=reply_markup)
        return cls.STATE__ENTRY_CATEGORY_CHOOSE

    @classmethod
    async def entry_category_choose(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()

        query_data = update.callback_query.data
        if query_data == cls.ACTION__CLOSE:
            await delete_last_message(update)
            return ConversationHandler.END
        if query_data == cls.ACTION__ADD:
            await delete_last_message(update)
            return await cls.add(update, context)

        context.user_data['account_id'] = query_data
        categories = context.user_data['categories']

        # распределяем кнопки по 2 в ряд
        keyboard_map = []
        for i, category in enumerate(categories.values()):
            button = InlineKeyboardButton(category.title, callback_data=category.id)
            if not i % 2:
                keyboard_map.append([button])
            else:
                keyboard_map[-1].append(button)

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton('Добавить', callback_data=cls.ACTION__ADD)],
            [InlineKeyboardButton('Закрыть', callback_data=cls.ACTION__CLOSE)],
            *keyboard_map,
        ])
        await edit_last_message(update=update, text='Выберите категорию', reply_markup=reply_markup)
        return cls.STATE__WRITE_CHANGES

    @classmethod
    async def write_changes(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = await get_user_id(update, context)
        await update.callback_query.answer()

        query_data = update.callback_query.data
        if query_data == cls.ACTION__CLOSE:
            await delete_last_message(update)
            return ConversationHandler.END
        if query_data == cls.ACTION__ADD:
            await delete_last_message(update)
            return await cls.add(update, context)

        account_id = force_int(context.user_data['account_id'])

        amount = force_decimal(context.user_data['amount'])
        if context.user_data['entry_type'] == cls.ACTION__EXPENSE:
            amount *= -1

        entry = EntryModel(
            amount=amount,
            title=context.user_data['title'],
            category_id=force_int(query_data),
            account_id=account_id,
            user_id=user_id,
        )
        async with async_session() as session:
            account = (await session.execute(select(AccountModel).filter_by(id=account_id))).scalars().one()
            account.amount += amount
            session.add(account)
            session.add(entry)
            await session.commit()

        await edit_last_message(update=update, text='Запись добавлена')
        return ConversationHandler.END

    @staticmethod
    def _prepare_entry_amount(amount_str: str) -> Tuple[Optional[Decimal], Optional[str]]:
        title = None
        if '\n' in amount_str:
            amount, title = amount_str.split('\n', 1)
        else:
            amount = amount_str
        thousands_factor = amount.count('k') + amount.count('к')
        amount_to_dec = force_decimal(amount.replace('k', '').replace('к', ''), None)
        amount = amount_to_dec * 10 ** (3 * thousands_factor)
        return amount, title
