import logging
import os
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

load_dotenv()

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
ADMIN_ID = int(os.getenv("ADMIN_ID"))

class MailState(StatesGroup):
    waiting_for_message = State()

# ========================================================================
# ========================================================================
#               ИНИЦИАЛИЗАЦИЯ БД (создание при её отсутсвии)
# ========================================================================
# ========================================================================
def init_db():
    if not os.path.exists('base.db'):
        with sqlite3.connect('base.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_tg INTEGER UNIQUE,
                    active INTEGER DEFAULT 1
                )
            ''')
            conn.commit()

init_db()

# ========================================================================
# ========================================================================
#                               РАССЫЛКА
# ========================================================================
# ========================================================================
@dp.message(MailState.waiting_for_message)
async def process_mail_message(message: types.Message, state: FSMContext):
    await state.clear()
    
    with sqlite3.connect('base.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id_tg FROM users WHERE active = 1")
        users = cursor.fetchall()
    
    total = len(users)
    success = 0
    errors = 0
    batch_size = 30
    
    status_msg = await message.answer(f"⏳ Рассылка начата (0/{total})")
    
    for i, user in enumerate(users, 1):
        try:
            await bot.copy_message(
                chat_id=user[0],
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            success += 1
        except Exception as e:
            errors += 1
            with sqlite3.connect('base.db') as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET active = 0 WHERE id_tg = ?", (user[0],))
                conn.commit()
        
        # Обновление статуса каждые 10 сообщений
        if i % 10 == 0:
            await status_msg.edit_text(
                f"⏳ Рассылка: {i}/{total} отправлено\n"
                f"✅ Успешно: {success}\n"
                f"❌ Ошибок: {errors}"
            )
        
        # Пауза после каждых 30 сообщений
        if i % batch_size == 0:
            await asyncio.sleep(1)
    
    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n"
        f"• Всего: {total}\n"
        f"• Успешно: {success}\n"
        f"• Ошибок: {errors}"
    )


# ========================================================================
# ========================================================================
#                           ОБРАБОТЧИКИ КОМАНД
# ========================================================================
# ========================================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    with sqlite3.connect('base.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (id_tg, active) 
            VALUES (?, 1)
        ''', (user_id,))
        cursor.execute('''
            UPDATE users SET active = 1 WHERE id_tg = ?
        ''', (user_id,))
        conn.commit()
    
    await message.answer("Добро пожаловать! Вы были зарегистрированы.")

@dp.message(Command("stat"))
async def cmd_stat(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Доступ запрещен!")

    with sqlite3.connect('base.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE active = 1")
        active = cursor.fetchone()[0]
    
    await message.answer(
        f"📊 Статистика:\n"
        f"• Всего пользователей: {total}\n"
        f"• Активных: {active}"
    )

@dp.message(Command("mail"))
async def cmd_mail(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Доступ запрещен!")
    
    await message.answer("Отправьте сообщение для рассылки:")
    await state.set_state(MailState.waiting_for_message)

# Пример echo
@dp.message()
async def echo_message(message: types.Message):
    await message.answer(f"📨 Вы написали: {message.text}")

# ========================================================================
# ========================================================================
#                               ЗАПУСК
# ========================================================================
# ========================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dp.run_polling(bot)