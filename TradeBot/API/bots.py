from datetime import timedelta
from fastapi import FastAPI, Depends, HTTPException, APIRouter, Query, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, update
from sqlalchemy.orm import joinedload, strategy_options
from sqlalchemy.sql.expression import or_, and_
from Models.models import HistoricalRequest, UserChangePassword, UserCreate, UserLogin, UserPassword, UserResponse, BotCreate, BotResponse, AnalyzeRequest
from DB.schemas import get_db, User, Bot
from Utils.tokens import create_change_password_access, verify_activation_token, verify_change_password_access
from Utils.email import send_activation_email, send_change_password_email
from Utils.tokens import create_activation_token, create_access_token, verify_access_token
from Const.const import access_cookie_time, refresh_cookie_time
import httpx
import bcrypt

router = APIRouter(prefix="/users/bots", tags=["bots"])

@router.post("/bot", response_model=BotResponse)
async def create_bot(bot_data: BotCreate, db: AsyncSession = Depends(get_db), access_token: str = Cookie(None)):
    # Получаем user_id из access_token
    user_id = verify_access_token(access_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")

    # Получаем пользователя из базы данных
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Проверяем, достаточно ли средств у пользователя
    if user.money < bot_data.money:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    # Списываем средства с баланса пользователя
    user.money -= bot_data.money
    db.add(user)

    # Создаем бота
    bot = Bot(
        name=bot_data.name,
        symbol=bot_data.symbol,
        money=bot_data.money,
        user_id=user_id,
        broker_id=bot_data.broker_id,
        strategy_id=bot_data.strategy_id,
        strategy_parameters=bot_data.strategy_parameters,
        isRunning=True  # Новый бот запускается автоматически
    )
    db.add(bot)

    # Сохраняем изменения в базе данных
    await db.commit()
    await db.refresh(bot)

    # Отправляем запрос на внешний сервер для запуска бота
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:  # Тайм-аут 30 секунд
        response = await client.post(
            "http://localhost:9090/start",
            json={
                "user_id": user_id,
                "bot_id": bot.id,
                "symbol": bot.symbol,
                "money": bot.money,
                "strategy_id": bot.strategy_id,
                "broker_id": bot.broker_id,
                "strategy_parameters": bot_data.strategy_parameters  # Передаём параметры стратегии
            }
        )
        if response.status_code != 200:
            await db.rollback()  # Откатываем транзакцию при ошибке
            raise HTTPException(
                status_code=response.status_code,  # Сохраняем оригинальный статус
                detail=f"External server error: {response.text}"  # Добавляем детали
            )
        return bot

@router.post("/bot/{bot_id}")
async def delete_bot(bot_id: int, db: AsyncSession = Depends(get_db), access_token: str = Cookie(None)):
    user_id = verify_access_token(access_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    
    # Start a transaction
    async with db.begin():
        # Get the bot with a lock to prevent concurrent modifications
        result = await db.execute(
            select(Bot)
            .where(Bot.id == bot_id, Bot.user_id == user_id)
            .with_for_update()
        )
        bot = result.scalars().first()
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found or does not belong to user")
        
        # Calculate the bot's value
        bot_value = bot.symbol_count * bot.current_price + bot.money
        
        # Update user's money
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(money=User.money + bot_value)
        )
        
        # Delete the bot
        await db.delete(bot)
    
    # The transaction is committed automatically when exiting the context manager
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:9090/stop",
            json={"bot_id": bot_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to stop bot on external server")
    
    return Response(status_code=200)

@router.post("/bot/{bot_id}/update")
async def update_bot(bot_id: int, bot_data: BotCreate, db: AsyncSession = Depends(get_db), access_token: str = Cookie(None)):
    user_id = verify_access_token(access_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    
    # Получаем бота и проверяем принадлежность пользователю
    result = await db.execute(select(Bot).where(Bot.id == bot_id, Bot.user_id == user_id))
    bot = result.scalars().first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found or does not belong to user")
    
    # Получаем пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    # Рассчитываем разницу в средствах
    new_money = bot_data.money - bot.money
    
    # Проверяем, достаточно ли средств у пользователя
    if user.money < new_money:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    # Списываем средства с баланса пользователя
    user.money -= new_money
    db.add(user)

    # Останавливаем текущего бота
    async with httpx.AsyncClient() as client:
        stop_response = await client.post(
            "http://localhost:9090/stop",
            json={"bot_id": bot_id}
        )
        if stop_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to stop bot on external server") 
    
    # Обновляем параметры существующего бота вместо создания нового
    bot.name = bot_data.name
    bot.symbol = bot_data.symbol
    bot.money = bot_data.money
    bot.broker_id = bot_data.broker_id
    bot.strategy_id = bot_data.strategy_id
    bot.strategy_parameters = bot_data.strategy_parameters
    bot.isRunning = True  # Будет запущен снова
    
    db.add(bot)
    await db.commit()
    await db.refresh(bot)
    
    # Запускаем обновленного бота
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        start_response = await client.post(
            "http://localhost:9090/start",
            json={
                "user_id": user_id,
                "bot_id": bot.id,  # Используем тот же ID
                "symbol": bot.symbol,
                "money": bot.money,
                "strategy_id": bot.strategy_id,
                "broker_id": bot.broker_id,
                "strategy_parameters": bot.strategy_parameters
            }
        )
        if start_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to start bot on external server")
    
    return bot
@router.post("/bot/{bot_id}/pause")
async def pause_bot(bot_id: int, db: AsyncSession = Depends(get_db), access_token: str = Cookie(None)):
    user_id = verify_access_token(access_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    
    result = await db.execute(select(Bot).where(Bot.id == bot_id, Bot.user_id == user_id))
    bot = result.scalars().first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found or does not belong to user")
    
    # Обновляем поле isRunning в базе данных
    await db.execute(
        update(Bot)
        .where(Bot.id == bot_id)
        .values(isRunning=False)
    )
    await db.commit()
    
    # Отправляем запрос на остановку бота
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:9090/stop",
            json={"bot_id": bot_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to pause bot on external server")
    
    return Response(status_code=200)

@router.post("/bot/{bot_id}/continue")
async def continue_bot(bot_id: int, db: AsyncSession = Depends(get_db), access_token: str = Cookie(None)):
    user_id = verify_access_token(access_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    
    result = await db.execute(select(Bot).where(Bot.id == bot_id, Bot.user_id == user_id))
    bot = result.scalars().first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found or does not belong to user")
    
    # Обновляем поле isRunning в базе данных
    await db.execute(
        update(Bot)
        .where(Bot.id == bot_id)
        .values(isRunning=True)
    )
    await db.commit()
    
    # Отправляем запрос на продолжение работы бота
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:9090/continue",
            json={"bot_id": bot_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to continue bot on external server")
    
    return Response(status_code=200)

@router.get("/bot/profit")
async def get_bots_profit(
    db: AsyncSession = Depends(get_db), 
    access_token: str = Cookie(None), 
    market_type: str = Query(None)
):
    user_id = verify_access_token(access_token)
    if not user_id:
        return Response(status_code=401)

    query = text("""
    SELECT 
        b.id AS bot_id,
        b.name AS bot_name,
        b.symbol,
        b.symbol_count,
        b.current_price,
        br.name AS broker_name,
        m.name AS market_name,
        mt.market_type_name,
        b.create_time,
        b.money,
        SUM(
            CASE 
                WHEN tt.type_name = 'Sell' THEN COALESCE(t.price_by_broker, 0)
                WHEN tt.type_name = 'Buy' THEN -COALESCE(t.price_by_broker, 0)
                ELSE 0
            END
        ) + b.symbol_count * b.current_price AS profit
    FROM bots b
    LEFT JOIN trades t ON t.bot_id = b.id   
    LEFT JOIN tradetypes tt ON tt.id = t.type_id
    INNER JOIN strategies s ON b.strategy_id = s.id
    INNER JOIN brokers br ON b.broker_id = br.id
    INNER JOIN markets m ON br.market_id = m.id
    INNER JOIN markettypes mt ON m.market_type_id = mt.id
    WHERE b.user_id = :user_id
    """ + (" AND mt.market_type_name = :market_type" if market_type else "") + """
    GROUP BY b.id, b.name, b.symbol, br.name, m.name, mt.market_type_name, b.create_time;
    """)
    
    params = {"user_id": user_id}
    if market_type:
        params["market_type"] = market_type
    
    result = await db.execute(query, params)
    bots_profit = result.mappings().all()
    
    return {"bots_profit": bots_profit}

@router.get("/bot/profit/{bot_id}")
async def get_bot_profit(
    bot_id: int,
    db: AsyncSession = Depends(get_db), 
    access_token: str = Cookie(None)
):
    # Проверка токена
    user_id = verify_access_token(access_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")

    # Исправленный SQL-запрос
    query = text("""
        SELECT 
            b.id AS bot_id,
            b.name AS bot_name,
            b.symbol,
            b.money,
            b.isRunning,
            br.id as broker_id,
            b.symbol_count as symbol_count,
            b.strategy_parameters,
            b.strategy_id,
            br.name AS broker_name,
            m.name AS market_name,
            mt.market_type_name,
            b.create_time,
            COALESCE(SUM(
                CASE 
                    WHEN tt.type_name = 'Sell' THEN t.price_by_broker
                    WHEN tt.type_name = 'Buy' THEN -t.price_by_broker
                    ELSE 0
                END
            ), 0) AS profit,
            COALESCE(COUNT(CASE WHEN tt.type_name = 'Buy' THEN 1 END), 0) AS buy_count,
            COALESCE(COUNT(CASE WHEN tt.type_name = 'Sell' THEN 1 END), 0) AS sell_count,
            COALESCE(AVG(CASE WHEN tt.type_name = 'Sell' THEN t.price_by_broker END), 0) AS sell_avg,
            COALESCE(AVG(CASE WHEN tt.type_name = 'Buy' THEN t.price_by_broker END), 0) AS buy_avg
        FROM bots b
        LEFT JOIN trades t ON t.bot_id = b.id
        LEFT JOIN tradetypes tt ON tt.id = t.type_id
        INNER JOIN strategies s ON b.strategy_id = s.id
        INNER JOIN brokers br ON b.broker_id = br.id
        INNER JOIN markets m ON br.market_id = m.id
        INNER JOIN markettypes mt ON m.market_type_id = mt.id
        WHERE b.id = :bot_id AND b.user_id = :user_id
        GROUP BY b.id, b.name, b.symbol, br.name, m.name, mt.market_type_name, b.create_time
    """)
    
    # Параметры для запроса
    params = {"bot_id": bot_id, "user_id": user_id}
    
    try:
        # Выполнение запроса
        result = await db.execute(query, params)
        bot_profit = result.mappings().first()
        
        if not bot_profit:
            raise HTTPException(status_code=404, detail="Bot not found")
            
        return {
            "bot_profit": {
                **bot_profit,
                "profit": float(bot_profit["profit"] or 0),
                "buy_count": int(bot_profit["buy_count"] or 0),
                "sell_count": int(bot_profit["sell_count"] or 0),
                "sell_avg": float(bot_profit["sell_avg"] or 0),
                "buy_avg": float(bot_profit["buy_avg"] or 0)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")