from datetime import timedelta
from fastapi import FastAPI, Depends, HTTPException, APIRouter, Query, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func,case,text
from sqlalchemy.orm import joinedload, strategy_options, aliased
from sqlalchemy.sql.expression import or_, and_
from Models.models import HistoricalRequest, UserChangePassword, UserCreate, UserLogin, UserPassword, UserResponse, BotCreate, BotResponse, AnalyzeRequest
from DB.schemas import Bot, Trade, Broker, TradeType
from DB.schemas import get_db, User, Bot,Strategy
from Utils.tokens import create_change_password_access, verify_activation_token, verify_change_password_access, create_activation_token, create_access_token, verify_access_token
from Utils.email import send_activation_email, send_change_password_email
from Const.const import access_cookie_time, refresh_cookie_time
import httpx
import bcrypt
from datetime import datetime
import json


router = APIRouter(prefix="/utils", tags=["utils"])

def calculate_bot_summary_from_historical(historical_results,historical_request):
    # Инициализируем переменные для расчетов
    sell_sum = 0.0
    buy_sum = 0.0
    sell_sum_broker = 0.0
    buy_sum_broker = 0.0
    total_trade_count = 0
    buy_trade_count = 0
    sell_trade_count = 0
    profit_percent = 0

    # Перебираем исторические данные
    for result in historical_results:
        # Суммируем значения для buy и sell
        if result["buy"]:
            for key, value in result["buy"].items():
                if key == "price":
                    buy_sum += value
                if key == "broker_price": 
                    buy_sum_broker+=value
            buy_trade_count += 1
        if result["sell"]:
            for key, value in result["sell"].items():
                if key == "price":
                    sell_sum += value  
                if key == "broker_price": 
                    sell_sum_broker += value  
            sell_trade_count += 1  

        # Увеличиваем общее количество сделок
        total_trade_count += 1

    # Рассчитываем комиссию и другие параметры
    total_profit_without_broker = sell_sum - buy_sum
    total_profit = sell_sum_broker - buy_sum_broker
    commission = total_profit_without_broker-total_profit;
    # Формируем объект bot_summary
    bot_summary = {
        "sell_sum": sell_sum,
        "buy_sum": buy_sum,
        "total_profit_without_broker": total_profit_without_broker,
        "sell_sum_broker": sell_sum_broker,
        "buy_sum_broker": buy_sum_broker,
        "total_profit": total_profit,
        "total_trade_count": total_trade_count,
        "buy_trade_count": buy_trade_count,
        "sell_trade_count": sell_trade_count,
        "commission": commission,
    }

    return bot_summary



@router.get("/strategies")
async def get_all_strategies(db: AsyncSession = Depends(get_db)):
    # Выполняем запрос к базе данных для получения всех стратегий
    result = await db.execute(select(Strategy))
    strategies = result.scalars().all()

    # Формируем ответ
    response = []
    for strategy in strategies:
        response.append({
            "id": strategy.id,
            "name": strategy.name,
            "strategy_parameters": strategy.required_parameters
        })

    return response


@router.get("/brokers")
async def get_all_brokers(db: AsyncSession = Depends(get_db)):
    # Выполняем SQL-запрос
    query = text("""
        SELECT 
            br.id,
            br.name AS broker_name,
            br.symbols,
            m.name AS market_name,
            mt.market_type_name,
            br.spred,
            br.procent_comission,
            br.fox_comission
        FROM brokers br
        INNER JOIN markets m ON br.market_id = m.id
        INNER JOIN markettypes mt ON m.market_type_id = mt.id;
    """)
    
    # Выполняем запрос
    result = await db.execute(query)
    brokers = result.mappings().all()  # Получаем результат в виде списка словарей

    # Формируем ответ
    response = []
    for broker in brokers:
        response.append({
            "id": broker["id"],
            "broker_name": broker["broker_name"],
            "market_name": broker["market_name"],
            "market_type_name": broker["market_type_name"],
            "spred": broker["spred"],
            "procent_comission": broker["procent_comission"],
            "fox_comission": broker["fox_comission"],
            "symbols": broker["symbols"],

        })

    return response

