from decimal import Decimal
from typing import Tuple, Optional

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Message
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from common import constants
from common.constants import COMMAND_CANCEL, COMMAND_ADD
from common.utils import (
    cancel,
    send_response,
    delete_last_message,
    get_user_id,
    user_amount_to_db_amount,
    edit_last_message, flush_user_data,
)
from db import CategoryModel, AccountModel, EntryModel, TransferModel
from db.base import async_session


class Add:

    STATE__CREATE_ENTRY__CATEGORY_ACCOUNT_CHECK = 0
    STATE__CREATE_ENTRY__CHOOSE_ACCOUNT = 1
    STATE__CREATE_ENTRY__ENTER_AMOUNT = 2
    STATE__CREATE_ENTRY = 3
    STATE__CREATE_TRANSFER__CHOOSE_ACCOUNT_TO = 4
    STATE__CREATE_TRANSFER__ENTER_AMOUNT = 5
    STATE__CREATE_TRANSFER = 6

    STAGE__CREATE_CATEGORY = 20

    STATE__CREATE_ACCOUNT__TITLE = 30
    STATE__CREATE_ACCOUNT = 31

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
                cls.STATE__CREATE_ENTRY__CATEGORY_ACCOUNT_CHECK: [
                    CallbackQueryHandler(cls.create_transfer__choose_account_from, pattern=cls.ACTION__TRANSFER),
                    CallbackQueryHandler(cls.create_entry__remember_entry_type),
                ],
                cls.STATE__CREATE_ENTRY__CHOOSE_ACCOUNT: [CallbackQueryHandler(cls.create_entry__choose_account)],
                cls.STATE__CREATE_ENTRY__ENTER_AMOUNT: [CallbackQueryHandler(cls.create_entry__enter_amount)],
                cls.STATE__CREATE_ENTRY: [
                    MessageHandler(filters.Regex(rf'^/{COMMAND_CANCEL}$'), cancel),
                    MessageHandler(filters.TEXT, cls.create_entry),
                ],
                cls.STAGE__CREATE_CATEGORY: [
                    MessageHandler(filters.Regex(rf'^/{COMMAND_CANCEL}$'), cancel),
                    MessageHandler(filters.TEXT, cls.create_category),
                ],
                cls.STATE__CREATE_ACCOUNT__TITLE: [
                    MessageHandler(filters.Regex(rf'^/{COMMAND_CANCEL}$'), cancel),
                    MessageHandler(filters.TEXT, cls.create_account__title),
                ],
                cls.STATE__CREATE_ACCOUNT: [
                    MessageHandler(filters.Regex(rf'^/{COMMAND_CANCEL}$'), cancel),
                    MessageHandler(filters.TEXT, cls.create_account),
                ],
                cls.STATE__CREATE_TRANSFER__CHOOSE_ACCOUNT_TO: [
                    CallbackQueryHandler(cls.create_transfer__choose_account_to),
                ],
                cls.STATE__CREATE_TRANSFER__ENTER_AMOUNT: [
                    CallbackQueryHandler(cls.create_transfer__enter_amount),
                ],
                cls.STATE__CREATE_TRANSFER: [
                    MessageHandler(filters.Regex(rf'^/{COMMAND_CANCEL}$'), cancel),
                    MessageHandler(filters.TEXT, cls.create_transfer),
                ],
            },
            fallbacks=[CommandHandler(constants.COMMAND_CANCEL, cancel)],
            allow_reentry=True,
        )

    @classmethod
    async def entrypoint(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = await get_user_id(update, context)

        upper_buttons = [InlineKeyboardButton(cls.ACTION__CLOSE, callback_data=cls.ACTION__CLOSE)]
        async with async_session() as session:
            accounts_count = (
                await session.execute(select(func.count()).select_from(AccountModel).filter_by(user_id=user_id))
            ).scalar_one()
        if accounts_count >= 2:
            upper_buttons.insert(0, InlineKeyboardButton(cls.ACTION__TRANSFER, callback_data=cls.ACTION__TRANSFER))

        reply_markup = InlineKeyboardMarkup([
            upper_buttons,
            [
                InlineKeyboardButton(cls.ACTION__INCOME, callback_data=cls.ACTION__INCOME),
                InlineKeyboardButton(cls.ACTION__EXPENSE, callback_data=cls.ACTION__EXPENSE),
            ],
        ])
        msg = await send_response(
            update=update, context=context, response='Выберите тип записи', reply_markup=reply_markup,
        )
        context.user_data['last_msg'] = msg
        return cls.STATE__CREATE_ENTRY__CATEGORY_ACCOUNT_CHECK

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
            return cls.STATE__CREATE_ACCOUNT__TITLE
        accounts = {account.id: account for account in accounts}
        context.user_data['accounts'] = accounts
        # распределяем кнопки по 2 в ряд
        keyboard_map = []
        for i, account in enumerate(accounts.values()):
            button = InlineKeyboardButton(
                f'{account.title} ({account.amount} {account.currency})', callback_data=account.id,
            )
            if not i % 2:
                keyboard_map.append([button])
            else:
                keyboard_map[-1].append(button)

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(cls.ACTION__ADD, callback_data=cls.ACTION__ADD)],
            [InlineKeyboardButton(cls.ACTION__CLOSE, callback_data=cls.ACTION__CLOSE)],
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
        return cls.STATE__CREATE_ENTRY__CHOOSE_ACCOUNT

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
            return cls.STATE__CREATE_ACCOUNT__TITLE

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
            [InlineKeyboardButton(cls.ACTION__ADD, callback_data=cls.ACTION__ADD)],
            [InlineKeyboardButton(cls.ACTION__CLOSE, callback_data=cls.ACTION__CLOSE)],
            *keyboard_map,
        ])

        if 'accounts' not in context.user_data:
            async with async_session() as session:
                accounts = (await session.execute(select(AccountModel).filter_by(user_id=user_id))).scalars().all()
            if not accounts:
                text = 'У вас нет ни одного счёта, введите название нового (/cancel для отмены):'
                await edit_last_message(update=update, text=text)
                return cls.STATE__CREATE_ACCOUNT__TITLE
            accounts = {account.id: account for account in accounts}
            context.user_data['accounts'] = accounts

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
        return cls.STATE__CREATE_ENTRY__ENTER_AMOUNT

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
        account_title = context.user_data['accounts'][context.user_data['account_id']].title
        await edit_last_message(
            update=update,
            text=(
                f'Введите сумму %s на <b>{category_title}</b> со счёта <b>{account_title}</b> '
                'с заметкой, если нужно, по следующим примерам:\n\n'
                '    <code>100</code>\n'
                '    <code>10k</code>\n'
                '    <code>1,5к</code>\n'
                '    <code>100к работа</code>\n'
                '    <code>100\n  вода</code>\n\n'
                '/cancel для отмены' % entry_type_str
            ),
        )

        return cls.STATE__CREATE_ENTRY

    @classmethod
    async def create_entry(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
                f'составляет {account.amount} {account.currency}.\n\n'
                f'/{COMMAND_ADD} - повторить'
            ),
        )
        return ConversationHandler.END

    @classmethod
    async def create_account__title(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        title = update.message.text
        existing_titles_lower = []
        if 'accounts' in context.user_data:
            existing_titles_lower = [c.title.lower() for c in context.user_data['accounts'].values()]

        if title.startswith('/'):
            await send_response(update=update, context=context, response='Название нельзя начинать с /')
            return await cls.entrypoint(update, context)
        elif title.capitalize() in cls.BAD_WORDS:
            await send_response(update=update, context=context, response='Такое название нельзя использовать')
            return await cls.entrypoint(update, context)
        elif title.lower() in existing_titles_lower:
            await send_response(update=update, context=context, response=f'Счёт <b>{title}</b> уже есть')
            return await cls.entrypoint(update, context)

        context.user_data['account_title'] = title

        text = (
            f'Введите начальную сумму счёта <b>{title}</b> с обозначением валюты через пробел, например:\n\n'
            '   <code>0 руб</code>\n'
            '   <code>300 $</code>\n'
            '   <code>10к тенге</code>\n'
            '   <code>3kk сум</code>\n\n'
            '(/cancel для отмены)'
        )
        await send_response(update=update, context=context, response=text)

        return cls.STATE__CREATE_ACCOUNT

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
            try:
                session.add(account)
                await session.commit()
            except IntegrityError:
                await send_response(
                    update=update,
                    context=context,
                    response=f'Счёт <b>{title}</b> уже есть',
                )
                await flush_user_data(update, context)
                return await cls.entrypoint(update, context)

        context.user_data['account_id'] = account.id
        await flush_user_data(update, context, exclude=['account_id', 'entry_type'])
        await send_response(
            update=update, context=context, response=(
                f'Счёт <b>{account.title}</b> создан с начальной суммой в <b>{amount} {currency}</b>'
            ),
        )
        return await cls.create_entry__choose_category(update, context)

    @classmethod
    async def create_category(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = await get_user_id(update, context)
        title = update.message.text

        category = CategoryModel(title=title, user_id=user_id)
        async with async_session() as session:
            try:
                session.add(category)
                await session.commit()
            except IntegrityError:
                await send_response(
                    update=update,
                    context=context,
                    response=f'Категория <b>{title}</b> уже есть',
                )
                await flush_user_data(update, context)
                return await cls.entrypoint(update, context)

        await send_response(update=update, context=context, response=f'Категория <b>{category.title}</b> создана')
        return await cls.create_entry__category_account_check(update, context)

    @classmethod
    async def create_transfer__choose_account_from(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = await get_user_id(update, context)
        await update.callback_query.answer()

        async with async_session() as session:
            accounts = (await session.execute(select(AccountModel).filter_by(user_id=user_id))).scalars().all()
        accounts = {account.id: account for account in accounts}
        context.user_data['accounts'] = accounts
        # распределяем кнопки по 2 в ряд
        keyboard_map = []
        for i, account in enumerate(accounts.values()):
            button = InlineKeyboardButton(
                f'{account.title} ({account.amount} {account.currency})', callback_data=account.id,
            )
            if not i % 2:
                keyboard_map.append([button])
            else:
                keyboard_map[-1].append(button)

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(cls.ACTION__CLOSE, callback_data=cls.ACTION__CLOSE)],
            *keyboard_map,
        ])
        await edit_last_message(
            update=update,
            text='Выберите счёт списания',
            reply_markup=reply_markup,
        )
        return cls.STATE__CREATE_TRANSFER__CHOOSE_ACCOUNT_TO

    @classmethod
    async def create_transfer__choose_account_to(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()

        query_data = update.callback_query.data
        if query_data == cls.ACTION__CLOSE:
            await delete_last_message(update)
            return ConversationHandler.END

        account_id_from = int(query_data)
        context.user_data['account_id_from'] = account_id_from
        accounts = {k: v for k, v in context.user_data['accounts'].items() if k != account_id_from}

        # распределяем кнопки по 2 в ряд
        keyboard_map = []
        for i, account in enumerate(accounts.values()):
            button = InlineKeyboardButton(
                f'{account.title} ({account.amount} {account.currency})', callback_data=account.id,
            )
            if not i % 2:
                keyboard_map.append([button])
            else:
                keyboard_map[-1].append(button)

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(cls.ACTION__CLOSE, callback_data=cls.ACTION__CLOSE)],
            *keyboard_map,
        ])
        await edit_last_message(
            update=update,
            text='Выберите счёт зачисления',
            reply_markup=reply_markup,
        )
        return cls.STATE__CREATE_TRANSFER__ENTER_AMOUNT

    @classmethod
    async def create_transfer__enter_amount(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()

        query_data = update.callback_query.data
        if query_data == cls.ACTION__CLOSE:
            await delete_last_message(update)
            return ConversationHandler.END

        context.user_data['account_id_to'] = int(query_data)

        account_title_from = context.user_data['accounts'][context.user_data['account_id_from']].title
        account_title_to = context.user_data['accounts'][context.user_data['account_id_to']].title

        text = (
            f'Введите сумму списания со счёта <b>{account_title_from}</b> '
            f'(и, если отличается, сумму начисления на счёт <b>{account_title_to}</b>) в следующем формате:\n\n'
            '    <code>100</code>\n'
            '    <code>10к 131,55</code>\n'
            '    <code>200k 29.8kk</code>\n\n'
            '(/cancel для отмены)'
        )
        await edit_last_message(
            update=update,
            text=text,
        )
        return cls.STATE__CREATE_TRANSFER

    @classmethod
    async def create_transfer(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        amount_from, amount_to = cls._prepare_transfer_amount(update.message.text)
        if amount_from is None or amount_to is None:
            await send_response(update=update, context=context, response='Неверный формат ввода')
            return await cls.entrypoint(update, context)

        user_id = await get_user_id(update, context)
        account_id_from = context.user_data['account_id_from']
        account_id_to = context.user_data['account_id_to']
        account_from = context.user_data['accounts'][account_id_from]
        account_to = context.user_data['accounts'][account_id_to]

        transfer = TransferModel(
            amount_from=amount_from,
            amount_to=amount_to,
            account_from_id=account_id_from,
            account_to_id=account_id_to,
            user_id=user_id,
        )
        async with async_session() as session:
            account_from.amount -= amount_from
            account_to.amount += amount_to
            session.add(account_from)
            session.add(account_to)
            session.add(transfer)
            await session.commit()

        await send_response(
            update=update,
            context=context,
            response=(
                'Запись добавлена, теперь баланс составляет\n'
                f'- <b>{account_from.title}</b> {account_from.amount} {account_from.currency}\n'
                f'- <b>{account_to.title}</b> {account_to.amount} {account_to.currency}'
            ),
        )
        return ConversationHandler.END

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

    @staticmethod
    def _prepare_transfer_amount(amount_str: str) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        if amount_str.count(' ') == 1:
            amount_from, amount_to = amount_str.split(' ', 1)
        elif amount_str.count('\n') == 1:
            amount_from, amount_to = amount_str.split('\n', 1)
        else:
            amount_from, amount_to = amount_str, amount_str
        amount_from = amount_from.strip().replace('-', '')
        amount_to = amount_to.strip().replace('-', '')
        return user_amount_to_db_amount(amount_from), user_amount_to_db_amount(amount_to)
