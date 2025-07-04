from pydantic import BaseModel, EmailStr
from typing import Dict, Optional
 

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str   

class UserLogin(BaseModel):
    login:str
    password:str

    
class UserChangePassword(BaseModel):
    email:str

class UserPassword(BaseModel):
    password:str

class BotCreate(BaseModel):
 
    name: str
    money: float   
    broker_id: int
    symbol: str
    strategy_id: int
    strategy_parameters: Optional[Dict[str, str]] = None  

class BotUpdate(BotCreate):
    id:int

class BotResponse(BaseModel):
    id: int
    name: str 
    user_id: int
    broker_id: int
    symbol: str
    strategy_id: int
    strategy_parameters: Optional[Dict[str, str]] = None 
class MoneyData(BaseModel):
    amount:float


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr

    class Config:
        from_attributes = True


class HistoricalRequest(BaseModel):
    strategy_id: int
    broker_id: int
    symbol:str
    money:float
    interval:str
    strategy_parameters: Dict[str, str]  

class AnalyzeRequest(BaseModel):
    start_date: str
    end_date: str
    market_type_name: str
    symbol:str
     

class UserStatisticsResponse(BaseModel):
    id: int
    username: str
    email: str
    start_money: float
    money: float
    bot_count: int
    market_count: int
    broker_count: int
    trade_count: int
    total_profit: float
    crypto_profit: float
    forex_profit: float
    stocks_profit: float

    class Config:
        from_attributes = True