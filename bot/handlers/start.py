from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, Contact
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from database.models.role import RoleEnum
from database.session import async_session_factory
from services.user_service import UserService
from services.audit_service import AuditService
from bot.keyboards.common import (
    get_main_menu_user,
    get_main_menu_operator,
    get_main_menu_admin,
    get_request_contact_keyboard,
)


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()

    async with async_session_factory() as session:
        user_service = UserService(session)
        user = await user_service.register_or_update(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        await session.commit()

    if not user.phone:
        await message.answer(
            "Добро пожаловать! Для завершения регистрации, пожалуйста, отправьте номер телефона.",
            reply_markup=get_request_contact_keyboard(),
        )
        return

    await _send_main_menu(message, user)


@router.message(F.contact)
async def process_contact(message: Message, state: FSMContext) -> None:
    contact: Contact = message.contact

    async with async_session_factory() as session:
        user_service = UserService(session)
        user = await user_service.update_phone(
            telegram_id=message.from_user.id,
            phone=contact.phone_number,
        )
        await session.commit()

    if user:
        await message.answer("Номер телефона сохранён. Регистрация завершена!")
        await _send_main_menu(message, user)
    else:
        await message.answer(
            "Пользователь не найден. Пожалуйста, нажмите /start"
        )


async def _send_main_menu(message: Message, user) -> None:
    role = user.role.name if user.role else RoleEnum.USER
    if hasattr(role, "value"):
        role = RoleEnum(role.value)

    if role == RoleEnum.ADMIN:
        await message.answer(
            "Вы вошли как Администратор 👑",
            reply_markup=get_main_menu_admin(),
        )
    elif role == RoleEnum.OPERATOR:
        await message.answer(
            "Вы вошли как Оператор 🛠",
            reply_markup=get_main_menu_operator(),
        )
    else:
        await message.answer(
            "Вы вошли как Пользователь 👤",
            reply_markup=get_main_menu_user(),
        )
