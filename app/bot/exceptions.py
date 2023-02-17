from typing import Optional


class BaseError(Exception):
    default_message = 'Не могу распознать'

    def __init__(self, message: Optional[str] = None):
        if message is None:
            message = self.default_message
        self.message = message

    def __str__(self):
        return self.message


class WrongPartsCountError(BaseError):
    default_message = (
        'Сообщение должно состоять из трех (для записи) или четырех (для перевода) частей, разделенных пробелом'
    )


class BadFirstCharForEntryError(BaseError):
    default_message = 'Сумма должна начинаться с + или -'


class CantRecognizeAmountError(BaseError):
    default_message = 'Сумма должна быть десятичным числом, в котором можно использовать `k` и `к`'


class CantFindAccountError(BaseError):
    default_message = 'Не могу найти аккаунт по такому алиасу'


class CantFindCategoryError(BaseError):
    default_message = 'Не могу найти категорию или подкатегорию по такому алиасу'


class TooBigAmountError(BaseError):
    default_message = 'Введена слишком большая сумма (больше 10^14)'


class UserAlreadyExistsError(BaseError):
    default_message = 'Пользователь с таким ником уже есть в системе, и это не вы'
