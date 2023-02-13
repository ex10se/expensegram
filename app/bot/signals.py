from typing import Type

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from bot.models import Entry, Transfer


# noinspection PyUnusedLocal
@receiver(pre_delete, sender=Entry)
def entry_return_amount(sender: Type[Entry], instance: Entry, **kwargs):
    """Возврат суммы при удалении записи дохода/расхода."""
    account = instance.account
    account.amount -= instance.amount
    account.save(update_fields=['amount'])


# noinspection PyUnusedLocal
@receiver(pre_delete, sender=Transfer)
def transfer_return_amounts(sender: Type[Transfer], instance: Transfer, **kwargs):
    """Возврат суммы при удалении записи дохода/расхода."""
    account_from = instance.account_from
    account_from.amount += instance.amount_from
    account_from.save(update_fields=['amount'])
    account_to = instance.account_to
    account_to.amount -= instance.amount_to
    account_to.save(update_fields=['amount'])
