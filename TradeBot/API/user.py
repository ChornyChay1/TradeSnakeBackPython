from datetime import timedelta
from fastapi import FastAPI, Depends, HTTPException, APIRouter,Query,Response,Cookie,Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,text,func
from sqlalchemy.orm import joinedload, strategy_options
from sqlalchemy.sql.expression import or_,and_
from Models.models import HistoricalRequest, MoneyData, UserChangePassword, UserCreate, UserLogin, UserPassword, UserResponse,BotCreate,BotResponse,AnalyzeRequest,UserStatisticsResponse
from DB.schemas import get_db, User,Bot,Transactions
from Utils.tokens import create_change_password_access, verify_activation_token,verify_change_password_access
from Utils.email import send_activation_email,send_change_password_email
from Utils.tokens import create_activation_token,create_access_token,verify_access_token
from Const.const import access_cookie_time, refresh_cookie_time
import httpx
import bcrypt
import io
import pandas as pd
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
 
    result = await db.execute(
        select(User).where(or_(User.email == user.email, User.username == user.username))
    )
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email or username already exists")

 
    password_hash = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()

 
    db_user = User(username=user.username, email=user.email, password_hash=password_hash, money = 0)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    return db_user

@router.post("/login")
async def create_user(user: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(or_(User.email == user.login, User.username == user.login))
    )
    existing_user = result.scalars().first()
    if not existing_user:
        raise HTTPException(status_code=400, detail="User with this email or username does not exist")
 
    if not bcrypt.checkpw(user.password.encode(), existing_user.password_hash.encode()):
        raise HTTPException(status_code=400, detail="Invalid password")

    if existing_user.activate is False:
        activation_token = create_activation_token(existing_user.id)
        await send_activation_email(existing_user.email, activation_token)
        return Response(status_code=302)
    else:
        refresh_token = create_access_token(data={"user_id": existing_user.id}, expires_delta=timedelta(days=7))
        access_token =   create_access_token(data = {"user_id":existing_user.id},expires_delta = timedelta(minutes=2))
        response = Response(status_code=200)
        response.set_cookie(
            key="refresh_token", value=refresh_token, httponly=True, max_age=refresh_cookie_time
        )
        response.set_cookie(
            key="access_token", value=access_token, httponly=True, max_age=access_cookie_time  
        )
        return response

@router.post("/change_password")
async def create_user(user: UserChangePassword, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(or_(User.email == user.email))
    )
    existing_user = result.scalars().first()
    if not existing_user:
        raise HTTPException(status_code=400, detail="User with this email or username is not exist")
    existing_user.change_password_request = True;
    await db.commit()
    change_password_token = create_change_password_access(existing_user.id)

    await send_change_password_email(existing_user.email, change_password_token)
    return Response(status_code=302)    

@router.post("/change_password/{token}")
async def change_password(token: str,new_password:UserPassword, db: AsyncSession = Depends(get_db)):
    user_id = verify_change_password_access(token)
    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid or expired activation token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.change_password_request is False:
        raise HTTPException(status_code=403, detail="No request for change password")
    password_hash = bcrypt.hashpw(new_password.password.encode(), bcrypt.gensalt()).decode()
    user.password_hash = password_hash
    user.change_password_request = False   
    await db.commit()
    return  Response(status_code=200)   

