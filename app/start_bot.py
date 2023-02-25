import logging
import traceback

from telegram import Message
from telegram.ext import ApplicationBuilder, CommandHandler

import handlers
from common import constants
from common.utils import send_response, cancel
from config import settings

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


async def error_handler(update, context) -> Message:
    """DEBUG"""
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ("".join(tb_list)).replace('<', '[').replace('>', ']')
    return await send_response(update=update, context=context, response=tb_string)


if __name__ == '__main__':
    application = ApplicationBuilder().token(settings.BOT_TOKEN).build()

    application.add_handler(CommandHandler(constants.COMMAND_START, handlers.start))
    # application.add_handler(CommandHandler(constants.COMMAND_CANCEL, cancel))
    application.add_handler(CommandHandler(constants.COMMAND_HELP, handlers.help_))

    application.add_handler(handlers.Add.handler())
    application.add_handler(handlers.Categories.handler())
    application.add_handler(handlers.Accounts.handler())

    # application.add_error_handler(error_handler)

    application.run_polling()
