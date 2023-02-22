from sqlalchemy import BigInteger, Column, ForeignKey, DECIMAL, DateTime, func
from sqlalchemy.orm import relationship

from db.base import Base


class TransferModel(Base):
    __tablename__ = 'transfer'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    amount_from = Column(DECIMAL(scale=2), nullable=False)
    amount_to = Column(DECIMAL(scale=2), nullable=False)
    account_from_id = Column(ForeignKey('account.id', ondelete='CASCADE'), nullable=False)
    account_to_id = Column(ForeignKey('account.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    date_created = Column(DateTime(timezone=True), server_default=func.now())
    date_updated = Column(DateTime(timezone=True), onupdate=func.now())

    account_from = relationship(
        'AccountModel',
        foreign_keys=[account_from_id],
        lazy='subquery',
        back_populates='transfers_from',
    )
    account_to = relationship(
        'AccountModel',
        foreign_keys=[account_to_id],
        lazy='subquery',
        back_populates='transfers_to',
    )
    user = relationship('UserModel', lazy='subquery', back_populates='transfers')
