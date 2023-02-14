from decimal import Decimal
from typing import (
    Optional,
    Union,
)

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.functions import Lower

User = get_user_model()


class CustomModelManager(models.Manager):
    """Дополненный методами Manager."""
    def title_lower(self, title: str) -> models.QuerySet:
        return self.annotate(title__lower=Lower('title')).filter(title__lower=title)


class Category(models.Model):
    title = models.CharField('Заголовок', max_length=255, unique=True, db_index=True)

    objects = CustomModelManager()

    def __str__(self):
        return self.title


class Subcategory(models.Model):
    title = models.CharField('Заголовок', max_length=255)
    category = models.ForeignKey(Category, related_name='subcategories', on_delete=models.CASCADE)

    objects = CustomModelManager()

    def __str__(self):
        return f'{self.category}.{self.title}'

    class Meta:
        unique_together = (
            ('title', 'category'),
        )


class Currency(models.Model):
    title = models.CharField('Заголовок', max_length=255)
    designation = models.CharField('Обозначение', max_length=3, unique=True)

    def __str__(self):
        return f'{self.title} ({self.designation})'


class Account(models.Model):
    title = models.CharField('Заголовок', max_length=255)
    currency = models.ForeignKey(Currency, related_name='accounts', on_delete=models.CASCADE)
    amount = models.DecimalField('Денежная сумма', max_digits=16, decimal_places=2)
    user = models.ForeignKey(User, related_name='accounts', on_delete=models.CASCADE, null=True, blank=True)

    objects = CustomModelManager()

    def __str__(self):
        return f'{self.title} ({self.id})'

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

    def find_category(self) -> Optional[Category]:
        return Category.objects.filter(title=self.db_value).first()

    def find_subcategory(self) -> Optional[Subcategory]:
        return Subcategory.objects.filter(title=self.db_value).first()

    def find_account(self) -> Optional[Account]:
        return Account.objects.filter(title=self.db_value).first()

    def find(self) -> Optional[Union[Subcategory, Category, Account]]:
        """Поиск инстанса по БД."""
        for func in (self.find_category, self.find_subcategory, self.find_account):
            result = func()
            if result is not None:
                return result

    def save(self, *args, **kwargs):
        """Перехват create для изменения регистра алиаса."""
        if self.pk is None:
            self.alias = self.alias.lower()
        return super().save(*args, **kwargs)


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
