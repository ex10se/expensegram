from sqlalchemy import BigInteger, Column, String, ForeignKey, DECIMAL, DateTime, func
from sqlalchemy.orm import relationship

from db.base import Base


class EntryModel(Base):
    __tablename__ = 'entry'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    amount = Column(DECIMAL(scale=2), nullable=False)
    title = Column(String(length=255), nullable=True)
    user_id = Column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    category_id = Column(ForeignKey('category.id', ondelete='CASCADE'), nullable=False)
    account_id = Column(ForeignKey('account.id', ondelete='CASCADE'), nullable=False)
    date_created = Column(DateTime(timezone=True), server_default=func.now())
    date_updated = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship('UserModel', lazy='subquery', back_populates='entries')
    category = relationship('CategoryModel', lazy='subquery', back_populates='entries')
    account = relationship('AccountModel', lazy='subquery', back_populates='entries')
