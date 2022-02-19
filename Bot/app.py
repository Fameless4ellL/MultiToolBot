import asyncio
import logging
import os
import sched
import sqlite3
import datetime

from typing import Dict
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.utils.helper import ListItem, Helper, HelperMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ParseMode, ContentType
from aiogram.utils.markdown import text, bold

from Tasks import timerTasks
import Scan
from Config import API_TOKEN
from Tasks.TimePicker.timepicker import InlineTimepicker
from Tasks.simple_calendar import calendar_callback as simple_cal_callback
from keyboards import inline_kb1, inline_kb2, inline_kb3, inline_kb6
from Tasks.simple_calendar import SimpleCalendar
from Tasks.urils import get_expire_time
import ssl

ssl._create_default_https_context = ssl._create_unverified_context
# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
inline_timepicker = InlineTimepicker()

sched = AsyncIOScheduler()
sched.start()


# Introduce Start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    """
    This handler will be called when user sends `/start` or `/help` command
    """
    await message.answer("Hi {user}!\nI'm @HandyMultiTBot! I was created to make your job easier. So far, I can't do "
                         "much. but it's only a matter of time.\n".format(user=message.from_user.full_name))


# Introduce help
# TODO update help command, add more command and instruction for them
@dp.message_handler(commands=['help'])
async def process_help_command(message: types.Message):
    msg = text(bold('I can handle this commands:'),
               '\n/Scan - analog scanner. prepare an image, remove shadows and unnecessary irregularities, convert to '
               'pdf format if desired. also can scan QRcode',
               '\n/timer - creates a timer with button to stop',
               '\n/pomodoro - tracks your productivity with a reminder of rest and work',
               '\n  ↳/pm_stop',
               '\n/remind - creating a reminder with exact date and time',
               '\n  ↳/list_rm',
               '\n  ↳/update_rm',
               '\n  ↳/delete_rm', sep='\n')
    await message.answer(msg, parse_mode=ParseMode.MARKDOWN)


# ============================ Pomodoro Timer handler ==================================
class Reminder(Helper):
    mode = HelperMode.snake_case
    TITLE = ListItem()
    DATE = ListItem()


# States
class Form(StatesGroup):
    ReminderTitle = State()
    ReminderChangeTitle = State()
    ReminderTask = State()
    ReminderDate = State()
    Title = State()
    work_time = State()
    break_time = State()


@dp.message_handler(commands='pomodoro')
@dp.throttled(lambda msg, loop, *args, **kwargs: loop.create_task(bot.send_message(msg.from_user.id, "Throttled")),
              rate=1)
async def cmd_start(message: types.Message):
    """
    Conversation's entry point
    """
    if sched.get_job(job_id=str(message.from_user.id)):
        await message.answer("Pomodoro timer already working!\n - stop command : /pm_stop")
        return
    # Set state
    await Form.Title.set()

    await message.reply("What our Task?")


# You can use state '*' if you need to handle all states
@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info('Cancelling state %r', current_state)
    # Cancel state and inform user about it
    await state.finish()
    # And remove keyboard (just in case)
    await message.reply('Cancelled.', reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(state=Form.Title)
async def process_title(message: types.Message, state: FSMContext):
    """
    Process user title
    """
    async with state.proxy() as data:
        data['Title'] = message.text

    await Form.next()
    await message.reply("How long will we work for one pomodoro?\n if you do not know how much you need then put 25 "
                        "minutes")


@dp.message_handler(lambda message: not message.text.isdigit(), state=Form.work_time)
async def process_work_time_invalid(message: types.Message):
    """
    If work_time is invalid
    """
    return await message.reply("Age gotta be a number.\nHow long will we work for one pomodoro? (digits only)")


@dp.message_handler(state=Form.work_time)
async def process_work_time(message: types.Message, state: FSMContext):
    """
    Process user work_time
    """
    async with state.proxy() as data:
        data['work_time'] = message.text

    await Form.next()
    await message.reply("How long will we rest for one pomodoro? this is usually 5 minutes")


@dp.message_handler(lambda message: not message.text.isdigit(), state=Form.break_time)
async def process_break_time_invalid(message: types.Message):
    """
    If break_time is invalid
    """
    return await message.reply("Age gotta be a number.\nHow long will we rest for one pomodoro? (digits only)")


@dp.message_handler(lambda message: message.text.isdigit(), state=Form.break_time)
async def process_break_time(message: types.Message, state: FSMContext):
    # Update state and data
    async with state.proxy() as data:
        data['break_time'] = message.text

    await Form.next()
    await state.update_data(break_time=int(message.text))

    async def break_schedule(work_time, break_time, count):
        await message.answer("Break time end! Let's work for " + str(work_time) + " min")
        work_expire_time = get_expire_time(work_time)
        sched.add_job(work_schedule, 'date', run_date=work_expire_time, args=[
            work_time, break_time, count], misfire_grace_time=300, id=str(message.from_user.id))
        pass

    async def work_schedule(work_time, break_time, count):
        await message.answer("[ 🏁 Work time end!] Let's break for " + str(break_time) + " min")
        if count == 3:
            count -= 3
            break_expire_time = get_expire_time(break_time)
            sched.add_job(break_schedule, 'date', run_date=break_expire_time,
                          args=[work_time, break_time * 5, count], misfire_grace_time=300, id=str(message.from_user.id))
        else:
            count += 1
            break_expire_time = get_expire_time(break_time)
            sched.add_job(break_schedule, 'date', run_date=break_expire_time,
                          args=[work_time, break_time, count], misfire_grace_time=300, id=str(message.from_user.id))
        pass

    work_expire_time = get_expire_time(int(data['work_time']))
    sched.add_job(work_schedule, 'date', run_date=work_expire_time,
                  args=[int(data['work_time']), int(data['break_time'], 0), 0], misfire_grace_time=300,
                  id=str(message.from_user.id))
    await message.answer(
        "Title: " + str(data['Title']) + "[Work " + str(data['work_time']) + " min, Break " + str(data['break_time']) +
        " min] Pomodoro Timer START.\n - stop command : /pm_stop")

    await state.finish()


@dp.message_handler(commands=['pm_stop'])
async def stop_pomodoro_timer(message: types.Message):
    """ Stop pomodoro timer
    Action:
        Stop pomodoro timer
    """
    sched.remove_job(str(message.from_user.id))
    await message.reply("Pomodoro Timer STOP.\n - start command : /pomodoro [work_min] [break_min]")


# ============================ Timer handler ==================================

@dp.message_handler(commands=['timer'], state='*')
@dp.edited_message_handler(commands=['timer'])
async def process_timer_command(message: types.Message):
    if not message.get_args():
        await message.reply("Use /timer <minutes> to set a timer")
    else:
        argument = message.get_args()
        if not argument.isdigit() or not argument:
            await message.reply("Failed, because the argument is not a digit")
        else:
            timer = timerTasks.Timer(int(argument), timerTasks.timeout_callback)
            await message.answer("Timer set on " + argument + " min", reply_markup=inline_kb3, reply=True)

            @dp.callback_query_handler(lambda c: c.data == 'CancelTimer')
            async def process_callback_button3(callback_query: types.CallbackQuery):
                await callback_query.message.delete_reply_markup()
                await message.answer("Timer stopped")
                timer.cancel()


async def timer_is_done(message: types.Message):
    await message.answer("Timer stopped")


# ============================ Scan handler ==================================

@dp.message_handler(commands=['Scan'])
async def process_scan_command(message: types.Message):
    msg = text(bold('send me a photo'), )
    await message.answer(msg)


@dp.message_handler(content_types=[ContentType.DOCUMENT, ContentType.PHOTO])
async def process_photo_command(message: types.Message):
    if message.photo:
        await message.photo[-1].download('static/img/' + str(message.from_user.id) + '.jpg')
        await bot.send_chat_action(message.from_user.id, action='upload_photo')
        await bot.send_photo(message.from_user.id,
                             photo=open('static/img/' + str(message.from_user.id) + '.jpg', 'rb'),
                             caption=" What to do with this?", reply_markup=inline_kb1)
    elif 'image' in message.document.mime_type:
        await bot.send_chat_action(message.from_user.id, action='upload_photo')
        file = await bot.get_file(message.document.file_id)
        file_path = file.file_path
        await bot.download_file(file_path, 'static/img/' + str(message.from_user.id) + '.jpg')
        await bot.send_photo(message.from_user.id, photo=open('static/img/' + str(message.from_user.id) + '.jpg', 'rb'),
                             caption="What to do with this?", reply_markup=inline_kb1)
    else:
        await message.reply("Please send me a photo")


@dp.callback_query_handler(lambda c: c.data == 'scan')
async def process_callback_button1(callback_query: types.CallbackQuery):
    await callback_query.message.delete_reply_markup()
    await bot.send_chat_action(callback_query.from_user.id, action='upload_document')
    if os.path.exists("static/img/" + str(callback_query.from_user.id) + ".jpg"):
        await bot.answer_callback_query(callback_query.id)
        asyncio.coroutine(await Scan.ScanDoc("static/img/" + str(callback_query.from_user.id) + ".jpg"))
        await bot.send_document(callback_query.from_user.id,
                                document=open('static/img/' + str(callback_query.from_user.id) + '.jpg', 'rb'),
                                caption="Done", reply_markup=inline_kb2)
    else:
        await bot.send_message(callback_query.from_user.id, 'Please send me photo again')


@dp.callback_query_handler(lambda c: c.data == 'qrcode')
async def process_callback_button2(callback_query: types.CallbackQuery):
    await callback_query.message.delete_reply_markup()
    await bot.send_chat_action(callback_query.from_user.id, action='typing')
    if os.path.exists("static/img/" + str(callback_query.from_user.id) + ".jpg"):
        await bot.answer_callback_query(callback_query.id)
        k = await Scan.QReader("static/img/" + str(callback_query.from_user.id) + ".jpg")
        await callback_query.message.answer('Decoded text: '+k)
    else:
        await bot.send_message(callback_query.from_user.id, 'Please send me photo again')


@dp.callback_query_handler(lambda c: c.data == 'pdf')
async def process_callback_button3(callback_query: types.CallbackQuery):
    await callback_query.message.delete_reply_markup()
    await bot.send_chat_action(callback_query.from_user.id, action='upload_document')
    if os.path.exists("static/img/" + str(callback_query.from_user.id) + ".jpg"):
        await bot.answer_callback_query(callback_query.id)
        asyncio.coroutine(await Scan.ToPdf("static/img/" + str(callback_query.from_user.id) + ".jpg"))
        await bot.send_document(callback_query.from_user.id,
                                document=open('static/img/' + str(callback_query.from_user.id) + '.pdf', 'rb'),
                                caption="here")
    else:
        await bot.send_message(callback_query.from_user.id, 'something done wrong')


# ============================================ Reminder =============================================================
async def scheduleDateReminder(user, task):
    conn = sqlite3.connect('botuploads.db')
    rows = conn.execute("SELECT TASK, ID_USER, TITLE, DATE FROM reminder3 WHERE ID_USER = ? AND TASK = ?",
                        (user, task,), ).fetchall()
    conn.close()
    for row in rows:
        await bot.send_message(chat_id=user,
                               text=f'Task {row[0]} Remind: \n Title:{row[2]} \n\n Date:{row[3]}'
                               )
    pass


@dp.message_handler(commands='remind')
async def remind_start(message: types.Message):
    # Set state
    await bot.send_chat_action(message.from_user.id, action='typing')
    await Form.ReminderTitle.set()
    await message.reply("What can I remind you?")


@dp.message_handler(state=Form.ReminderTitle)
async def process_remind_title(message: types.Message, state: FSMContext):
    """
    Process user title for reminder
    """
    Reminder.TITLE = (str(message.text))

    await message.answer("Please select a date to remind: ", reply_markup=await SimpleCalendar().start_calendar())
    await state.finish()

    # calendar usage
    @dp.callback_query_handler(simple_cal_callback.filter())
    @dp.message_handler(state="Please select a date to remind: ")
    async def process_simple_calendar(callback_query: types.CallbackQuery, callback_data: dict):
        selected, date = await SimpleCalendar().process_selection(callback_query, callback_data)
        async with state.proxy() as data:
            data['ReminderDate'] = str(date.strftime('%Y-%m-%d '))
        if selected:
            inline_timepicker.init(
                datetime.time(12),
                datetime.time(1),
                datetime.time(23),
            )

            await message.answer(f'Set Time:', reply_markup=inline_timepicker.get_keyboard())

    @dp.callback_query_handler(inline_timepicker.filter())
    async def cb_handler(query: types.CallbackQuery, callback_data: Dict[str, str]):
        await query.answer()
        handle_result = inline_timepicker.handle(query.from_user.id, callback_data)
        async with state.proxy() as data:
            reminderDate = data['ReminderDate']

        if handle_result is not None:
            conn = sqlite3.connect('botuploads.db')
            count = conn.execute("SELECT TASK FROM reminder3 WHERE ID_USER = ?",
                                 (query.from_user.id,), ).fetchall()
            conn.text_factory = str
            conn.execute("insert into reminder3 (TASK, ID_USER, TITLE, DATE) values (?, ?, ?, ?)",
                         (str(len(count) + 1), str(query.from_user.id),
                          str(Reminder.TITLE),
                          str(reminderDate) + ' ' + str(handle_result)))
            conn.commit()
            conn.close()
            sched.add_job(scheduleDateReminder, 'date', run_date=str(reminderDate) + '' + str(handle_result),
                          args=[message.from_user.id, str(len(count) + 1)], misfire_grace_time=300,
                          id=str(message.from_user.id) + '' + str(len(count) + 1))
            print(str(message.from_user.id) + '' + str(len(count) + 1))
            await bot.edit_message_text(f'Task is settled \n See: /list_rm',
                                        chat_id=query.from_user.id,
                                        message_id=query.message.message_id)
        else:
            await bot.edit_message_reply_markup(chat_id=query.from_user.id,
                                                message_id=query.message.message_id,
                                                reply_markup=inline_timepicker.get_keyboard())


@dp.message_handler(commands='list_rm', state='*')
@dp.edited_message_handler(commands='list_rm', )
async def list_remind_start(message: types.Message):
    conn = sqlite3.connect('botuploads.db')
    if message.get_args().isdigit():
        rows = conn.execute("SELECT TASK, ID_USER, TITLE, DATE FROM reminder3 WHERE ID_USER = ? AND TASK = ?",
                            (message.from_user.id, message.get_args(),), ).fetchall()
        for row in rows:
            await message.answer(

                f'Task {row[0]}: \n Title:{row[2]} \n\n Date:{row[3]} \n useful commands:'
                f'\n /update_rm <number of task>'
                f'\n /delete_rm <number of task>',
            )
    else:
        rows = conn.execute("SELECT TASK, ID_USER, TITLE, DATE FROM reminder3 WHERE ID_USER = ?",
                            (message.from_user.id,), ).fetchall()
        if len(rows) > 0:
            for row in rows:
                await message.answer(

                    f'Task {row[0]}: \n\n Title:{row[2]} \n Date:{row[3]} \n useful commands:'
                    f'\n /update_rm <number of task>'
                    f'\n /delete_rm <number of task>',
                )
        else:
            await message.answer(f'You dont have tasks')

    conn.close()


@dp.message_handler(commands='update_rm', state='*')
@dp.edited_message_handler(commands='update_rm')
async def update_remind_start(message: types.Message, state: FSMContext):
    if message.get_args().isdigit():
        conn = sqlite3.connect('botuploads.db')
        task = conn.execute(
            "SELECT TASK FROM reminder3 WHERE ID_USER = ? AND TASK = ?",
            (str(message.from_user.id), str(message.get_args())),
        ).fetchall()
        if len(task) > 0:
            try:
                async with state.proxy() as data:
                    data['ReminderTask'] = message.get_args()
                await message.answer(f'What would you like to change in Task {message.get_args()}?',
                                     reply_markup=inline_kb6)
            except:
                await message.answer(f'You dont have this task: {message.get_args()}')
        else:
            await message.answer(f'You dont have tasks')
        conn.close()
    else:
        await message.answer(f'message {message.get_args()} is no a digit')


@dp.callback_query_handler(lambda c: c.data == 'Title_rm')
async def process_callback_title_rm_button(callback_query: types.CallbackQuery):
    await callback_query.message.delete_reply_markup()
    await callback_query.message.answer(f'Title: ')
    await Form.ReminderChangeTitle.set()


@dp.message_handler(state=Form.ReminderChangeTitle)
async def process_title_change(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        task_rm = data['ReminderTask']

    conn = sqlite3.connect('botuploads.db')
    conn.execute(
        "UPDATE reminder3 SET TITLE = ? WHERE TASK = ? AND ID_USER = ?",
        (message.text, task_rm, message.from_user.id)
    )
    conn.commit()
    conn.close()
    await state.finish()
    await message.answer(f'Title changed in Task {task_rm} \nSee:/list_rm')


# @dp.callback_query_handler(lambda c: c.data == 'Date_rm')
# async def process_callback_title_rm_button(callback_query: types.CallbackQuery):
#     await callback_query.message.delete_reply_markup()
#     await callback_query.message.answer(f'Date: ', reply_markup=await SimpleCalendar().start_calendar())
#
#     # calendar usage
#     @dp.callback_query_handler(simple_cal_callback.filter())
#     @dp.message_handler(state="Date: ")
#     async def process_change_date_calendar(callback_query: types.CallbackQuery, callback_data: dict, state: FSMContext):
#         selected, date = await SimpleCalendar().process_selection(callback_query, callback_data)
#         async with state.proxy() as data:
#             data['ReminderDate'] = str(date.strftime('%Y-%m-%d '))
#         if selected:
#             await inline_timepicker.init(
#                 datetime.time(12),
#                 datetime.time(1),
#                 datetime.time(23),
#             )
#             await callback_query.message.answer(f'Time: ', reply_markup=inline_timepicker.get_keyboard())
#
#     @dp.callback_query_handler(inline_timepicker.filter())
#     @dp.message_handler(state='Time: ')
#     async def time_change_handler(query: types.Message, callback_data: Dict[str, str], state: FSMContext):
#         await query.answer(f"now is started")
#         await query.answer()
#         handle_result = inline_timepicker.handle(query.from_user.id, callback_data)
#
#         async with state.proxy() as data:
#             reminderDate = data['ReminderDate']
#             task_rm = data['ReminderTask']
#
#         if handle_result is not None:
#             conn = sqlite3.connect('botuploads.db')
#             conn.execute(
#                 "UPDATE reminder3 SET DATE = ? WHERE TASK = ? AND ID_USER = ?",
#                 (str(reminderDate) + '' + str(handle_result), task_rm, query.from_user.id)
#             )
#             conn.commit()
#             conn.close()
#             sched.remove_job(job_id=str(query.from_user.id) + '' + str(task_rm))
#             sched.add_job(scheduleDateReminder, 'date', run_date=str(reminderDate) + '' + str(handle_result),
#                           args=[query.from_user.id, task_rm], misfire_grace_time=300,
#                           id=str(query.from_user.id) + '' + task_rm)
#             await bot.edit_message_text(f'Task is settled \n See: /list_rm',
#                                         chat_id=query.from_user.id,
#                                         message_id=query.message_id)
#         else:
#             await bot.edit_message_reply_markup(chat_id=query.from_user.id,
#                                                 message_id=query.message_id,
#                                                 reply_markup=await inline_timepicker.get_keyboard())


@dp.message_handler(commands='delete_rm', state='*')
@dp.edited_message_handler(commands='delete_rm')
async def delete_remind_start(message: types.Message):
    if message.get_args().isdigit():
        try:
            conn = sqlite3.connect('botuploads.db')
            conn.execute("DELETE FROM reminder3 WHERE  ID_USER = ? AND TASK = ?",
                         (message.from_user.id, message.get_args()))
            conn.commit()
            conn.close()
            sched.remove_job(job_id=str(message.from_user.id) + '' + str(message.get_args()))
            await message.answer(f"Task '{message.get_args()}' deleted")
        except:
            await message.answer(f"You don't have this Task '{message.get_args()}'")
    else:
        await message.answer(f'message {message.get_args()} is not a digit')


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
