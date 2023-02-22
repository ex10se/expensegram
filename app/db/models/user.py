from sqlalchemy import BigInteger, Column, String
from sqlalchemy.orm import relationship

from db.base import Base, cascade


class UserModel(Base):
    __tablename__ = 'user'

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    accounts = relationship('AccountModel', lazy='subquery', back_populates='user', cascade=cascade)
    categories = relationship('CategoryModel', lazy='subquery', back_populates='user', cascade=cascade)
    transfers = relationship('TransferModel', lazy='subquery', back_populates='user', cascade=cascade)
    entries = relationship('EntryModel', lazy='subquery', back_populates='user', cascade=cascade)
