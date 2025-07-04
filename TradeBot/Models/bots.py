from pydantic import BaseModel, EmailStr


class BotCreate(BaseModel):
    name:str
    broker_id:int
    profit:float

class Bot(BotCreate):
    id:int


class TradeCreate(BaseModel):
    type_id:int
    price:int