@router.post("/add_money")
async def add_user_money(
    money_data: MoneyData,
    access_token: str = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    user_id = verify_access_token(access_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")

    try:
 
        transaction = Transactions(
            user_id=user_id,
            money=money_data.amount
        )
        db.add(transaction)
        
        # Обновляем баланс пользователя
        update_query = text("""
            UPDATE users 
            SET money = money + :amount
            WHERE id = :user_id
        """)
        await db.execute(update_query, {"amount": money_data.amount, "user_id": user_id})
        
        await db.commit()
        return {"message": "Money added successfully"}
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# @router.put("/update_money")
# async def update_user_money(
#     access_token: str = Cookie(None),  # Получаем токен из куки
#     db: AsyncSession = Depends(get_db)
# ):
#     # Проверяем токен и получаем user_id
#     user_id = verify_access_token(access_token)
#     if not user_id:
#         raise HTTPException(status_code=401, detail="Invalid or expired access token")

#     # Получаем новое значение money для пользователя
#     select_money_query = text("""
#         SELECT COALESCE(SUM(
#             CASE 
#                 WHEN tt.type_name = 'Sell' THEN t.price_by_broker
#                 WHEN tt.type_name = 'Buy' THEN -t.price_by_broker
#                 ELSE 0
#             END
#         ), 0) + u.unused_money  AS new_money
#         FROM bots b
#         INNER JOIN trades t ON t.bot_id = b.id
#         INNER JOIN tradetypes tt ON tt.id = t.type_id
#         INNER JOIN users u ON b.user_id = u.id
#         WHERE u.id = :user_id
#     """)

#     result = await db.execute(select_money_query, {"user_id": user_id})
#     new_money_row = result.first()

#     if not new_money_row:
#         raise HTTPException(status_code=404, detail="User not found")

#     new_money = new_money_row.new_money

#     # Выполняем запрос на обновление данных пользователя
#     update_money_query = text("""
#         UPDATE users
#         SET money = :new_money
#         WHERE id = :user_id;
#     """)
    
#     # Выполняем обновление
#     await db.execute(update_money_query, {"new_money": new_money, "user_id": user_id})
#     await db.commit()  # Завершаем обновление

#     return {"message": "User money updated successfully"}
@router.get("/statistics")
async def get_user_statistics(
    access_token: str = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    user_id = verify_access_token(access_token)
    if not user_id:
        return Response(status_code=403)

 
    start_money = 0
    first_transaction_result = await db.execute(
        select(Transactions.money)
        .where(Transactions.user_id == user_id)
        .order_by(Transactions.create_time.asc())
        .limit(1)
    )
    first_transaction = first_transaction_result.scalar_one_or_none()
    if first_transaction is not None:
        start_money = first_transaction

    # Получаем сумму всех транзакций пользователя
    total_transactions_result = await db.execute(
        select(func.sum(Transactions.money))
        .where(Transactions.user_id == user_id)
    )
    total_transactions = total_transactions_result.scalar_one_or_none() or 0

 
    bots_value_result = await db.execute(
        select(func.sum(Bot.symbol_count * Bot.current_price))
        .where(Bot.user_id == user_id)
    )
    bots_value = bots_value_result.scalar_one_or_none() or 0

    # Основной запрос статистики
    sql_query = text("""
    SELECT 
        u.id,
        u.username,
        u.email,
        u.money,
        COUNT(DISTINCT b.id) AS bot_count,   
        COUNT(DISTINCT m.id) AS market_count,  
        COUNT(DISTINCT br.id) AS broker_count,  
        COUNT(DISTINCT t.id) AS trade_count,
        COUNT(CASE WHEN tt.type_name = 'Buy' THEN 1 END) AS buy_count,  
        COUNT(CASE WHEN tt.type_name = 'Sell' THEN 1 END) AS sell_count,  
        SUM(
            CASE 
                WHEN tt.type_name = 'Sell' THEN t.price_by_broker
                WHEN tt.type_name = 'Buy' THEN -t.price_by_broker
                ELSE 0
            END
        ) AS total_profit,
        SUM(
            CASE 
                WHEN tt.type_name = 'Sell' AND mt.market_type_name = 'Crypto' THEN t.price_by_broker
                WHEN tt.type_name = 'Buy' AND mt.market_type_name = 'Crypto' THEN -t.price_by_broker
                ELSE 0
            END
        ) AS crypto_profit,
        SUM(
            CASE 
                WHEN tt.type_name = 'Sell' AND mt.market_type_name = 'Forex' THEN t.price_by_broker
                WHEN tt.type_name = 'Buy' AND mt.market_type_name = 'Forex' THEN -t.price_by_broker
                ELSE 0
            END
        ) AS forex_profit,
        SUM(
            CASE 
                WHEN tt.type_name = 'Sell' AND mt.market_type_name = 'Stocks' THEN t.price_by_broker
                WHEN tt.type_name = 'Buy' AND mt.market_type_name = 'Stocks' THEN -t.price_by_broker
                ELSE 0
            END
        ) AS stocks_profit
    FROM 
        users u
        LEFT JOIN bots b ON b.user_id = u.id 
        LEFT JOIN trades t ON t.bot_id = b.id
        LEFT JOIN tradetypes tt ON tt.id = t.type_id
        LEFT JOIN brokers br ON b.broker_id = br.id
        LEFT JOIN markets m ON br.market_id = m.id
        LEFT JOIN markettypes mt ON m.market_type_id = mt.id 
    WHERE 
        u.id = :user_id
    GROUP BY 
        u.id, u.username, u.email, u.money;
    """)

    result = await db.execute(sql_query, {"user_id": user_id})
    row = result.first()
    
    # Рассчитываем procent
    current_assets = row.money + bots_value
    procent = (current_assets / total_transactions * 100)-100 if total_transactions != 0 else 0

    user_statistics = {
        "id": row.id,
        "username": row.username,
        "email": row.email,
        "money": row.money,
        "start_money": start_money,
        "bot_count": row.bot_count,
        "market_count": row.market_count,
        "broker_count": row.broker_count,
        "trade_count": row.trade_count,
        "buy_count": row.buy_count,
        "sell_count": row.sell_count,
        "total_profit": row.total_profit or 0,
        "crypto_profit": row.crypto_profit or 0,
        "forex_profit": row.forex_profit or 0,
        "stocks_profit": row.stocks_profit or 0,
        "procent": round(procent, 2),  
        "current_assets": current_assets,
        "total_transactions": total_transactions
    }

    return user_statistics

@router.get("/trade_statistics")
async def get_trade_statistics(
    access_token: str = Cookie(None),  # Получаем токен из куки
    db: AsyncSession = Depends(get_db)  # Подключение к базе данных
):
 
    user_id = verify_access_token(access_token)
    if not user_id:
        return Response(status_code=403)

    # Определяем SQL-запрос
    sql_query = text("""
    SELECT 
        b.name,
        b.symbol,
        tt.type_name,
        t.price_by_broker,
        t.time,
        t.quantity
    FROM 
        bots b 
    INNER JOIN trades t ON b.id = t.bot_id
    INNER JOIN tradetypes tt ON t.type_id = tt.id
    WHERE 
        b.user_id = :user_id
    ORDER BY t.time DESC
    LIMIT 65;
    """)

 
    result = await db.execute(sql_query, {"user_id": user_id})
    rows = result.fetchall()

 
    # Формируем ответ
    trade_statistics = []
    for row in rows:
        trade_statistics.append({
            "bot_name": row.name,
            "trade_type": row.type_name,
            "symbol": row.symbol,
            "price_by_broker": row.price_by_broker,
            "time": row.time,
            "quantity": row.quantity
        })

    return {"trade_statistics": trade_statistics}

@router.get("/money_history")
async def get_money_history(
    access_token: str = Cookie(None),  
    db: AsyncSession = Depends(get_db)
):
    user_id = verify_access_token(access_token)
    if not user_id:
        return Response(status_code=401)
     
    sql_query = text("""
        WITH 
        -- Объединяем все операции без предварительной агрегации
        raw_data AS (
            -- Транзакции (пополнения)
            SELECT 
                create_time AS timestamp,
                money AS amount,
                'deposit' AS type
            FROM 
                transactions
            WHERE 
                user_id = :user_id
            
            UNION ALL
            
            -- Торговые операции
            SELECT 
                t.time AS timestamp,
                CASE 
                    WHEN tt.type_name = 'Sell' THEN t.price_by_broker
                    WHEN tt.type_name = 'Buy' THEN -t.price_by_broker
                    ELSE 0
                END AS amount,
                'trade' AS type
            FROM 
                trades t
                INNER JOIN bots b ON t.bot_id = b.id
                INNER JOIN tradetypes tt ON tt.id = t.type_id
            WHERE 
                b.user_id = :user_id
        ),
        
        -- Группируем по timestamp и type, суммируя amount
        grouped_data AS (
            SELECT 
                timestamp,
                SUM(amount) AS amount,
                type
            FROM 
                raw_data
            GROUP BY 
                timestamp, type
        ),
        
        -- Рассчитываем баланс
        calculated_balance AS (
            SELECT 
                timestamp,
                amount,
                type,
                SUM(amount) OVER (ORDER BY timestamp) AS balance
            FROM 
                grouped_data
        )
        
        SELECT 
            timestamp,
            balance,
            amount,
            type
        FROM 
            calculated_balance
        ORDER BY 
            timestamp;
        
    """)

    result = await db.execute(sql_query, {"user_id": user_id})
    rows = result.fetchall()

    history = [{
        "timestamp": row.timestamp,
        "money": float(row.balance),
        "amount": float(row.amount),
        "type": row.type
    } for row in rows]

    return history

@router.post("/logout")
def logout(response: Response):
    response.set_cookie("access_token", "", max_age=0, httponly=True)
    response.set_cookie("refresh_token", "", max_age=0, httponly=True)
    return {"message": "Logged out"}


@router.post("/auth")
async def authentication_user(
    db: AsyncSession = Depends(get_db),
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):

    if not refresh_token:
        return Response(status_code=403)

    if not access_token:
        refresh_user_id =  verify_access_token(refresh_token)
        if not refresh_user_id:
            return Response(status_code=401)
         
  
        result = await db.execute(select(User).where(User.id == refresh_user_id))
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        response = Response(status_code=200)
        access_token =   create_access_token(data = {"user_id":user.id},expires_delta = timedelta(minutes=10))
        response.set_cookie(
            key="access_token", value=access_token, httponly=True, max_age=access_cookie_time
        )
        return response
    user_id = verify_access_token(access_token)
    if not user_id:
        refresh_user_id =  verify_access_token(refresh_token)
        if not refresh_user_id:
            raise HTTPException(status_code=401, detail="Invalid or expired access token")
  
        result = await db.execute(select(User).where(User.id == refresh_user_id))
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        response = Response(status_code=200)
        access_token =   create_access_token(data = {"user_id":user.id},expires_delta = timedelta(days=2))
        response.set_cookie(
            key="access_token", value=access_token, httponly=True, max_age=access_cookie_time
        )
        return response

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        return Response(status_code=404)

    return {"message": "User authenticated", "user_id": user.id}


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/activate/{token}")
async def activate_account(token: str, db: AsyncSession = Depends(get_db)):
    user_id = verify_activation_token(token)
    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid or expired activation token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.activate is True:
        raise HTTPException(status_code=403, detail="Account is active")
    user.activate = True
    await db.commit()

    refresh_token = create_access_token(data={"user_id": user.id}, expires_delta=timedelta(days=7))
    access_token = create_access_token(data={"user_id": user.id}, expires_delta=timedelta(minutes=2))

    response = Response(status_code=200)
    response.set_cookie(
        key="refresh_token", value=refresh_token, httponly=True, max_age=refresh_cookie_time
    )
    response.set_cookie(
        key="access_token", value=access_token, httponly=True, max_age=access_cookie_time
    )

    return response


@router.get("/money_history/export")
async def export_money_history(
    access_token: str = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    user_id = verify_access_token(access_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
     
    sql_query = text("""
    WITH 
    trade_data AS (
        SELECT 
            t.time AS timestamp,
            CASE 
                WHEN tt.type_name = 'Sell' THEN t.price_by_broker
                WHEN tt.type_name = 'Buy' THEN -t.price_by_broker
                ELSE 0
            END AS amount,
            'trade' AS type,
            b.name AS bot_name,
            b.symbol
        FROM 
            trades t
            INNER JOIN bots b ON t.bot_id = b.id
            INNER JOIN tradetypes tt ON tt.id = t.type_id
        WHERE 
            b.user_id = :user_id
    ),
    
    transaction_data AS (
        SELECT 
            create_time AS timestamp,
            money AS amount,
            'deposit' AS type,
            NULL AS bot_name,
            NULL AS symbol
        FROM 
            transactions
        WHERE 
            user_id = :user_id
    ),
    
    combined_data AS (
        SELECT * FROM transaction_data
        UNION ALL
        SELECT * FROM trade_data
    ),
    
    calculated_balance AS (
        SELECT 
            timestamp,
            amount,
            type,
            bot_name,
            symbol,
            SUM(amount) OVER (ORDER BY timestamp) AS balance
        FROM 
            combined_data
    )
    
    SELECT 
        timestamp,
        balance,
        amount,
        type,
        bot_name,
        symbol
    FROM 
        calculated_balance
    ORDER BY 
        timestamp;
    """)

    result = await db.execute(sql_query, {"user_id": user_id})
    rows = result.fetchall()

    df = pd.DataFrame([{
        "Дата и время": row.timestamp,
        "Баланс": float(row.balance),
        "Сумма операции": float(row.amount),
        "Тип операции": row.type,
        "Имя бота": row.bot_name,
        "Символ": row.symbol
    } for row in rows])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='История операций', index=False)
        
        workbook = writer.book
        worksheet = writer.sheets['История операций']
        
 
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
 
        date_format = workbook.add_format({'num_format': 'dd.mm.yyyy hh:mm:ss'})
        
 
        format_green = workbook.add_format({'font_color': '#006100', 'bg_color': '#C6EFCE'})
        format_red = workbook.add_format({'font_color': '#9C0006', 'bg_color': '#FFC7CE'})
        
 
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
 
        worksheet.set_column('A:A', 20, date_format)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:D', 15)
        worksheet.set_column('E:E', 20)
        worksheet.set_column('F:F', 15)
        
 
        num_rows = len(df)
 
        if num_rows > 0:
 
            worksheet.conditional_format(
                f'C2:C{num_rows + 1}',  
                {
                    'type': 'cell',
                    'criteria': '>=',
                    'value': 0,
                    'format': format_green
                }
            )
            
 
            worksheet.conditional_format(
                f'C2:C{num_rows + 1}',
                {
                    'type': 'cell',
                    'criteria': '<',
                    'value': 0,
                    'format': format_red
                }
            )

    output.seek(0)
    headers = {
        'Content-Disposition': 'attachment; filename="money_history.xlsx"',
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }
    
    return StreamingResponse(output, headers=headers)