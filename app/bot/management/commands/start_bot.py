import logging

from django.core.management import BaseCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from bot import handlers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


COMMAND_HANDLERS = {
    "start": handlers.start,
    "help": handlers.help_,
    "account_list": handlers.account_list,
    # "account_add": handlers.start,
    # "account_delete": handlers.start,
    # "currency_list": handlers.start,
    # "currency_add": handlers.start,
    # "currency_delete": handlers.start,
    # "entry_list": handlers.start,
    # "entry_delete": handlers.start,
    # "transfer_list": handlers.start,
    # "transfer_delete": handlers.start,
    # "category_list": handlers.start,
    # "category_add": handlers.start,
    # "category_delete": handlers.start,
    # "subcategory_list": handlers.start,
    # "subcategory_add": handlers.start,
    # "subcategory_delete": handlers.start,
    # "message_map_list": handlers.start,
    # "message_map_add": handlers.start,
    # "message_map_delete": handlers.start,
}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--token', type=str)

    def handle(self, *args, **options):
        token = options.get('token')
        application = ApplicationBuilder().token(token).build()

        for command_name, command_handler in COMMAND_HANDLERS.items():
            application.add_handler(CommandHandler(command_name, command_handler))

        application.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), handlers.handle_message)
        )

        application.run_polling()
