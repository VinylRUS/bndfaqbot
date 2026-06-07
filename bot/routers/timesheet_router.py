from aiogram import Router

from bot.handlers.timesheet import router as timesheet_handler_router

timesheet_router = Router()
timesheet_router.include_router(timesheet_handler_router)
