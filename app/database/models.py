from enum import Enum
from typing import Optional

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Enum as SQLEnum, Table, Column, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Role(str, Enum):
    ADMIN = 'admin'
    MODERATOR = 'moderator'
    USER = 'user'

photo_m2m_tag = Table(
    'photo_m2m_tag',
    Base.metadata,
    Column('photo_id', ForeignKey('photos.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True),
)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(25), unique=True)
    email: Mapped[str] = mapped_column(String(150), unique=True)
    password: Mapped[str] = mapped_column(String(150))
    role: Mapped[Role] = mapped_column(SQLEnum(Role), default=Role.USER)
    refresh_token: Mapped[Optional[str]] = mapped_column(String(255))
    confirmed: Mapped[bool] = mapped_column(default=False)

class Photo(Base):
    __tablename__ = 'photos'
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now()) 
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    public_id: Mapped[str] = mapped_column(String(255), unique=True)
    tags: Mapped[list['Tag']] = relationship(secondary=photo_m2m_tag)
    links: Mapped[list['PhotoLink']] = relationship(back_populates='photo', cascade='all, delete-orphan')
    comments: Mapped[list['Comment']] = relationship(back_populates='photo', cascade='all, delete-orphan')

class Tag(Base):
    __tablename__ = 'tags'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(25), unique=True)


class PhotoLink(Base):
    __tablename__ = 'photo_links'
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(500))
    params: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    photo_id: Mapped[int] = mapped_column(ForeignKey('photos.id', ondelete='CASCADE'))
    photo: Mapped['Photo'] = relationship(back_populates='links')

class Comment(Base):
    __tablename__ = 'comments'
    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now()) 
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    photo_id: Mapped[int] = mapped_column(ForeignKey('photos.id', ondelete='CASCADE'), index=True)
    photo: Mapped['Photo'] = relationship(back_populates='comments')