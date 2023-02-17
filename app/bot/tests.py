from typing import Optional

from _decimal import Decimal
from asgiref.sync import async_to_sync
from django.test import TestCase
from django.utils import timezone
from telegram import (
    Update,
    Message,
    Chat,
)
# noinspection PyProtectedMember
from telegram._user import User as TGUser

from bot.exceptions import (
    CantRecognizeAmountError,
    CantFindAccountError,
    CantFindCategoryError,
    TooBigAmountError,
)
from bot.handlers import handle_message, account_list
from bot.handlers.entry import (
    amount_to_decimal,
    find_account,
    resolve_desc,
    handle_entry_message,
    handle_transfer_message,
)
from bot.models import (
    Entry,
    Category,
    Subcategory,
    Account,
    MessageMap,
    Transfer,
)


class TestBot(TestCase):
    """Тесты функционала приложения bot."""

    fixtures = [
        'fixtures/categories.json',
        'fixtures/subcategories.json',
        'fixtures/currencies.json',
        'fixtures/message_maps.json',
        'fixtures/test.json',
    ]

    def setUp(self):
        self.test_entry = Entry(
            title='тест',
            desc='хлам',
            amount=Decimal('-100'),
            category=Category.objects.get(title='Еда'),
            subcategory=Subcategory.objects.get(title='Рестораны'),
            account=Account.objects.get(title='Сбербанк'),
        )
        self.tg_user = TGUser(
            id=1, first_name='test_name', last_name='test_lname', username='test_user', is_bot=False,
        )

    @staticmethod
    def _get_update_obj(message: str = '', user: Optional[TGUser] = None) -> Update:
        msg_kwargs = {
            'message_id': 0,
            'chat': Chat(id=0, type=''),
            'date': timezone.now(),
            'text': message,
        }
        if user:
            msg_kwargs['from_user'] = user
        return Update(update_id=0, message=Message(**msg_kwargs))

    def test_add_delete_entry(self):
        self.assertEqual(self.test_entry.account.amount, Decimal('1000'))
        self.test_entry.save()
        self.assertEqual(self.test_entry.account.amount, Decimal('900'))
        self.test_entry.delete()
        self.assertEqual(Entry.objects.count(), 0)
        self.assertEqual(self.test_entry.account.amount, Decimal('1000'))

    def test_message_map_find_value(self):
        instance = MessageMap.objects.get(alias='доставка').find()
        self.assertTrue(isinstance(instance, Subcategory))

        instance = MessageMap.objects.get(alias='музей').find()
        self.assertTrue(isinstance(instance, Category))

        instance = MessageMap.objects.get(alias='сбер').find()
        self.assertTrue(isinstance(instance, Account))

    def test_transfer(self):
        Transfer.objects.create(
            account_from=Account.objects.get(title='Тинькофф Блэк'),
            account_to=Account.objects.get(title='Сбербанк'),
            amount_from=Decimal('500'),
            amount_to=Decimal('500'),
        )
        self.assertEqual(Account.objects.get(title='Тинькофф Блэк').amount, Decimal('55.20'))
        self.assertEqual(Account.objects.get(title='Сбербанк').amount, Decimal('1500'))

    def test_handle_message__entry(self):
        with self.subTest('Тестирование entry'):
            self.assertEqual(Account.objects.get(title='Тинькофф Блэк').amount, Decimal('555.20'))
            async_to_sync(handle_message)(self._get_update_obj('-0,5k блэк доставка'))
            self.assertEqual(Account.objects.get(title='Тинькофф Блэк').amount, Decimal('55.20'))
        with self.subTest('Тестирование entry: указана категория вместо алиаса'):
            async_to_sync(handle_message)(self._get_update_obj('-1,5k блэк помощь'))
        with self.subTest('Тестирование entry: указана подкатегория вместо алиаса'):
            async_to_sync(handle_message)(self._get_update_obj('-1,5k блэк рестораны'))
        with self.subTest('Тестирование entry: указана аккаунт вместо алиаса'):
            async_to_sync(handle_message)(self._get_update_obj('-1,5k Сбербанк доставка'))

    def test_handle_message__transfer(self):
        self.assertEqual(Account.objects.get(title='Тинькофф Блэк').amount, Decimal('555.20'))
        self.assertEqual(Account.objects.get(title='Сбербанк').amount, Decimal('1000'))
        async_to_sync(handle_message)(self._get_update_obj('1к сбер блэк'))
        self.assertEqual(Account.objects.get(title='Тинькофф Блэк').amount, Decimal('1555.20'))
        self.assertEqual(Account.objects.get(title='Сбербанк').amount, Decimal('0'))

    def test_handle_entry_message(self):
        with self.subTest('entry: Указана слишком большая сумма'):
            with self.assertRaises(TooBigAmountError):
                handle_entry_message(amount='-100kkkkkkkkkkk', account=find_account('сбер'), desc='доставка'),

    def test_handle_transfer_message(self):
        with self.subTest('transfer: Указана слишком большая сумма'):
            with self.assertRaises(TooBigAmountError):
                handle_transfer_message(
                    account_alias_from='блэк', account_alias_to='сбер', amount_from='100kkkkkkkkkkk',
                )

    def test_amount_to_decimal_negative(self):
        with self.assertRaises(CantRecognizeAmountError):
            amount_to_decimal('qpwekjq')

    def test_find_account_negative(self):
        MessageMap.objects.create(alias='test', db_value='qweqweqweqwr')
        with self.assertRaises(CantFindAccountError):
            find_account('test')
        with self.assertRaises(CantFindAccountError):
            find_account('test22')

    def test_resolve_desc_negative(self):
        with self.assertRaises(CantFindCategoryError):
            resolve_desc('qpwekjq')

    def test_account_list(self):
        send_args = async_to_sync(account_list)(update=self._get_update_obj(user=self.tg_user))
        self.assertEqual(send_args['text'], '<b>1.</b> Сбербанк 1000.00 RUB\n<b>2.</b> Тинькофф Блэк 555.20 RUB\n')
