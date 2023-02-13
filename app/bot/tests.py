from _decimal import Decimal

from django.test import TestCase

from bot.models import Entry, Category, Subcategory, Account, MessageMap, Transfer


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

    def test_add_entry(self):
        self.test_entry.save()
        self.assertEqual(Entry.objects.count(), 1)

    def test_delete_entry(self):
        self.test_entry.save()
        self.assertEqual(self.test_entry.account.amount, Decimal('1000'))
        self.test_entry.delete()
        self.assertEqual(Entry.objects.count(), 0)
        self.assertEqual(self.test_entry.account.amount, Decimal('1100'))

    def test_message_map_find_value(self):
        instance = MessageMap.objects.get(alias='доставка').find()
        self.assertTrue(isinstance(instance, Subcategory))

        instance = MessageMap.objects.get(alias='музей').find()
        self.assertTrue(isinstance(instance, Category))

        instance = MessageMap.objects.get(alias='сбер').find()
        self.assertTrue(isinstance(instance, Account))

    def test_transfer(self):
        Transfer.objects.create(
            account_from=Account.objects.get(title='Тинькофф'),
            account_to=Account.objects.get(title='Сбербанк'),
            amount=Decimal('500'),
        )
        self.assertEqual(Account.objects.get(title='Тинькофф').amount, Decimal('55.20'))
        self.assertEqual(Account.objects.get(title='Сбербанк').amount, Decimal('1500'))
