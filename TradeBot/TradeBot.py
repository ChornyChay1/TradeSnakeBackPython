import hypercorn
from API.routes import app    
from hypercorn.config import Config
from hypercorn.asyncio import serve
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
import asyncio
import hypercorn.asyncio
from hypercorn.config import Config
import os
from DB.schemas import init_db 
from API.user import router as user_router
from API.bots import router as bots_router
from API.utils import router as utils_router

app.include_router(user_router)
app.include_router(utils_router)
app.include_router(bots_router)



# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","http://localhost:3001"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)


if __name__ == "__main__": 

    asyncio.run(init_db())
    config = Config()
    config.bind = ["127.0.0.1:8000"]  
    asyncio.run(hypercorn.asyncio.serve(app, config))

