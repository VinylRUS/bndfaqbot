from aiogram import Router

from bot.handlers.operator import router as operator_handler_router

operator_router = Router(name="operator")
operator_router.include_router(operator_handler_router)
