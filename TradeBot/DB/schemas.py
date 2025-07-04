from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, ForeignKey, JSON
from pydantic import BaseModel, EmailStr
from sqlalchemy.sql import func
import asyncio
from Const.const import db_pass

DATABASE_URL = f"mysql+asyncmy://root:{db_pass}@localhost/tradesnake"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    activate = Column(Boolean, nullable=False, default=False)
    money = Column(Float, nullable=False, default=0.0) 
    change_password_request = Column(Boolean, nullable=False, default=False)

    bots = relationship("Bot", back_populates="user", cascade="all, delete-orphan")

class Strategy(Base):
    __tablename__ = "strategies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    required_parameters = Column(JSON)  # Оставляем это поле

    bots = relationship("Bot", back_populates="strategy", cascade="all, delete-orphan")

class Bot(Base):
    __tablename__ = "bots"
    id = Column(Integer, primary_key=True, index=True)
    money = Column(Float, nullable=False)
    name = Column(String(50), nullable=False)
    symbol = Column(String(50), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False)
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    current_price = Column(Float, nullable=False, default=0.0)
    strategy_parameters = Column(JSON, nullable=True)
    symbol_count = Column(Float, nullable=False, default=0)
    user = relationship("User", back_populates="bots")
    broker = relationship("Broker", back_populates="bots")
    strategy = relationship("Strategy", back_populates="bots")
    trades = relationship("Trade", back_populates="bot", cascade="all, delete-orphan")
    create_time = Column(DateTime, server_default=func.now())
    isRunning = Column(Boolean, nullable=False, default=False)


class Transactions(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # Изменили Float на Integer
    money = Column(Float, nullable=False)
    create_time = Column(DateTime, server_default=func.now())

class Broker(Base):
    __tablename__ = "brokers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    market_id = Column(Integer, ForeignKey("markets.id", ondelete="CASCADE"), nullable=False)
    spred = Column(Float, nullable=False)
    procent_comission = Column(Float, nullable=False)
    fox_comission = Column(Float, nullable=False)
    symbols = Column(JSON)  # Перенесли поле symbols сюда

    bots = relationship("Bot", back_populates="broker", cascade="all, delete-orphan")
    market = relationship("Market", back_populates="brokers")

class TradeType(Base):
    __tablename__ = "tradetypes"
    id = Column(Integer, primary_key=True, index=True)
    type_name = Column(String(50), nullable=False)

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    type_id = Column(Integer, ForeignKey("tradetypes.id", ondelete="CASCADE"), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    price_by_broker = Column(Float, nullable=False)
    time = Column(DateTime, nullable=False)

    bot = relationship("Bot", back_populates="trades")
    trade_type = relationship("TradeType")

class Market(Base):
    __tablename__ = "markets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    market_type_id = Column(Integer, ForeignKey("markettypes.id", ondelete="CASCADE"), nullable=False)

    brokers = relationship("Broker", back_populates="market", cascade="all, delete-orphan")
    market_type = relationship("MarketType", back_populates="markets")

class MarketType(Base):
    __tablename__ = "markettypes"
    id = Column(Integer, primary_key=True, index=True)
    market_type_name = Column(String(50), nullable=False)

    markets = relationship("Market", back_populates="market_type", cascade="all, delete-orphan")

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


