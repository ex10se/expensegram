from sqlalchemy import BigInteger, Column, String, UniqueConstraint, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from db.base import Base, cascade


class CategoryModel(Base):
    __tablename__ = 'category'
    __table_args__ = (
        UniqueConstraint('title', 'user_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(length=255), nullable=False)
    disabled = Column(Boolean, default=False, nullable=False)
    user_id = Column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

    user = relationship('UserModel', lazy='subquery', back_populates='categories')
    entries = relationship('EntryModel', lazy='subquery', back_populates='category', cascade=cascade)