@router.post("/execute_historical")
async def execute_historical(
    historical_request: HistoricalRequest,
    db: AsyncSession = Depends(get_db),
    access_token: str = Cookie(None)
):
    
    historical_request.strategy_parameters["interval"] = historical_request.interval
    historical_request.strategy_parameters["symbol"] = historical_request.symbol
    historical_request.strategy_parameters["money"] = historical_request.money
     
    user_id_from_token = verify_access_token(access_token)
    if not user_id_from_token:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    start_money = historical_request.strategy_parameters["money"]

 
    async with httpx.AsyncClient(timeout=httpx.Timeout(500.0)) as client:
        response = await client.post(
            "http://localhost:9090/execute_historical",
            json={
                "user_id": user_id_from_token,
                "strategy_id": historical_request.strategy_id,
                "broker_id": historical_request.broker_id,
                "strategy_parameters": historical_request.strategy_parameters
            }
        )
    if response.status_code == 200:
   
        print(f"Response content: {response.content}")
    
        if response.content:
            historical_results = response.json()
            bot_summary = calculate_bot_summary_from_historical(historical_results,historical_request)
        else:
            raise HTTPException(status_code=500, detail="Empty response body")
    else:
        return Response(status_code = 500)
        raise HTTPException(status_code=response.status_code, detail="Failed request to C++ server")

    return {
        "results": historical_results,
        "bot_summary": bot_summary
    }


@router.post("/analyze")
async def analyze(request: AnalyzeRequest):
    async with httpx.AsyncClient(timeout=httpx.Timeout(100.0)) as client:
        try:
            response = await client.post("http://localhost:9090/analyze", json=request.dict())
            
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError:
                    raise HTTPException(status_code=500, detail="Failed to parse JSON response")
            else:
                raise HTTPException(status_code=response.status_code, detail="Failed request to C++ server")
        
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")

@router.get("/bot_summary")
async def get_bot_summary(bot_id: int = Query(...), db: AsyncSession = Depends(get_db)):
 
    sql_query = text("""
        WITH trade_data AS (
            SELECT 
                bots.id AS bot_id,
                bots.name AS bot_name,
                SUM(CASE WHEN tradetypes.type_name = 'Sell' THEN trades.price ELSE 0 END) AS sell_sum,
                SUM(CASE WHEN tradetypes.type_name = 'Buy' THEN trades.price ELSE 0 END) AS buy_sum,
                SUM(CASE WHEN tradetypes.type_name = 'Sell' THEN trades.price_by_broker ELSE 0 END) AS sell_sum_broker,
                SUM(CASE WHEN tradetypes.type_name = 'Buy' THEN trades.price_by_broker ELSE 0 END) AS buy_sum_broker,
                COUNT(trades.id) AS total_trade_count,
                SUM(CASE WHEN tradetypes.type_name = 'Buy' THEN 1 ELSE 0 END) AS buy_trade_count,
                SUM(CASE WHEN tradetypes.type_name = 'Sell' THEN 1 ELSE 0 END) AS sell_trade_count
            FROM bots
            JOIN trades ON trades.bot_id = bots.id
            JOIN tradetypes ON tradetypes.id = trades.type_id
            WHERE bots.id = :bot_id
            GROUP BY bots.id, bots.name
        )
        SELECT 
            bot_id,
            bot_name,
            sell_sum,
            buy_sum,
            sell_sum - buy_sum AS total_profit_without_broker,
            sell_sum_broker,
            buy_sum_broker,
            sell_sum_broker - buy_sum_broker AS total_profit,
            total_trade_count,
            buy_trade_count,
            sell_trade_count,
            sell_sum_broker - buy_sum_broker - sell_sum + buy_sum AS commission
        FROM trade_data;
    """)

 
    result = await db.execute(sql_query, {"bot_id": bot_id})
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="No bot data found for the given bot_id")

 
    bot_summary = {
        "bot_id": row.bot_id,
        "bot_name": row.bot_name,
        "sell_sum": row.sell_sum,
        "buy_sum": row.buy_sum,
        "total_profit": row.total_profit,
        "total_profit_without_broker": row.total_profit_without_broker,
        "buy_sum_broker": row.buy_sum_broker,
        "total_profit": row.total_profit,
        "total_trade_count": row.total_trade_count,
        "buy_trade_count": row.buy_trade_count,
        "sell_trade_count": row.sell_trade_count,
        "commission": row.commission,
    }

    return {"bot_summary": bot_summary}


