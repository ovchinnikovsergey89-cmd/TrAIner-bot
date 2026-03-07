import datetime
import logging
import asyncio
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import PromoCode
from database.crud import UserCRUD
from config import Config

router = Router()
logger = logging.getLogger(__name__)

# Простая проверка: является ли юзер админом
def is_admin(user_id: int) -> bool:
    if not Config.ADMIN_IDS: return False
    # Поддержка и одного ID (int), и списка (list)
    if isinstance(Config.ADMIN_IDS, int):
        return user_id == Config.ADMIN_IDS
    return user_id in Config.ADMIN_IDS

# 1. СТАТИСТИКА
@router.message(Command("admin"))
async def admin_stats(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id): return

    stats = await UserCRUD.get_stats(session)
    
    # Считаем конверсию (чтобы не делить на ноль)
    conversion = 0
    if stats['total'] > 0:
        conversion = int((stats['active_profile'] / stats['total']) * 100)
    
    text = (
        f"👨‍💻 <b>Панель Администратора</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Всего людей:</b> {stats['total']}\n"
        f"🔥 <b>Активны (24ч):</b> {stats['active_24h']}\n"
        f"📝 <b>С профилем:</b> {stats['active_profile']} ({conversion}%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏋️‍♂️ <b>Тренируются:</b> {stats['has_workout']}\n"
        f"🍏 <b>Питаются:</b> {stats['has_nutrition']}\n\n"
        f"🛠 <b>Управление:</b>\n"
        f"📢 <code>/broadcast Текст</code> — Рассылка\n"
        f"📦 <code>/backup</code> — Скачать базу"
    )
    await message.answer(text, parse_mode="HTML")

# 2. РАССЫЛКА
@router.message(Command("broadcast"))
async def admin_broadcast(message: Message, command: CommandObject, session: AsyncSession):
    if not is_admin(message.from_user.id): return

    text = command.args
    if not text:
        await message.answer("⚠️ Ошибка. Пиши: <code>/broadcast Привет всем!</code>")
        return

    users = await UserCRUD.get_all_users(session)
    count = 0
    
    status_msg = await message.answer(f"🚀 Начинаю рассылку на {len(users)} чел...")
    
    for user in users:
        try:
            await message.bot.send_message(user.telegram_id, f"📢 <b>Новости от Тренера:</b>\n\n{text}", parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05) # Анти-спам задержка
        except:
            pass # Если юзер заблокировал бота
            
    await status_msg.edit_text(f"✅ Рассылка завершена!\nДоставлено: {count} из {len(users)}")

# 3. БЭКАП БАЗЫ
@router.message(Command("backup"))
async def admin_backup(message: Message):
    if not is_admin(message.from_user.id): return

    try:
        # Пытаемся найти файл базы данных
        import os
        filename = "db.sqlite3" # Стандартное имя
        
        if not os.path.exists(filename):
            filename = "trainer.db" # Альтернативное имя
            
        if os.path.exists(filename):
            db_file = FSInputFile(filename)
            await message.answer_document(db_file, caption=f"📦 Бэкап от {message.date.date()}")
        else:
            await message.answer("❌ Файл базы данных не найден в корне папки.")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

from aiogram.fsm.context import FSMContext
import time

@router.message(Command("admin_boost"))
async def admin_boost_cmd(message: Message, session: AsyncSession, state: FSMContext):
    if not is_admin(message.from_user.id): return

    # 1. Начисляем лимиты в базе
    user = await UserCRUD.get_user(session, message.from_user.id)
    if user:
        # Убедитесь, что эти колонки добавлены в models.py и базу данных
        user.is_premium = True
        user.workout_limit = 999
        user.chat_limit = 999
        await session.commit()
    
    # 2. Сбрасываем таймеры ожидания в FSM
    await state.update_data(
        last_workout_gen_time=0,
        last_nutrition_gen_time=0
    )
    
    await message.answer("🚀 <b>Босс, лимиты пополнены (999), таймеры сброшены!</b>", parse_mode="HTML")        

# 1. ГЕНЕРАЦИЯ (с поддержкой срока годности)
@router.message(Command("gen_promo"))
async def admin_gen_promo(message: Message, session: AsyncSession):
    args = message.text.split()
    if len(args) < 4:
        await message.answer("ℹ️ <code>/gen_promo КОД КОЛВО УРОВЕНЬ [ДНИ]</code>\nПример: <code>/gen_promo VIP 10 ultra 1</code>", parse_mode="HTML")
        return

    code_text = args[1].upper()
    uses = int(args[2])
    level = args[3].lower()
    days = int(args[4]) if len(args) > 4 else 365 # По умолчанию год

    expiry = datetime.datetime.now() + datetime.timedelta(days=days)
    
    new_promo = PromoCode(code=code_text, uses_left=uses, target_level=level, expiry_date=expiry)
    session.add(new_promo)
    
    try:
        await session.commit()
        await message.answer(f"✅ Код <b>{code_text}</b> создан!\nЛимит: {uses} чел.\nГоден до: {expiry.strftime('%d.%m.%Y %H:%M')}")
    except Exception:
        await session.rollback()
        await message.answer("❌ Такой код уже есть!")

# 2. УДАЛЕНИЕ
@router.message(Command("del_promo"))
async def admin_del_promo(message: Message, session: AsyncSession):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Введите код: <code>/del_promo КОД</code>")
        return
    
    success = await UserCRUD.delete_promo(session, args[1])
    if success:
        await message.answer(f"🗑 Промокод <b>{args[1].upper()}</b> удален.")
    else:
        await message.answer("❌ Код не найден.")

# 3. СПИСОК ВСЕХ КОДОВ
@router.message(Command("list_promos"))
async def admin_list_promos(message: Message, session: AsyncSession):
    promos = await UserCRUD.get_all_promos(session)
    if not promos:
        await message.answer("Список промокодов пуст.")
        return
    
    text = "📋 <b>Список промокодов:</b>\n\n"
    for p in promos:
        status = "✅" if p.uses_left > 0 else "❌"
        text += f"{status} <code>{p.code}</code> | {p.target_level} | Осталось: {p.uses_left}\n"
    
    await message.answer(text, parse_mode="HTML")    