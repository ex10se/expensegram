from typing import Optional, Union

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Category(models.Model):
    title = models.CharField('Заголовок', max_length=255, unique=True, db_index=True)


class Subcategory(models.Model):
    title = models.CharField('Заголовок', max_length=255)
    category = models.ForeignKey(Category, related_name='subcategories', on_delete=models.CASCADE)

    class Meta:
        unique_together = (
            ('title', 'category'),
        )


class Currency(models.Model):
    title = models.CharField('Заголовок', max_length=255)
    designation = models.CharField('Обозначение', max_length=3, unique=True)


class Account(models.Model):
    title = models.CharField('Заголовок', max_length=255)
    currency = models.ForeignKey(Currency, related_name='accounts', on_delete=models.CASCADE)
    amount = models.DecimalField('Денежная сумма', max_digits=16, decimal_places=2)
    user = models.ForeignKey(User, related_name='accounts', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = (
            ('title', 'currency'),
        )


class Entry(models.Model):
    title = models.CharField('Заголовок', max_length=255)
    desc = models.TextField('Описание', null=True, blank=True)
    amount = models.DecimalField('Денежная сумма', max_digits=16, decimal_places=2)
    category = models.ForeignKey(Category, related_name='items', on_delete=models.CASCADE)
    subcategory = models.ForeignKey(Subcategory, related_name='items', on_delete=models.CASCADE, null=True, blank=True)
    account = models.ForeignKey(Account, related_name='items', on_delete=models.CASCADE)
    date_created = models.DateTimeField('Дата записи', auto_now_add=True)
    date_updated = models.DateTimeField('Дата изменения записи', auto_now=True)

    def save(self, *args, **kwargs):
        """Перехват create для пересчета суммы на счете."""
        if self.pk is None:
            account = self.account
            account.amount += self.amount
            account.save(update_fields=['amount'])
        return super().save(*args, **kwargs)


class MessageMap(models.Model):
    db_value = models.CharField('Истинное значение в БД', max_length=255)
    alias = models.CharField('Присвоенное значение', max_length=255)

    class Meta:
        unique_together = (
            ('db_value', 'alias'),
        )
        db_table = 'bot_message_map'

    def find(self) -> Optional[Union[Subcategory, Category, Account]]:
        """Поиск инстанса по БД."""
        subcategory = Subcategory.objects.filter(title=self.db_value).first()
        if subcategory is not None:
            return subcategory
        category = Category.objects.filter(title=self.db_value).first()
        if category is not None:
            return category
        account = Account.objects.filter(title=self.db_value).first()
        if account is not None:
            return account


class Transfer(models.Model):
    amount_from = models.DecimalField('Сумма переведенная', max_digits=16, decimal_places=2, default=Decimal('0'))
    amount_to = models.DecimalField('Сумма полученная', max_digits=16, decimal_places=2, default=Decimal('0'))
    account_from = models.ForeignKey(Account, related_name='transfers_from', on_delete=models.CASCADE)
    account_to = models.ForeignKey(Account, related_name='transfers_to', on_delete=models.CASCADE)
    date_created = models.DateTimeField('Дата записи', auto_now_add=True)
    date_updated = models.DateTimeField('Дата изменения записи', auto_now=True)

    def save(self, *args, **kwargs):
        """Перехват create для пересчета суммы на счетах."""
        if self.pk is None:
            account_from = self.account_from
            account_to = self.account_to
            account_from.amount -= self.amount_from
            account_to.amount += self.amount_to
            account_from.save(update_fields=['amount'])
            account_to.save(update_fields=['amount'])
        return super().save(*args, **kwargs)
