import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils import markdown

import db
from utils import format_shift, parse_time_range, format_shift_short, md_escape, MONTHS_LIST
import keyboards
import rus_calendar as cal
from aiogram_calendar import simple_calendar
import messages

logging.basicConfig(level=logging.INFO)

# Токен бота хранится напрямую в коде. Не использовать env для простоты демонстрации.
BOT_TOKEN = "7355813660:AAFE6dOJMaHuCMVCRXC6M8gen4ZlamnbZmM"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

db.init_db()


class AddShift(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()


class OfferShift(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()
    choosing_my_shift = State()


class ViewDate(StatesGroup):
    waiting_for_date = State()


@dp.message(Command('start'))
async def cmd_start(message: Message):
    await message.answer(
        messages.WELCOME,
        reply_markup=keyboards.main_kb,
    )


@dp.message(Command('add'))
@dp.message(F.text == '\u2795 Добавить смену')
async def cmd_add(message: Message, state: FSMContext):
    await message.answer(messages.SELECT_DATE, reply_markup=await cal.start_calendar())
    await state.set_state(AddShift.waiting_for_date)


@dp.message(F.text == '\U0001F4C5 Доступные смены')
async def cmd_pick_date(message: Message, state: FSMContext):
    await message.answer(messages.SELECT_DATE, reply_markup=await cal.start_calendar())
    await state.set_state(ViewDate.waiting_for_date)


@dp.callback_query(simple_calendar.SimpleCalendarCallback.filter(), AddShift.waiting_for_date)
async def add_shift_pick_date(callback: CallbackQuery, callback_data: simple_calendar.SimpleCalendarCallback, state: FSMContext):
    selected, date = await cal.process_calendar(callback, callback_data)
    if selected:
        await state.update_data(date=date)
        await callback.message.answer(messages.ENTER_TIME, reply_markup=ReplyKeyboardRemove())
        await state.set_state(AddShift.waiting_for_time)
    await callback.answer()


@dp.callback_query(F.data.startswith('del:'))
async def delete_callback(callback: CallbackQuery):
    """Handle shift deletion from inline keyboard."""
    shift_id = int(callback.data.split(':')[1])
    success = db.delete_shift(shift_id, callback.from_user.id)
    text = 'Смена удалена ✅' if success else 'Не удалось удалить смену.'
    await callback.message.edit_text(text)
    await callback.answer()


@dp.callback_query(F.data.startswith('shift:'))
async def show_shift(callback: CallbackQuery):
    shift_id = int(callback.data.split(':')[1])
    shift = db.get_shift(shift_id)
    if not shift:
        await callback.answer('Смена не найдена', show_alert=True)
        return
    text = format_shift_short(shift) + f"\nРазместил: {md_escape('@'+shift['username']) if shift['username'] else shift['user_id']}"
    await callback.message.answer(
        text,
        reply_markup=keyboards.shift_detail_keyboard(shift['username'], shift_id),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith('offer:'))
async def inline_offer(callback: CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split(':')[1])
    target = db.get_shift(target_id)
    dev = db.is_dev(callback.from_user.id)
    if not target or target['status'] != 'active' or (target['user_id'] == callback.from_user.id and not dev):
        await callback.answer('Эта смена недоступна для обмена.', show_alert=True)
        return
    date = datetime.fromisoformat(target['start_time'])
    await state.update_data(target_shift_id=target_id, date=date)
    my_shifts = db.get_user_shifts_by_date(callback.from_user.id, date)
    if my_shifts:
        await callback.message.answer(
            messages.CHOOSE_MY_SHIFT,
            reply_markup=keyboards.my_shifts_keyboard(my_shifts),
        )
        await state.set_state(OfferShift.choosing_my_shift)
    else:
        await callback.message.answer(messages.NO_MY_SHIFT_ON_DATE)
        await state.set_state(OfferShift.waiting_for_time)
    await callback.answer()


@dp.callback_query(F.data.startswith('myshift:'), OfferShift.choosing_my_shift)
async def choose_my_shift(callback: CallbackQuery, state: FSMContext):
    my_id = int(callback.data.split(':')[1])
    data = await state.get_data()
    target_id = data.get('target_shift_id')
    if not target_id:
        await callback.answer('Ошибка состояния', show_alert=True)
        await state.clear()
        return
    my_shift = db.get_shift(my_id)
    if not my_shift or my_shift['user_id'] != callback.from_user.id:
        await callback.answer('Смена не найдена', show_alert=True)
        await state.clear()
        return
    start = datetime.fromisoformat(my_shift['start_time'])
    end = datetime.fromisoformat(my_shift['end_time'])
    offer_id = db.offer_shift(
        target_id,
        callback.from_user.id,
        callback.from_user.username or '',
        start,
        end,
    )
    if not offer_id:
        await callback.message.answer('Не удалось создать предложение. Возможно, смена уже занята.')
        await state.clear()
        await callback.answer()
        return
    target = db.get_shift(target_id)
    await callback.message.answer(messages.OFFER_SENT)
    await state.clear()
    if target:
        try:
            shift_text = f"{start.day} {MONTHS_LIST[start.month-1]} {start.strftime('%H:%M')} — {end.strftime('%H:%M')}"
            await bot.send_message(
                target['user_id'],
                f"Пользователь @{callback.from_user.username or callback.from_user.id} предлагает обмен на вашу смену ID {target_id}.\n"
                f"Его смена ID {offer_id}: {shift_text}\n"
                f"Чтобы подтвердить, отправьте /approve {offer_id}"
            )
        except Exception as e:
            logging.error('Failed to send offer message: %s', e)
    await callback.answer()


@dp.callback_query(simple_calendar.SimpleCalendarCallback.filter(), ViewDate.waiting_for_date)
async def view_date_pick(callback: CallbackQuery, callback_data: simple_calendar.SimpleCalendarCallback, state: FSMContext):
    selected, date = await cal.process_calendar(callback, callback_data)
    if selected:
        shifts = db.list_shifts_by_date(date, callback.from_user.id, include_self=db.is_dev(callback.from_user.id))
        if not shifts:
            await callback.message.answer(messages.NO_SHIFTS)
            await state.clear()
        else:
            await callback.message.answer(
                f"Смены на {date.day} {MONTHS_LIST[date.month - 1]}:",
                reply_markup=keyboards.shifts_keyboard(shifts, 'shift'),
            )
            await state.clear()
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
        await message.answer(messages.TIME_FORMAT_ERROR)
        return
    start, end = parsed
    shift_id = db.add_shift(message.from_user.id, message.from_user.username or '', start, end)
    await message.answer(f"{messages.SHIFT_SAVED} ID {shift_id}.", reply_markup=keyboards.main_kb)
    await state.clear()


@dp.message(Command('list'))
async def cmd_list(message: Message):
    include_self = db.is_dev(message.from_user.id)
    shifts = db.list_active_shifts(message.from_user.id, include_self=include_self)
    if not shifts:
        await message.answer(messages.NO_SHIFTS)
        return
    text = '\n'.join(format_shift(s) for s in shifts)
    await message.answer(text)


@dp.message(Command('my'))
@dp.message(F.text == '\U0001F4CC Мои смены')
async def cmd_my(message: Message):
    shifts = db.list_user_shifts(message.from_user.id)
    if not shifts:
        await message.answer(messages.MY_NO_SHIFTS)
        return
    text = '\n'.join(format_shift(s) for s in shifts)
    await message.answer(text)


@dp.message(Command('cancel'))
@dp.message(F.text == '\U0001F5D1 Удалить смену')
async def cmd_cancel(message: Message, command: CommandObject, state: FSMContext):
    if command.args and command.args.isdigit():
        success = db.delete_shift(int(command.args), message.from_user.id)
        await message.answer('Смена удалена ✅' if success else 'Не удалось удалить смену.')
        return
    shifts = db.list_user_shifts(message.from_user.id)
    if not shifts:
        await message.answer(messages.MY_NO_SHIFTS)
        return
    await message.answer(messages.CHOOSE_SHIFT_DELETE, reply_markup=keyboards.delete_shift_keyboard(shifts))


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
    await message.answer(messages.SELECT_DATE, reply_markup=await cal.start_calendar())
    await state.set_state(OfferShift.waiting_for_date)


@dp.callback_query(simple_calendar.SimpleCalendarCallback.filter(), OfferShift.waiting_for_date)
async def offer_pick_date(callback: CallbackQuery, callback_data: simple_calendar.SimpleCalendarCallback, state: FSMContext):
    selected, date = await cal.process_calendar(callback, callback_data)
    if selected:
        await state.update_data(date=date)
        await callback.message.answer(messages.ENTER_TIME, reply_markup=ReplyKeyboardRemove())
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
        await message.answer(messages.TIME_FORMAT_ERROR)
        return
    start, end = parsed
    offer_id = db.offer_shift(target_id, message.from_user.id, message.from_user.username or '', start, end)
    if not offer_id:
        await message.answer('Не удалось создать предложение. Возможно, смена уже занята.')
        await state.clear()
        return
    target = db.get_shift(target_id)
    await message.answer(messages.OFFER_SENT)
    await state.clear()
    if target:
        try:
            shift_text = f"{start.day} {MONTHS_LIST[start.month-1]} {start.strftime('%H:%M')} — {end.strftime('%H:%M')}"
            await bot.send_message(
                target['user_id'],
                f"Пользователь @{message.from_user.username or message.from_user.id} предлагает обмен на вашу смену ID {target_id}.\n"
                f"Его смена ID {offer_id}: {shift_text}\n"
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
    db.delete_shift_force(offer['id'])
    db.delete_shift_force(target['id'])
    link = messages.EXCHANGE_CONFIRMED.format(
        user=markdown.link(md_escape(f"@{offer['username']}") if offer['username'] else md_escape(str(offer['user_id'])),
                           f"https://t.me/{offer['username']}" if offer['username'] else f"tg://user?id={offer['user_id']}")
    )
    await message.answer(link)
    try:
        other_link = markdown.link(
            md_escape(f"@{message.from_user.username}") if message.from_user.username else md_escape(str(message.from_user.id)),
            f"https://t.me/{message.from_user.username}" if message.from_user.username else f"tg://user?id={message.from_user.id}"
        )
        await bot.send_message(offer['user_id'], messages.EXCHANGE_CONFIRMED.format(user=other_link))
    except Exception as e:
        logging.error('Failed to notify user: %s', e)


@dp.message(Command('developer'))
async def cmd_developer(message: Message):
    """Toggle developer mode for current user."""
    enabled = not db.is_dev(message.from_user.id)
    db.set_dev_mode(message.from_user.id, enabled)
    await message.answer(
        'Режим разработчика ' + ('включён.' if enabled else 'выключен.')
    )


@dp.message(Command('dev_status'))
async def cmd_dev_status(message: Message):
    await message.answer(
        'Режим разработчика: ' + ('on' if db.is_dev(message.from_user.id) else 'off')
    )


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
