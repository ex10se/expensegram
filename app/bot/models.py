from django.db import models


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


class MessageMap(models.Model):
    db_value = models.CharField('Истинное значение в БД', max_length=255)
    alias = models.CharField('Присвоенное значение', max_length=255)

    class Meta:
        unique_together = (
            ('db_value', 'alias'),
        )
        db_table = 'bot_message_map'
