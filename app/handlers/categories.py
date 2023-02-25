from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Message
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

from common import constants
from common.constants import COMMAND_CANCEL, COMMAND_CATEGORIES
from common.utils import (
    get_user_id,
    cancel,
    force_int,
    send_response,
    edit_last_message,
    delete_last_message,
    close,
    sep_titles,
    flush_user_data,
)
from db import CategoryModel
from db.base import async_session


class Categories:

    STATE__CREATE = 0
    STATE__SHOW_CATEGORY_ACTIONS = 1
    STATE__CHOOSE_CATEGORY_ACTION = 2
    STATE__EDIT = 3
    STATE__DELETE_CONFIRM = 4

    ACTION__ADD = 'Добавить'
    ACTION__CLOSE = 'Закрыть'
    ACTION__DELETE = 'Удалить'
    ACTION__BACK = 'Назад'
    ACTION__EDIT = 'Изменить'
    ACTION__HIDE = 'Скрыть'
    ACTION__ACTIVATE = 'Показать'

    BAD_WORDS = [
        ACTION__ADD,
        ACTION__CLOSE,
        ACTION__DELETE,
        ACTION__BACK,
        ACTION__EDIT,
        ACTION__HIDE,
        ACTION__ACTIVATE,
        f'/{COMMAND_CANCEL}'
    ]

    @classmethod
    def handler(cls):

        return ConversationHandler(
            entry_points=[CommandHandler(COMMAND_CATEGORIES, cls.entrypoint)],
            states={
                cls.STATE__CREATE: [
                    MessageHandler(filters.Regex(rf'^/{COMMAND_CANCEL}$'), close),
                    MessageHandler(filters.TEXT, cls.create),
                ],
                cls.STATE__SHOW_CATEGORY_ACTIONS: [CallbackQueryHandler(cls.show_category_actions)],
                cls.STATE__CHOOSE_CATEGORY_ACTION: [CallbackQueryHandler(cls.choose_category_action)],
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
            categories = (await session.execute(select(CategoryModel).filter_by(user_id=user_id))).scalars().all()

        if not categories:
            text = (
                'У вас нет категорий, '
                'введите название новой (можно несколько через запятую), '
                'например:\n\n'
                '    <code>Продукты</code>\n'
                '    <code>Счета, Техника, Одежда</code>\n\n'
                '(/cancel для отмены)'
            )
            msg = await send_response(update=update, context=context, response=text)
            context.user_data['msg'] = msg
            return cls.STATE__CREATE

        categories = {category.id: category for category in categories}
        context.user_data['categories'] = categories

        # распределяем кнопки по 2 в ряд
        keyboard_map = []
        for i, category in enumerate(categories.values()):
            if category.disabled:
                title = f'(скрыта) {category.title}'
            else:
                title = category.title
            button = InlineKeyboardButton(title, callback_data=category.id)
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
            update=update, context=context, response='Выберите категорию', reply_markup=reply_markup,
        )
        context.user_data['msg'] = msg
        return cls.STATE__SHOW_CATEGORY_ACTIONS

    @classmethod
    async def create(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = await get_user_id(update, context)

        titles = sep_titles(update.message.text)
        existing_titles_lower = []
        if 'categories' in context.user_data:
            existing_titles_lower = [c.title.lower() for c in context.user_data['categories'].values()]

        titles_in_bad_words = []
        titles_in_existing_titles_lower = []
        error_text = []
        for title in titles:
            if title.capitalize() in cls.BAD_WORDS:
                titles_in_bad_words.append(title)
            elif title.lower() in existing_titles_lower:
                titles_in_existing_titles_lower.append(title)
        if titles_in_bad_words:
            error_text.append(f'Следующие названия нельзя использовать: <b>{", ".join(titles_in_bad_words)}</b>')
        if titles_in_existing_titles_lower:
            error_text.append(f'Следующие категории уже есть: <b>{", ".join(titles_in_existing_titles_lower)}</b>')
        if error_text:
            await send_response(update=update, context=context, response='\n'.join(error_text))
            return await cls.entrypoint(update, context)

        categories = [CategoryModel(title=title, user_id=user_id) for title in titles]

        async with async_session() as session:
            try:
                session.add_all(categories)
                await session.commit()
            except IntegrityError as e:
                bad_category = next(iter(title for title in titles if title in str(e.orig)))
                await send_response(
                    update=update,
                    context=context,
                    response=f'Категория <b>{bad_category}</b> уже есть',
                )
                await flush_user_data(update, context)
                return await cls.entrypoint(update, context)

        await flush_user_data(update, context)
        if len(categories) == 1:
            text = f'Категория <b>{titles[0]}</b> добавлена'
        else:
            categories_list_str = ', '.join(titles)
            text = f'Категории <b>{categories_list_str}</b> добавлены'
        await send_response(update=update, context=context, response=text)
        return await cls.entrypoint(update, context)

    @classmethod
    async def show_category_actions(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()

        query_data = update.callback_query.data
        if query_data == cls.ACTION__CLOSE:
            await close(update, context)
            return ConversationHandler.END
        if query_data == cls.ACTION__ADD:
            text = (
                'Введите название новой категории (можно несколько через запятую), '
                'например:\n\n'
                '    <code>Продукты</code>\n\n'
                '    <code>Счета, Техника, Одежда</code>\n\n'
                '/cancel для отмены'
            )
            await edit_last_message(update, text)
            return cls.STATE__CREATE

        category_id = force_int(query_data)
        context.user_data['category_id'] = category_id
        category_title = context.user_data['categories'][category_id].title
        category_disabled = context.user_data['categories'][category_id].disabled
        context.user_data['category_title'] = category_title
        context.user_data['category_disabled'] = category_disabled

        if category_disabled:
            hide_show_button = InlineKeyboardButton(cls.ACTION__ACTIVATE, callback_data=cls.ACTION__ACTIVATE)
        else:
            hide_show_button = InlineKeyboardButton(cls.ACTION__HIDE, callback_data=cls.ACTION__HIDE)

        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(cls.ACTION__DELETE, callback_data=cls.ACTION__DELETE),
                    hide_show_button,
                    InlineKeyboardButton(cls.ACTION__BACK, callback_data=cls.ACTION__BACK),
                ],
                [
                    InlineKeyboardButton(cls.ACTION__CLOSE, callback_data=cls.ACTION__CLOSE),
                    InlineKeyboardButton(cls.ACTION__EDIT, callback_data=cls.ACTION__EDIT),
                ],
            ],
        )

        msg = await edit_last_message(
            update=update,
            text=f'Выберите действие над категорией <b>{category_title}</b>',
            reply_markup=reply_markup,
        )
        if isinstance(msg, Message):
            context.user_data['msg'] = msg
        return cls.STATE__CHOOSE_CATEGORY_ACTION

    @classmethod
    async def choose_category_action(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        query_data = update.callback_query.data
        category_title = context.user_data['category_title']
        category_disabled = context.user_data['category_disabled']

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
            if category_disabled:
                text = (
                    f'Вы уверены, что хотите удалить категорию <b>{category_title}</b>? '
                    'В данный момент она скрыта и не отображается при добавлении новых записей'
                )
            else:
                keyboard[1].insert(0, InlineKeyboardButton(cls.ACTION__HIDE, callback_data=cls.ACTION__HIDE))
                text = (
                    f'Вы уверены, что хотите удалить категорию <b>{category_title}</b>? '
                    'Это удалит также и все записи по ней. '
                    'Если вы не хотите отображать её при добавлении новых записей, достаточно её скрыть'
                )
            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_last_message(
                update=update,
                text=text,
                reply_markup=reply_markup,
            )
            return cls.STATE__DELETE_CONFIRM

        if query_data == cls.ACTION__HIDE:
            return await cls.hide(update, context)

        if query_data == cls.ACTION__ACTIVATE:
            await delete_last_message(update)
            return await cls.activate(update, context)

        if query_data == cls.ACTION__EDIT:
            await edit_last_message(
                update=update,
                text=f'Введите новое название для категории <b>{category_title}</b> (/cancel для отмены):',
            )
            return cls.STATE__EDIT

    @classmethod
    async def delete_confirm(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        query_data = update.callback_query.data

        if query_data == cls.ACTION__ACTIVATE:
            await delete_last_message(update)
            return await cls.activate(update, context)
        if query_data == cls.ACTION__HIDE:
            await delete_last_message(update)
            return await cls.hide(update, context)
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
        category_id = context.user_data['category_id']
        category_title = context.user_data['category_title']

        async with async_session() as session:
            category = (await session.execute(select(CategoryModel).filter_by(id=category_id))).scalars().one()
            await session.delete(category)
            await session.commit()

        await flush_user_data(update, context)
        await send_response(update=update, context=context, response=f'Категория <b>{category_title}</b> удалена')
        return await cls.entrypoint(update, context)

    @classmethod
    async def activate(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        category_id = context.user_data['category_id']
        category_title = context.user_data['category_title']

        async with async_session() as session:
            category = (await session.execute(select(CategoryModel).filter_by(id=category_id))).scalars().one()
            category.disabled = False
            session.add(category)
            await session.commit()

        await flush_user_data(update, context)
        await send_response(update=update, context=context, response=f'Категория <b>{category_title}</b> активирована')
        return await cls.entrypoint(update, context)

    @classmethod
    async def hide(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        category_id = context.user_data['category_id']
        category_title = context.user_data['category_title']

        async with async_session() as session:
            category = (await session.execute(select(CategoryModel).filter_by(id=category_id))).scalars().one()
            category.disabled = True
            session.add(category)
            await session.commit()

        await flush_user_data(update, context)
        await send_response(update=update, context=context, response=f'Категория <b>{category_title}</b> скрыта')
        return await cls.entrypoint(update, context)

    @classmethod
    async def edit(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        category_id = context.user_data['category_id']
        old_title = context.user_data['category_title']
        new_title = update.message.text.capitalize()
        existing_titles_lower = (c.title.lower() for c in context.user_data['categories'].values())

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
                update=update, context=context, response=f'Категория <b>{new_title}</b> уже есть',
            )
            return await cls.entrypoint(update, context)

        async with async_session() as session:
            category = (await session.execute(select(CategoryModel).filter_by(id=category_id))).scalars().one()
            category.title = new_title
            session.add(category)
            await session.commit()

        await flush_user_data(update, context)
        await send_response(
            update=update,
            context=context,
            response=f'Категория <b>{old_title}</b> теперь имеет имя <b>{new_title}</b>',
        )
        return await cls.entrypoint(update, context)
