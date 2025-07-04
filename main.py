import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

import db
from utils import parse_shift, format_shift

logging.basicConfig(level=logging.INFO)
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN not set')

bot = Bot(BOT_TOKEN, parse_mode='HTML')
dp = Dispatcher()

db.init_db()


class AddShift(StatesGroup):
    waiting_for_shift = State()


class OfferShift(StatesGroup):
    waiting_for_shift = State()


@dp.message(Command('start'))
async def cmd_start(message: Message):
    await message.answer(
        'Добро пожаловать!\n'
        'Доступные команды:\n'
        '/add - добавить смену\n'
        '/list - список смен\n'
        '/offer <id> - предложить обмен\n'
        '/approve <id> - подтвердить обмен\n'
        '/my - мои смены\n'
        '/cancel <id> - удалить смену'
    )


@dp.message(Command('add'))
async def cmd_add(message: Message, state: FSMContext):
    await message.answer('Введите смену в формате: "7 июля, 10:45 — 19:45"')
    await state.set_state(AddShift.waiting_for_shift)


@dp.message(AddShift.waiting_for_shift)
async def process_add_shift(message: Message, state: FSMContext):
    parsed = parse_shift(message.text)
    if not parsed:
        await message.answer('Не удалось разобрать дату. Попробуйте ещё раз.')
        return
    start, end = parsed
    shift_id = db.add_shift(message.from_user.id, message.from_user.username or '', start, end)
    await message.answer(f'Смена сохранена с ID {shift_id}.')
    await state.clear()


@dp.message(Command('list'))
async def cmd_list(message: Message):
    shifts = db.list_active_shifts(message.from_user.id)
    if not shifts:
        await message.answer('Нет доступных смен.')
        return
    text = '\n'.join(format_shift(s) for s in shifts)
    await message.answer(text)


@dp.message(Command('my'))
async def cmd_my(message: Message):
    shifts = db.list_user_shifts(message.from_user.id)
    if not shifts:
        await message.answer('У вас нет смен.')
        return
    text = '\n'.join(format_shift(s) for s in shifts)
    await message.answer(text)


@dp.message(Command('cancel'))
async def cmd_cancel(message: Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        await message.answer('Использование: /cancel <id>')
        return
    success = db.delete_shift(int(command.args), message.from_user.id)
    if success:
        await message.answer('Смена удалена.')
    else:
        await message.answer('Не удалось удалить смену.')


@dp.message(Command('offer'))
async def cmd_offer(message: Message, command: CommandObject, state: FSMContext):
    if not command.args or not command.args.isdigit():
        await message.answer('Использование: /offer <id>')
        return
    target_id = int(command.args)
    target = db.get_shift(target_id)
    if not target or target['status'] != 'active' or target['user_id'] == message.from_user.id:
        await message.answer('Эта смена недоступна для обмена.')
        return
    await state.update_data(target_shift_id=target_id)
    await message.answer('Введите вашу смену в формате: "7 июля, 10:45 — 19:45"')
    await state.set_state(OfferShift.waiting_for_shift)


@dp.message(OfferShift.waiting_for_shift)
async def process_offer_shift(message: Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get('target_shift_id')
    parsed = parse_shift(message.text)
    if not parsed:
        await message.answer('Не удалось разобрать дату. Попробуйте ещё раз.')
        return
    start, end = parsed
    offer_id = db.offer_shift(target_id, message.from_user.id, message.from_user.username or '', start, end)
    if not offer_id:
        await message.answer('Не удалось создать предложение. Возможно, смена уже занята.')
        await state.clear()
        return
    target = db.get_shift(target_id)
    await message.answer('Предложение отправлено владельцу смены.')
    await state.clear()
    if target:
        try:
            await bot.send_message(
                target['user_id'],
                f"Пользователь @{message.from_user.username or message.from_user.id} предлагает обмен на вашу смену ID {target_id}.\n"
                f"Его смена ID {offer_id}: {start.strftime('%d %B %H:%M')} - {end.strftime('%H:%M')}\n"
                f"Чтобы подтвердить, отправьте /approve {offer_id}"
            )
        except Exception as e:
            logging.error('Failed to send offer message: %s', e)


@dp.message(Command('approve'))
async def cmd_approve(message: Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        await message.answer('Использование: /approve <offer_id>')
        return
    offer_id = int(command.args)
    result = db.approve_offer(offer_id, message.from_user.id)
    if not result:
        await message.answer('Не удалось подтвердить предложение.')
        return
    offer, target = result
    await message.answer('Обмен подтверждён!')
    try:
        await bot.send_message(offer['user_id'], f'Ваше предложение обмена подтверждено!')
    except Exception as e:
        logging.error('Failed to notify user: %s', e)


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
