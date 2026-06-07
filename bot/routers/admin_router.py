from aiogram import Router

from bot.handlers.admin import router as admin_handler_router

admin_router = Router(name="admin")
admin_router.include_router(admin_handler_router)