async def get_bot_data(bot_id: int, db: AsyncSession):
    query = text("""
        SELECT 
            b.create_time,
            mt.market_type_name,
            b.symbol,
            b.strategy_parameters
        FROM bots b
        INNER JOIN brokers br ON b.broker_id = br.id
        INNER JOIN markets m ON m.id = br.market_id
        INNER JOIN markettypes mt ON mt.id = m.market_type_id
        WHERE b.id = :bot_id;
    """)
    result = await db.execute(query, {"bot_id": bot_id})
    bot_data = result.mappings().first()
    if not bot_data:
        raise HTTPException(status_code=404, detail="Bot not found")

 
    strategy_parameters = json.loads(bot_data["strategy_parameters"])

 
    create_time = bot_data["create_time"]
    start_date = create_time - timedelta(days=3)  # Вычитаем 1 день
    start_date_unix = int(start_date.timestamp()) * 1000  # В миллисекундах

    # Вычисляем end_date (текущее время в Unix-секундах)
    end_date_unix = int(datetime.now().timestamp()) * 1000  # В миллисекундах

 
    return {
        "start_date": start_date_unix,
        "end_date": end_date_unix,
        "market_type_name": bot_data["market_type_name"],
        "symbol": bot_data["symbol"],
        "interval": strategy_parameters.get("interval", "60")  
    }
 
async def get_historical_data(user_id: int, bot_id: int, db: AsyncSession):
    # Получаем данные о боте
    bot_data = await get_bot_data(bot_id, db)

    # Формируем запрос на C++ сервер
    historical_request = {
        "bot_id": bot_id,
        "user_id": user_id,
        "start_date": int(bot_data["start_date"]/1000),
        "end_date": int(bot_data["end_date"]/1000),
        "market_type_name": bot_data["market_type_name"],
        "symbol": bot_data["symbol"],
        "interval": bot_data["interval"]
    }

    async with httpx.AsyncClient(timeout=100.0) as client:
        response = await client.post(
            "http://localhost:9090/historical_data",
            json=historical_request
        )
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch historical data")

 
async def get_trades_from_db(bot_id: int, db: AsyncSession):
    query = text("""
        SELECT 
            trades.id AS trade_id,
            trades.bot_id,
            trades.type_id,
            trades.price,
            trades.quantity,
            trades.price_by_broker,
            trades.time AS trade_time,
            bots.money,
            bots.symbol,
            bots.strategy_parameters
        FROM trades
        INNER JOIN bots ON bots.id = trades.bot_id
        WHERE bots.id = :bot_id
        ORDER BY trades.time;
    """)
    result = await db.execute(query, {"bot_id": bot_id})
    return result.mappings().all()
