from django.db.models.signals import pre_delete
from django.dispatch import receiver

from bot.models import Entry


@receiver(pre_delete, sender=Entry)
def return_amount(sender: Entry):
    """Возврат суммы при удалении записи дохода/расхода."""
    account = sender.account
    account.amount -= sender.amount
    account.save(update_fields=['amount'])
