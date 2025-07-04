from fastapi import FastAPI, Query
from typing import Optional
from Brokers.MetaTrader5 import MetaTrader5Adapter
from datetime import datetime
from typing import Dict,Any
from Testing.StrategyTester import StrategyTester
from Adapters.BrokerAdaper import BrokerAdapter
from Strategies.MovingAverageStrategy import MovingAverageStrategy
from Strategies.DoubleMovingAverageStrategy import DoubleMovingAverageStrategy
from Strategies.TripleMovingAverageStrategy import MovingAverageTripleStrategy
from Strategies.Trand_RSI_Double_MA import TrendFollowingStrategy

# Инициализация FastAPI приложения
from Utils.utils import calculate_ema


# Инициализация FastAPI приложения
app = FastAPI()

# # Инициализация адаптера
# adapter = MetaTrader5Adapter()
# login = 89295934  # замените на реальный логин
# password = "V@AlTo2e"  # замените на реальный пароль
# server = "MetaQuotes-Demo"  # замените на реальный сервер

# if adapter.enter(password=password, login=login, server=server):
#     print("Успешный вход в MetaTrader5")
# else:
#     print("Ошибка входа в MetaTrader5") 
# @app.get("/get_symbol_history")
# async def get_symbol_history(symbol: str, start_date: str, end_date: str):
#     """
#     Получение исторических данных для символа за указанный диапазон дат.
#     :param symbol: Символ для которого запрашиваем данные.
#     :param start_date: Дата начала в формате "YYYY-MM-DD".
#     :param end_date: Дата конца в формате "YYYY-MM-DD".
#     :return: Исторические данные о ценах для символа.
#     """
#     try:
#         # Преобразуем строки в datetime
#         start_date = datetime.strptime(start_date, "%Y-%m-%d")
#         end_date = datetime.strptime(end_date, "%Y-%m-%d")
#             # Пробуем войти в терминал MetaTrader5

#         # Получаем данные
#         historical_data = adapter.get_historical_data(symbol, start_date, end_date)
        
#         # Проверяем, если есть ошибка
#         if isinstance(historical_data, dict) and "error" in historical_data:
#             return historical_data  # Возвращаем ошибку, если она есть

#         return {"symbol": symbol, "historical_data": historical_data}
    
#     except Exception as e:
#         return {"error": str(e)}

# @app.get("/test_strategy")
# async def test_strategy(
#     symbol: str,  
#     start_date: str, 
#     end_date: str,
#     quantity: int,
#     period: Optional[int] = None,
#     shortPeriod: Optional[int] = None,
#     longPeriod: Optional[int] = None,
#     rsi_period: Optional[int] = None,
#     strategy_type: str = "moving_average"  # Новый параметр для выбора стратегии
# ) -> Dict[str, Any]:
#     """
#     Тестирует стратегию на указанном активе за указанный период.

#     :param symbol: Символ актива.
#     :param start_date: Начало тестирования в формате "YYYY-MM-DD".
#     :param end_date: Конец тестирования в формате "YYYY-MM-DD".
#     :param strategy_type: Тип стратегии для тестирования.
#     :return: Результаты тестирования.
#     """
#     try:
#         # Преобразуем строки в datetime
#         start_date = datetime.strptime(start_date, "%Y-%m-%d")
#         end_date = datetime.strptime(end_date, "%Y-%m-%d") 
        
#         # Выбор стратегии в зависимости от параметра strategy_type
#         if strategy_type == "moving_average":
#             if period is None:
#                 return {"error": "Параметр 'period' обязателен для стратегии Moving Average"}
#             strategy = MovingAverageStrategy(period=period, quantity=quantity)
#         elif strategy_type == "double_moving_average":
#             if shortPeriod is None or longPeriod is None:
#                 return {"error": "Параметры 'shortPeriod' и 'longPeriod' обязательны для стратегии Double Moving Average"}
#             strategy = DoubleMovingAverageStrategy(short_period=shortPeriod, long_period=longPeriod, quantity=quantity)

#         elif strategy_type == "triple_moving_average":
#             strategy = MovingAverageTripleStrategy(quantity=quantity)
#         elif strategy_type == "trand_strategy":
#             if shortPeriod is None or longPeriod is None or rsi_period is None:
#                 return {"error": "Параметры 'shortPeriod' и 'longPeriod' и rsi_period обязательны для стратегии TrandStrategy"}
#             strategy = TrendFollowingStrategy(short_period=shortPeriod, long_period=longPeriod,rsi_period=rsi_period, quantity=quantity)
#         else:
#             return {"error": f"Неизвестный тип стратегии: {strategy_type}"}
        
#         tester = StrategyTester(strategy, adapter)
        
#         # Запускаем тестирование стратегии и получаем результаты
#         test_results = tester.run_test(symbol, start_date, end_date)
        
#         # Формируем результат
#         response = []
#         for result in test_results["results"]:
#             response.append({
#                 "timestamp": result["timestamp"],
#                 "open": result.get("open", None),  # Если open есть в результатах
#                 "close": result.get("close", None),
#                 "high": result.get("high", None),
#                 "low": result.get("low", None), 
#                 "buy": {
#                     "price": result["buy"]["price"] if result["buy"] else None,
#                     "quantity": result["buy"]["quantity"] if result["buy"] else None
#                 },
#                 "sell": {
#                     "price": result["sell"]["price"] if result["sell"] else None,
#                     "quantity": result["sell"]["quantity"] if result["sell"] else None
#                 }
#             })
        
#         statistic = []
#         # Добавляем статистику по покупкам/продажам и профиту в ответ
#         statistic.append({
#             "total_buy_quantity": test_results["total_buy_quantity"],
#             "total_sell_quantity": test_results["total_sell_quantity"],
#             "average_buy_price": test_results["average_buy_price"],
#             "average_sell_price": test_results["average_sell_price"],
#             "buy_count": test_results["buy_count"],
#             "sell_count": test_results["sell_count"],
#             "profit": test_results["profit"],
#             "profit_percent": test_results["profit_percent"],
#             "good_sell": test_results["good_sell"]
#         })
        
#         return {"data": response, "statistic": statistic}

#     except Exception as e:
#         return {"error": str(e)}

     