def combine_data(historical_data, trades):
    combined = []
    candles = historical_data["result"]

   
    trades = [
        {
            **trade,  # Копируем все поля из RowMapping
            "trade_time_unix": int(trade["trade_time"].timestamp()) * 1000  # Добавляем новое поле
        }
        for trade in trades
    ]

    # Индекс для трейдов
    trade_index = 0

    # Проходим по свечам
    for i in range(len(candles)):
        candle = candles[i]
        trade_entry = {
            "timestamp": candle["timestamp"],
            "open": candle["open"],
            "close": candle["close"],
            "high": candle["high"],
            "low": candle["low"],
            "volume": candle["volume"],
            "buy": {},   
            "sell": {}   
        }

       
        current_time = int(candle["timestamp"])
        next_time = int(candles[i + 1]["timestamp"]) if i < len(candles) - 1 else None

        # Проходим по трейдам и добавляем их, если они попадают в интервал
        while trade_index < len(trades):
            trade = trades[trade_index]
            trade_time_unix = trade["trade_time_unix"]

            # Если трейд находится перед текущей свечой, пропускаем его
            if trade_time_unix < current_time:
                trade_index += 1
                continue

            # Если трейд находится после следующей свечи, завершаем обработку для текущей свечи
            if next_time and trade_time_unix >= next_time:
                break

            
            if trade["type_id"] == 1:  # Buy
                if trade_entry["buy"]:  # Если уже есть данные в buy
                    trade_entry["buy"]["broker_price"] += float(trade["price_by_broker"])
                    trade_entry["buy"]["price"] += float(trade["price"])
                    trade_entry["buy"]["quantity"] += float(trade["quantity"])
                else:  # Если buy пустой
                    trade_entry["buy"] = {
                        "broker_price": float(trade["price_by_broker"]),
                        "price": float(trade["price"]),
                        "quantity": float(trade["quantity"])
                    }
            elif trade["type_id"] == 2:  # Sell
                if trade_entry["sell"]:  # Если уже есть данные в sell
                    trade_entry["sell"]["broker_price"] += float(trade["price_by_broker"])
                    trade_entry["sell"]["price"] += float(trade["price"])
                    trade_entry["sell"]["quantity"] += float(trade["quantity"])
                else:  # Если sell пустой
                    trade_entry["sell"] = {
                        "broker_price": float(trade["price_by_broker"]),
                        "price": float(trade["price"]),
                        "quantity": float(trade["quantity"])
                    }

            
            trade_index += 1

        combined.append(trade_entry)

    
    if trade_index < len(trades):
        last_candle = combined[-1]
        for trade in trades[trade_index:]:
            if trade["type_id"] == 1:  # Buy
                if last_candle["buy"]:  # Если уже есть данные в buy
                    last_candle["buy"]["broker_price"] += float(trade["price_by_broker"])
                    last_candle["buy"]["price"] += float(trade["price"])
                    last_candle["buy"]["quantity"] += float(trade["quantity"])
                else:  # Если buy пустой
                    last_candle["buy"] = {
                        "broker_price": float(trade["price_by_broker"]),
                        "price": float(trade["price"]),
                        "quantity": float(trade["quantity"])
                    }
            elif trade["type_id"] == 2:  # Sell
                if last_candle["sell"]:  # Если уже есть данные в sell
                    last_candle["sell"]["broker_price"] += float(trade["price_by_broker"])
                    last_candle["sell"]["price"] += float(trade["price"])
                    last_candle["sell"]["quantity"] += float(trade["quantity"])
                else:  # Если sell пустой
                    last_candle["sell"] = {
                        "broker_price": float(trade["price_by_broker"]),
                        "price": float(trade["price"]),
                        "quantity": float(trade["quantity"])
                    }

    return combined

@router.post("/get_combined_data")
async def get_combined_data(
    bot_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    access_token: str = Cookie(None),
):
    # Проверка токена
    user_id = verify_access_token(access_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")

    # Получаем исторические данные
    historical_data = await get_historical_data(user_id, bot_id, db)

    # Получаем данные о сделках
    trades = await get_trades_from_db(bot_id, db)

    # Объединяем данные
    combined_data = combine_data(historical_data, trades)

    # Рассчитываем сводку
    bot_summary = calculate_bot_summary_from_historical(combined_data, historical_data)

    return {
        "results": combined_data,
        "bot_summary": bot_summary
    }
 