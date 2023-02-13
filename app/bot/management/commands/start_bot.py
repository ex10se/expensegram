import logging

from django.core.management import BaseCommand
from telegram.ext import ApplicationBuilder, CommandHandler

from bot import handlers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


COMMAND_HANDLERS = {
    "start": handlers.start,
}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--token', type=str)

    def handle(self, *args, **options):
        token = options.get('token')
        application = ApplicationBuilder().token(token).build()

        for command_name, command_handler in COMMAND_HANDLERS.items():
            application.add_handler(CommandHandler(command_name, command_handler))

        application.run_polling()
