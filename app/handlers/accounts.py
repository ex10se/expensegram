from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

from common import constants
from common.constants import COMMAND_CANCEL, COMMAND_ACCOUNTS
from common.utils import (
    get_user_id,
    cancel,
    force_int,
    send_response,
    edit_last_message,
    delete_last_message,
    close,
    flush_user_data, user_amount_to_db_amount,
)
from db import AccountModel
from db.base import async_session


class Accounts:

    STATE__CREATE__TITLE = 0
    STATE__CREATE = 1
    STATE__SHOW_ACCOUNT_ACTIONS = 2
    STATE__CHOOSE_ACCOUNT_ACTION = 3
    STATE__EDIT = 4
    STATE__DELETE_CONFIRM = 5

    ACTION__ADD = 'Добавить'
    ACTION__CLOSE = 'Закрыть'
    ACTION__DELETE = 'Удалить'
    ACTION__BACK = 'Назад'
    ACTION__EDIT = 'Изменить'

    BAD_WORDS = [
        ACTION__ADD,
        ACTION__CLOSE,
        ACTION__DELETE,
        ACTION__BACK,
        ACTION__EDIT,
        f'/{COMMAND_CANCEL}'
    ]

    @classmethod
    def handler(cls):

        return ConversationHandler(
            entry_points=[CommandHandler(COMMAND_ACCOUNTS, cls.entrypoint)],
            states={
                cls.STATE__CREATE__TITLE: [
                    MessageHandler(filters.Regex(rf'^/{COMMAND_CANCEL}$'), close),
                    MessageHandler(filters.TEXT, cls.create__title),
                ],
                cls.STATE__CREATE: [
                    MessageHandler(filters.Regex(rf'^/{COMMAND_CANCEL}$'), close),
                    MessageHandler(filters.TEXT, cls.create),
                ],
                cls.STATE__SHOW_ACCOUNT_ACTIONS: [CallbackQueryHandler(cls.show_account_actions)],
                cls.STATE__CHOOSE_ACCOUNT_ACTION: [CallbackQueryHandler(cls.choose_account_action)],
                cls.STATE__DELETE_CONFIRM: [CallbackQueryHandler(cls.delete_confirm)],
                cls.STATE__EDIT: [
                    MessageHandler(filters.Regex(rf'^/{COMMAND_CANCEL}$'), cancel),
                    MessageHandler(filters.TEXT, cls.edit),
                ],
            },
            fallbacks=[CommandHandler(constants.COMMAND_CANCEL, cancel)],
            allow_reentry=True,
        )

    @classmethod
    async def entrypoint(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = await get_user_id(update, context)

        async with async_session() as session:
            accounts = (await session.execute(select(AccountModel).filter_by(user_id=user_id))).scalars().all()

        if not accounts:
            text = (
                'У вас нет счетов, введите название нового, например:\n\n'
                '    <code>Лучший Банк</code>\n'
                '    <code>Наличка</code>\n\n'
                '(/cancel для отмены)'
            )
            msg = await send_response(update=update, context=context, response=text)
            context.user_data['msg'] = msg
            return cls.STATE__CREATE__TITLE

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
        msg = await send_response(
            update=update, context=context, response='Выберите счёт', reply_markup=reply_markup,
        )
        context.user_data['msg'] = msg
        return cls.STATE__SHOW_ACCOUNT_ACTIONS

    @classmethod
    async def create__title(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        context.user_data['title'] = title

        text = (
            f'Введите начальную сумму счёта <b>{title}</b> с обозначением валюты через пробел, например:\n\n'
            '   <code>0 руб</code>\n'
            '   <code>300 $</code>\n'
            '   <code>10к тенге</code>\n'
            '   <code>3kk сум</code>\n\n'
            '(/cancel для отмены)'
        )
        await send_response(update=update, context=context, response=text)

        return cls.STATE__CREATE

    @classmethod
    async def create(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = await get_user_id(update, context)
        message = update.message.text
        if message.count(' ') != 1:
            await send_response(update=update, context=context, response='Неверный формат ввода')
            return await cls.create__title(update, context)
        amount, currency = update.message.text.split(' ')
        amount = user_amount_to_db_amount(amount)
        title = context.user_data['title']

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

        await send_response(
            update=update, context=context, response=(
                f'Счёт <b>{account.title}</b> создан с начальной суммой в <b>{amount} {currency}</b>'
            ),
        )
        await flush_user_data(update, context)
        return await cls.entrypoint(update, context)

    @classmethod
    async def show_account_actions(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()

        query_data = update.callback_query.data
        if query_data == cls.ACTION__CLOSE:
            await close(update, context)
            return ConversationHandler.END
        if query_data == cls.ACTION__ADD:
            text = (
                'Введите название нового счёта, например:\n\n'
                '    <code>Лучший Банк</code>\n'
                '    <code>Наличка</code>\n\n'
                '(/cancel для отмены)'
            )
            await edit_last_message(update, text)
            return cls.STATE__CREATE__TITLE

        account_id = force_int(query_data)
        context.user_data['account_id'] = account_id
        account_title = context.user_data['accounts'][account_id].title
        context.user_data['account_title'] = account_title

        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(cls.ACTION__DELETE, callback_data=cls.ACTION__DELETE),
                    InlineKeyboardButton(cls.ACTION__BACK, callback_data=cls.ACTION__BACK),
                ],
                [
                    InlineKeyboardButton(cls.ACTION__CLOSE, callback_data=cls.ACTION__CLOSE),
                    InlineKeyboardButton(cls.ACTION__EDIT, callback_data=cls.ACTION__EDIT),
                ],
            ],
        )

        await edit_last_message(
            update=update,
            text=f'Выберите действие над счётом <b>{account_title}</b>',
            reply_markup=reply_markup,
        )
        return cls.STATE__CHOOSE_ACCOUNT_ACTION

    @classmethod
    async def choose_account_action(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        query_data = update.callback_query.data
        account_title = context.user_data['account_title']

        if query_data == cls.ACTION__BACK:
            await delete_last_message(update)
            return await cls.entrypoint(update, context)

        if query_data == cls.ACTION__CLOSE:
            await delete_last_message(update)
            return ConversationHandler.END

        if query_data == cls.ACTION__DELETE:
            keyboard = [
                [InlineKeyboardButton('Удалить вместе с записями', callback_data=cls.ACTION__DELETE)],
                [
                    InlineKeyboardButton(cls.ACTION__CLOSE, callback_data=cls.ACTION__CLOSE),
                    InlineKeyboardButton(cls.ACTION__BACK, callback_data=cls.ACTION__BACK),
                ],
            ]

            await edit_last_message(
                update=update,
                text=(
                    f'Вы уверены, что хотите удалить счёт <b>{account_title}</b>? '
                    'Это удалит также и все записи по нему'
                ),
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return cls.STATE__DELETE_CONFIRM

        if query_data == cls.ACTION__EDIT:
            await edit_last_message(
                update=update,
                text=f'Введите новое название для счёта <b>{account_title}</b> (/cancel для отмены):',
            )
            return cls.STATE__EDIT

    @classmethod
    async def delete_confirm(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        query_data = update.callback_query.data

        if query_data == cls.ACTION__DELETE:
            await delete_last_message(update)
            return await cls.delete(update, context)
        if query_data == cls.ACTION__BACK:
            await delete_last_message(update)
            return await cls.entrypoint(update, context)
        if query_data == cls.ACTION__CLOSE:
            await delete_last_message(update)
            return ConversationHandler.END

    @classmethod
    async def delete(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        account_id = context.user_data['account_id']
        account_title = context.user_data['account_title']

        async with async_session() as session:
            account = (await session.execute(select(AccountModel).filter_by(id=account_id))).scalars().one()
            await session.delete(account)
            await session.commit()

        await flush_user_data(update, context)
        await send_response(update=update, context=context, response=f'Счёт <b>{account_title}</b> удалён')
        return await cls.entrypoint(update, context)

    @classmethod
    async def edit(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        account_id = context.user_data['account_id']
        old_title = context.user_data['account_title']
        new_title = update.message.text.capitalize()
        existing_titles_lower = (c.title.lower() for c in context.user_data['accounts'].values())

        if new_title.startswith('/'):
            await send_response(update=update, context=context, response='Название нельзя начинать с /')
            return await cls.entrypoint(update, context)
        elif new_title == old_title:
            await send_response(update=update, context=context, response='Название не отличается от предыдущего')
            return await cls.entrypoint(update, context)
        elif new_title.capitalize() in cls.BAD_WORDS:
            await send_response(update=update, context=context, response='Такое название нельзя использовать')
            return await cls.entrypoint(update, context)
        elif new_title.lower() in existing_titles_lower:
            await send_response(
                update=update, context=context, response=f'Счёт <b>{new_title}</b> уже есть',
            )
            return await cls.entrypoint(update, context)

        async with async_session() as session:
            account = (await session.execute(select(AccountModel).filter_by(id=account_id))).scalars().one()
            account.title = new_title
            session.add(account)
            await session.commit()

        await flush_user_data(update, context)
        await send_response(
            update=update,
            context=context,
            response=f'Счёт <b>{old_title}</b> теперь имеет имя <b>{new_title}</b>',
        )
        return await cls.entrypoint(update, context)
