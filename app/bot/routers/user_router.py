from aiogram import Router

from app.bot.handlers.start import router as start_router
from app.bot.handlers.user import router as user_handler_router

user_router = Router(name="user")
user_router.include_router(start_router)
user_router.include_router(user_handler_router)
