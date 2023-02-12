from typing import Type

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from bot.models import Entry


# noinspection PyUnusedLocal
@receiver(pre_delete, sender=Entry)
def return_amount(sender: Type[Entry], instance: Entry, **kwargs):
    """Возврат суммы при удалении записи дохода/расхода."""
    account = instance.account
    account.amount -= instance.amount
    account.save(update_fields=['amount'])
