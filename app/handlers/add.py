from decimal import Decimal
from typing import Tuple, Optional

from sqlalchemy import select
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Message
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes, filters,
)

from common import constants
from common.constants import COMMAND_CANCEL, COMMAND_ADD
from common.utils import (
    cancel,
    send_response,
    delete_last_message,
    get_user_id, user_amount_to_db_amount, edit_last_message, flush_user_data,
)
from db import CategoryModel, AccountModel, EntryModel
from db.base import async_session


class AddConversation:

    STAGE__CREATE_ENTRY__CATEGORY_ACCOUNT_CHECK = 0
    STAGE__CREATE_ENTRY__CHOOSE_ACCOUNT = 1
    STAGE__CREATE_ENTRY__ENTER_AMOUNT = 2
    STAGE__ADD_ENTRY = 3

    STAGE__CREATE_CATEGORY = 20

    STAGE__CREATE_ACCOUNT__TITLE = 30
    STAGE__CREATE_ACCOUNT = 31

    ACTION__CLOSE = 'Закрыть'
    ACTION__EXPENSE = 'Расход'
    ACTION__INCOME = 'Доход'
    ACTION__TRANSFER = 'Перевод'
    ACTION__ADD = 'Добавить'

    BAD_WORDS = [
        ACTION__CLOSE,
        ACTION__EXPENSE,
        ACTION__INCOME,
        ACTION__TRANSFER,
        ACTION__ADD,
        f'/{COMMAND_CANCEL}'
    ]

    @classmethod
    def handler(cls):
        return ConversationHandler(
            entry_points=[CommandHandler(COMMAND_ADD, cls.entrypoint)],
            states={
                cls.STAGE__CREATE_ENTRY__CATEGORY_ACCOUNT_CHECK: [
                    CallbackQueryHandler(cls.create_entry__remember_entry_type),
                ],
                cls.STAGE__CREATE_ENTRY__CHOOSE_ACCOUNT: [CallbackQueryHandler(cls.create_entry__choose_account)],
                cls.STAGE__CREATE_ENTRY__ENTER_AMOUNT: [CallbackQueryHandler(cls.create_entry__enter_amount)],
                cls.STAGE__ADD_ENTRY: [
                    MessageHandler(filters.Regex(rf'^/{COMMAND_CANCEL}$'), cancel),
                    MessageHandler(filters.TEXT, cls.add_entry),
                ],
                cls.STAGE__CREATE_CATEGORY: [
                    MessageHandler(filters.Regex(rf'^/{COMMAND_CANCEL}$'), cancel),
                    MessageHandler(filters.TEXT, cls.create_category),
                ],
                cls.STAGE__CREATE_ACCOUNT__TITLE: [
                    MessageHandler(filters.Regex(rf'^/{COMMAND_CANCEL}$'), cancel),
                    MessageHandler(filters.TEXT, cls.create_account__title),
                ],
                cls.STAGE__CREATE_ACCOUNT: [
                    MessageHandler(filters.Regex(rf'^/{COMMAND_CANCEL}$'), cancel),
                    MessageHandler(filters.TEXT, cls.create_account),
                ],
            },
            fallbacks=[CommandHandler(constants.COMMAND_CANCEL, cancel)],
            allow_reentry=True,
        )

    @classmethod
    async def entrypoint(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        msg = await send_response(
            update=update, context=context, response='Выберите тип записи', reply_markup=reply_markup,
        )
        context.user_data['last_msg'] = msg
        return cls.STAGE__CREATE_ENTRY__CATEGORY_ACCOUNT_CHECK

    @classmethod
    async def create_entry__remember_entry_type(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()

        query_data = update.callback_query.data
        if query_data == cls.ACTION__CLOSE:
            await delete_last_message(update)
            return ConversationHandler.END
        if query_data == cls.ACTION__INCOME:
            context.user_data['entry_type'] = cls.ACTION__INCOME
        elif query_data == cls.ACTION__EXPENSE:
            context.user_data['entry_type'] = cls.ACTION__EXPENSE

        return await cls.create_entry__category_account_check(update, context)

    @classmethod
    async def create_entry__category_account_check(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = await get_user_id(update, context)

        async with async_session() as session:
            accounts = (await session.execute(select(AccountModel).filter_by(user_id=user_id))).scalars().all()
        if not accounts:
            text = 'У вас нет ни одного счёта, введите название нового (/cancel для отмены):'
            await edit_last_message(update=update, text=text)
            return cls.STAGE__CREATE_ACCOUNT__TITLE
        accounts = {account.id: account for account in accounts}
        context.user_data['accounts'] = accounts
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
        if context.user_data['entry_type'] == cls.ACTION__INCOME:
            entry_type_str = '<b>дохода</b>'
        else:
            entry_type_str = '<b>расхода</b>'
        text = f'Выберите счёт для записи {entry_type_str}'
        if context.user_data.get('last_msg'):
            msg = await edit_last_message(update=update, text=text, reply_markup=reply_markup)
            if isinstance(msg, Message):
                context.user_data['last_msg'] = msg
            else:
                del context.user_data['last_msg']
        else:
            msg = await send_response(update=update, context=context, response=text, reply_markup=reply_markup)
            context.user_data['last_msg'] = msg
        return cls.STAGE__CREATE_ENTRY__CHOOSE_ACCOUNT

    @classmethod
    async def create_entry__choose_account(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()

        query_data = update.callback_query.data
        if query_data == cls.ACTION__CLOSE:
            await delete_last_message(update)
            return ConversationHandler.END
        if query_data == cls.ACTION__ADD:
            text = 'Введите название нового счёта (/cancel для отмены):'
            if context.user_data.get('last_msg'):
                await edit_last_message(update=update, text=text)
                del context.user_data['last_msg']
            else:
                await send_response(
                    update=update,
                    context=context,
                    response=text,
                )
            return cls.STAGE__CREATE_ACCOUNT__TITLE

        context.user_data['account_id'] = int(query_data)
        return await cls.create_entry__choose_category(update, context)

    @classmethod
    async def create_entry__choose_category(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = await get_user_id(update, context)

        async with async_session() as session:
            categories = (await session.execute(select(CategoryModel).filter_by(user_id=user_id))).scalars().all()
        if not categories:
            text = 'У вас нет ни одной категории, введите название новой (/cancel для отмены):'
            await send_response(update=update, context=context, response=text)
            return cls.STAGE__CREATE_CATEGORY
        categories = {category.id: category for category in categories if not category.disabled}
        context.user_data['categories'] = categories

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
        account_title = context.user_data['accounts'][context.user_data['account_id']].title
        if context.user_data['entry_type'] == cls.ACTION__INCOME:
            entry_type_str = '<b>дохода</b> на счёт'
        else:
            entry_type_str = '<b>расхода</b> со счёта'
        text = f'Выберите категорию записи {entry_type_str} <b>{account_title}</b>'
        if context.user_data.get('last_msg'):
            await edit_last_message(update=update, text=text, reply_markup=reply_markup)
            del context.user_data['last_msg']
        else:
            await send_response(update=update, context=context, response=text, reply_markup=reply_markup)
        return cls.STAGE__CREATE_ENTRY__ENTER_AMOUNT

    @classmethod
    async def create_entry__enter_amount(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()

        query_data = update.callback_query.data
        if query_data == cls.ACTION__CLOSE:
            await delete_last_message(update)
            return ConversationHandler.END
        if query_data == cls.ACTION__ADD:
            await edit_last_message(
                update=update,
                text='Введите название новой категории (/cancel для отмены):',
            )
            return cls.STAGE__CREATE_CATEGORY

        category_id = int(query_data)
        context.user_data['category_id'] = category_id
        category_title = context.user_data['categories'][category_id].title

        if context.user_data['entry_type'] == cls.ACTION__INCOME:
            entry_type_str = 'дохода'
        else:
            entry_type_str = 'расхода'
        await edit_last_message(
            update=update,
            text=(
                f'Введите сумму %s на <b>{category_title}</b> с заметкой, если нужно, по следующим примерам:\n\n'
                '    <code>100</code>\n'
                '    <code>10k</code>\n'
                '    <code>1,5к</code>\n'
                '    <code>100к работа</code>\n'
                '    <code>100\n  вода</code>\n\n'
                '/cancel для отмены' % entry_type_str
            ),
        )

        return cls.STAGE__ADD_ENTRY

    @classmethod
    async def add_entry(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        amount, title = cls._prepare_entry_amount(update.message.text)
        if amount is None:
            await send_response(update=update, context=context, response='Неверный формат ввода')
            return await cls.entrypoint(update, context)
        if context.user_data['entry_type'] == cls.ACTION__EXPENSE:
            amount *= -1
        user_id = await get_user_id(update, context)
        account_id = context.user_data['account_id']
        account = context.user_data['accounts'][account_id]
        category_id = context.user_data['category_id']

        entry = EntryModel(
            user_id=user_id, amount=amount, title=title, category_id=category_id, account_id=account_id,
        )
        async with async_session() as session:
            account.amount += amount
            session.add(account)
            session.add(entry)
            await session.commit()

        await send_response(
            update=update,
            context=context,
            response=(
                f'Запись добавлена, теперь баланс счёта <b>{account.title}</b> '
                f'составляет {account.amount} {account.currency}'
            ),
        )
        flush_user_data(update, context)
        return ConversationHandler.END

    @classmethod
    async def create_account__title(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        account_title = update.message.text
        context.user_data['account_title'] = account_title

        text = (
            f'Введите начальную сумму счёта <b>{account_title}</b> с обозначением валюты через пробел, например:\n\n'
            '   <code>0 руб</code>\n'
            '   <code>300 $</code>\n'
            '   <code>10к тенге</code>\n'
            '   <code>3kk сум</code>\n\n'
            '(/cancel для отмены)'
        )
        await send_response(update=update, context=context, response=text)

        return cls.STAGE__CREATE_ACCOUNT

    @classmethod
    async def create_account(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = await get_user_id(update, context)
        message = update.message.text
        if message.count(' ') != 1:
            await send_response(update=update, context=context, response='Неверный формат ввода')
            return await cls.create_account__title(update, context)
        amount, currency = update.message.text.split(' ')
        amount = user_amount_to_db_amount(amount)
        title = context.user_data['account_title']

        account = AccountModel(
            title=title,
            user_id=user_id,
            amount=amount,
            currency=currency,
        )
        async with async_session() as session:
            session.add(account)
            await session.commit()

        context.user_data['account_id'] = account.id

        del context.user_data['account_title']
        await send_response(
            update=update, context=context, response=(
                f'Счёт <b>{account.title}</b> создан с начальной суммой в <b>{amount} {currency}</b>'
            ),
        )
        if 'last_msg' in context.user_data:
            del context.user_data['last_msg']
        return await cls.create_entry__choose_category(update, context)

    @classmethod
    async def create_category(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = await get_user_id(update, context)
        title = update.message.text

        category = CategoryModel(title=title, user_id=user_id)
        async with async_session() as session:
            session.add(category)
            await session.commit()

        await send_response(update=update, context=context, response=f'Категория <b>{category.title}</b> создана')
        return await cls.create_entry__category_account_check(update, context)

    @staticmethod
    def _prepare_entry_amount(amount_str: str) -> Tuple[Optional[Decimal], Optional[str]]:
        title = None
        if amount_str.count(' ') == 1:
            amount, title = amount_str.split(' ', 1)
        elif amount_str.count('\n') == 1:
            amount, title = amount_str.split('\n', 1)
        else:
            amount = amount_str
        amount = amount.strip().replace('-', '')
        return user_amount_to_db_amount(amount), title
