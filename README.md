# Серверная часть информационно-аналитической системы для тестирования торговых стратегий TradeSnake


## О проекте

TradeSnake — система для тестирования торговых стратегий на бирже.

Особенности:
- Тестирование на исторических и реальных данных
- Просмотр статистики портфеля ботов
- Гибкая настройка и создание ботов с готовыми стратегиями
- Обновление стратегий на серверной части

---
## О сервисе
 Основной сервис для авторизации и работы с базой данных.

---
## Быстрый старт

```bash
git clone https://github.com/ChornyChay1/TradeSnakeBackPython.git
cd TradeBot
pip install -r requirements.txt
python TradeBot.py
```
---
## Используемые библиотеки

- FastAPI  
- Pydantic  
- SQLAlchemy  
- hypercorn


---
## Особенности
В данном репозитории скрыта часть, связанная с авторизацией.
BackEnd будет неполноценным без подключения сервиса торговли на С++ [Вот тут](https://github.com/ChornyChay1/TradeSnakeBackendC) 

---
## Архитектура
### Диаграмма развертывания:
<p align="center">
  <img src="./TradeBot/presentation/deployment_diagram.png" width="400" alt="Диаграмма развертывания" />
</p>

### Диаграмма компонентов:
<p align="center">
  <img src="./TradeBot/presentation/component_diagram.png" width="400" alt="Диаграмма компонентов" />
</p>

---
## Связанные репозитории

Backend торговый сервис: [BackEndС](https://github.com/ChornyChay1/TradeSnakeBackendC)  
Frontend: [Frontend](https://github.com/ChornyChay1/TradeSnakeFront)  

