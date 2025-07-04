from typing import List, Dict
import numpy as np

def calculate_ema(prices: List[float], dates: List[str], period: int) -> Dict[str, float]:
    """
    Рассчитывает экспоненциальную скользящую среднюю (EMA) для переданных цен.

    :param prices: Список цен для расчета EMA.
    :param dates: Список дат для соответствующих цен.
    :param period: Период для расчёта EMA.
    :return: Словарь {дата: значение EMA}.
    """
    ema = {}
    alpha = 2 / (period + 1)  # Параметр сглаживания для EMA

    # Начальная EMA — простая скользящая средняя для первых значений
    ema[dates[period-1]] = np.mean(prices[:period])  # Первая EMA как SMA

    for i in range(period, len(prices)):
        new_ema = (prices[i] - ema[dates[i-1]]) * alpha + ema[dates[i-1]]
        ema[dates[i]] = new_ema

    return ema

def calculate_ma(prices: List[float], dates: List[str], period: int) -> Dict[str, float]:
    """
    Рассчитывает простую скользящую среднюю (MA) для переданных цен.

    :param prices: Список цен для расчета MA.
    :param dates: Список дат для соответствующих цен.
    :param period: Период для расчёта скользящей средней.
    :return: Словарь {дата: значение MA}.
    """
    if period <= 0:
        raise ValueError("Период должен быть положительным числом.")
    if len(prices) < period:
        raise ValueError("Количество цен должно быть больше или равно периоду.")
    
    ma = {}

    # Проходим по ценам, рассчитывая среднее для каждого окна
    for i in range(len(prices) - period + 1):
        window = prices[i:i + period]  # Выбираем окно из цен длиной "period"
        ma[dates[i + period - 1]] = sum(window) / period  # Среднее значение для текущего окна
    
    return ma

def calculate_rsi(prices: List[float], dates: List[str], period: int) -> Dict[str, float]:
    if len(prices) < period:
        raise ValueError("Количество цен должно быть больше или равно периоду.")

    gains = []
    losses = []

    # Собираем начальные данные для первых периодов
    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        if change >= 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(-change)

    # Начальные средние значения
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    rsi = {}

    # Рассчитываем RSI для каждого периода
    for i in range(period, len(prices)):
        if avg_loss == 0:
            rsi_value = 100
        else:
            rs = avg_gain / avg_loss
            rsi_value = 100 - (100 / (1 + rs))

        rsi[dates[i]] = rsi_value

        # Обновляем средние значения прироста и потерь
        if i < len(prices) - 1:
            change = prices[i + 1] - prices[i]
            gain = max(0, change)
            loss = max(0, -change)

            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

    return rsi
