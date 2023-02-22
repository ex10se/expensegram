from decimal import Decimal

from sqlalchemy import BigInteger, Column, String, UniqueConstraint, ForeignKey, DECIMAL
from sqlalchemy.orm import relationship

from db.base import Base, cascade


class AccountModel(Base):
    __tablename__ = 'account'
    __table_args__ = (
        UniqueConstraint('title', 'user_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(length=255), nullable=False)
    amount = Column(DECIMAL(precision=20, scale=2), default=Decimal('0'), nullable=False)
    user_id = Column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    currency = Column(String(length=100), nullable=False)

    user = relationship('UserModel', lazy='subquery', back_populates='accounts')
    transfers_from = relationship(
        'TransferModel',
        primaryjoin="TransferModel.account_from_id == AccountModel.id",
        back_populates='account_from',
        lazy='subquery',
        cascade=cascade,
    )
    transfers_to = relationship(
        'TransferModel',
        primaryjoin="TransferModel.account_to_id == AccountModel.id",
        back_populates='account_to',
        lazy='subquery',
        cascade=cascade,
    )
    entries = relationship('EntryModel', lazy='subquery', back_populates='account', cascade=cascade)
