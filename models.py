# SQLAlchemy models for SMS Poll
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Poll(Base):
    __tablename__ = "polls"
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    question = Column(Text)
    template = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    choices = relationship("Choice", back_populates="poll", cascade="all, delete-orphan")
    votes = relationship("Vote", back_populates="poll")

class Choice(Base):
    __tablename__ = "choices"
    id = Column(Integer, primary_key=True)
    poll_id = Column(Integer, ForeignKey("polls.id", ondelete="CASCADE"))
    code = Column(String(10), index=True)   # e.g., "A", "1"
    label = Column(String(200))
    poll = relationship("Poll", back_populates="choices")

class Vote(Base):
    __tablename__ = "votes"
    id = Column(Integer, primary_key=True)
    poll_id = Column(Integer, ForeignKey("polls.id"))
    choice_id = Column(Integer, ForeignKey("choices.id"))
    from_number = Column(String(50), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("poll_id", "from_number", name="uix_poll_from"),)

    poll = relationship("Poll", back_populates="votes")
    choice = relationship("Choice")

class RawMessage(Base):
    __tablename__ = "raw_messages"
    id = Column(Integer, primary_key=True)
    poll_id = Column(Integer, nullable=True)
    from_number = Column(String(50))
    to_number = Column(String(50))
    body = Column(Text)
    received_at = Column(DateTime, default=datetime.utcnow)

class OptOut(Base):
    __tablename__ = "opt_outs"
    number = Column(String(50), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)