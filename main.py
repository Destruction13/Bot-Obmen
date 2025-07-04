import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

import db
from utils import parse_shift, format_shift, parse_time_range
import keyboards
import calendar_utils as cal
from aiogram_calendar import simple_calendar

logging.basicConfig(level=logging.INFO)
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN not set')
DEV_ADMINS = {int(uid) for uid in os.getenv('DEV_ADMINS', '').split(',') if uid.isdigit()}

bot = Bot(BOT_TOKEN, parse_mode='HTML')
dp = Dispatcher()

db.init_db()


class AddShift(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()


class OfferShift(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()


@dp.message(Command('start'))
async def cmd_start(message: Message):
    await message.answer(
        'Добро пожаловать! Выберите действие:',
        reply_markup=keyboards.main_kb,
    )


@dp.message(Command('add'))
@dp.message(F.text == '\u2795 Добавить смену')
async def cmd_add(message: Message, state: FSMContext):
    await message.answer('Выберите дату:', reply_markup=await cal.start_calendar())
    await state.set_state(AddShift.waiting_for_date)


@dp.callback_query(simple_calendar.SimpleCalendarCallback.filter(), AddShift.waiting_for_date)
async def add_shift_pick_date(callback: CallbackQuery, callback_data: simple_calendar.SimpleCalendarCallback, state: FSMContext):
    selected, date = await cal.process_calendar(callback, callback_data)
    if selected:
        await state.update_data(date=date)
        await callback.message.answer('Введите время как "HH:MM - HH:MM"', reply_markup=ReplyKeyboardRemove())
        await state.set_state(AddShift.waiting_for_time)
    await callback.answer()


@dp.message(AddShift.waiting_for_time)
async def process_add_shift(message: Message, state: FSMContext):
    data = await state.get_data()
    date = data.get('date')
    if not date:
        await message.answer('Ошибка состояния. Попробуйте снова.')
        await state.clear()
        return
    parsed = parse_time_range(message.text, date)
    if not parsed:
        await message.answer('Неверный формат времени. Используйте "HH:MM - HH:MM"')
        return
    start, end = parsed
    shift_id = db.add_shift(message.from_user.id, message.from_user.username or '', start, end)
    await message.answer(f'Смена сохранена с ID {shift_id}.', reply_markup=keyboards.main_kb)
    await state.clear()


@dp.message(Command('list'))
@dp.message(F.text == '\U0001F4C4 Доступные смены')
async def cmd_list(message: Message):
    include_self = db.is_dev(message.from_user.id)
    shifts = db.list_active_shifts(message.from_user.id, include_self=include_self)
    if not shifts:
        await message.answer('Нет доступных смен.')
        return
    text = '\n'.join(format_shift(s) for s in shifts)
    await message.answer(text)


@dp.message(Command('my'))
@dp.message(F.text == '\U0001F4CC Мои смены')
async def cmd_my(message: Message):
    shifts = db.list_user_shifts(message.from_user.id)
    if not shifts:
        await message.answer('У вас нет смен.')
        return
    text = '\n'.join(format_shift(s) for s in shifts)
    await message.answer(text)


@dp.message(Command('cancel'))
@dp.message(F.text == '\U0001F5D1 Удалить смену')
async def cmd_cancel(message: Message, command: CommandObject):
    if not command.args:
        if message.text.startswith('\U0001F5D1'):
            await message.answer('Используйте /cancel <id> для удаления смены.')
        else:
            await message.answer('Использование: /cancel <id>')
        return
    if not command.args.isdigit():
        await message.answer('ID должен быть числом')
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
    dev = db.is_dev(message.from_user.id)
    if not target or target['status'] != 'active' or (target['user_id'] == message.from_user.id and not dev):
        await message.answer('Эта смена недоступна для обмена.')
        return
    await state.update_data(target_shift_id=target_id)
    await message.answer('Выберите дату вашей смены:', reply_markup=await cal.start_calendar())
    await state.set_state(OfferShift.waiting_for_date)


@dp.callback_query(simple_calendar.SimpleCalendarCallback.filter(), OfferShift.waiting_for_date)
async def offer_pick_date(callback: CallbackQuery, callback_data: simple_calendar.SimpleCalendarCallback, state: FSMContext):
    selected, date = await cal.process_calendar(callback, callback_data)
    if selected:
        await state.update_data(date=date)
        await callback.message.answer('Введите время вашей смены "HH:MM - HH:MM"', reply_markup=ReplyKeyboardRemove())
        await state.set_state(OfferShift.waiting_for_time)
    await callback.answer()


@dp.message(OfferShift.waiting_for_time)
async def process_offer_shift(message: Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get('target_shift_id')
    date = data.get('date')
    if not date or not target_id:
        await message.answer('Ошибка состояния. Попробуйте заново.')
        await state.clear()
        return
    parsed = parse_time_range(message.text, date)
    if not parsed:
        await message.answer('Неверный формат времени. Используйте "HH:MM - HH:MM"')
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


@dp.message(Command('dev_on'))
async def cmd_dev_on(message: Message):
    if message.from_user.id not in DEV_ADMINS:
        await message.answer('Недостаточно прав.')
        return
    db.set_dev_mode(message.from_user.id, True)
    await message.answer('Режим разработчика включён.')


@dp.message(Command('dev_off'))
async def cmd_dev_off(message: Message):
    if message.from_user.id not in DEV_ADMINS:
        await message.answer('Недостаточно прав.')
        return
    db.set_dev_mode(message.from_user.id, False)
    await message.answer('Режим разработчика выключен.')


@dp.message(Command('dev_status'))
async def cmd_dev_status(message: Message):
    await message.answer('Dev mode: ' + ('on' if db.is_dev(message.from_user.id) else 'off'))


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
