import time
import datetime
import logging
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from database.models import PromoCode, User
from database.crud import UserCRUD
from config import Config

router = Router()
logger = logging.getLogger(__name__)

class AdminBroadcast(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirm = State()

class UserManagement(StatesGroup):
    waiting_for_id = State()    

class PromoCreation(StatesGroup):
    waiting_for_code = State()
    waiting_for_level = State()
    waiting_for_uses = State()    

# Простая проверка: является ли юзер админом
def is_admin(user_id: int) -> bool:
    if not Config.ADMIN_IDS: return False
    if isinstance(Config.ADMIN_IDS, int):
        return user_id == Config.ADMIN_IDS
    return user_id in Config.ADMIN_IDS

# ==========================================
# 1. ГЛАВНОЕ МЕНЮ АДМИНА
# ==========================================
@router.message(Command("admin"))
async def admin_panel_start(message: Message):
    if not is_admin(message.from_user.id): return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Живая статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Глобальная рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔑 Управление юзером", callback_data="admin_users")],
        [InlineKeyboardButton(text="🎟 Управление промокодами", callback_data="admin_list_promos")] 
        # Кнопку "Массовая рассылка" отсюда удалили
    ])
    
    await message.answer(
        "👨‍💻 <b>Центр управления TrAIner Bot</b>\n\n"
        "Выбери нужный раздел:", 
        reply_markup=kb, 
        parse_mode="HTML"
    )

# ==========================================
# 2. КНОПКА: СТАТИСТИКА
# ==========================================
@router.callback_query(F.data == "admin_stats")
async def show_admin_stats(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id): return

    stats = await UserCRUD.get_stats(session)
    
    conversion = 0
    if stats['total'] > 0:
        conversion = int((stats['active_profile'] / stats['total']) * 100)
    
    text = (
        f"📊 <b>Статистика проекта</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего запусков: <b>{stats['total']}</b>\n"
        f"✅ Заполнили профиль: <b>{stats['active_profile']}</b> ({conversion}%)\n"
        f"🔥 Активны (24ч): <b>{stats['active_24h']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Срез по тарифам:</b>\n"
        f"🌱 Free: <b>{stats['free_users']}</b>\n"
        f"🥉 Lite: <b>{stats['lite_users']}</b>\n"
        f"🥈 Standard: <b>{stats['standard_users']}</b>\n"
        f"💎 Ultra: <b>{stats['ultra_users']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="admin_back_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

# ==========================================
# 3. ВОЗВРАТ В ГЛАВНОЕ МЕНЮ
# ==========================================
@router.callback_query(F.data == "admin_back_main")
async def back_to_admin_main(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    
    await state.clear() # Очищаем любые состояния (рассылку, поиск и т.д.)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Живая статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Глобальная рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔑 Управление юзером", callback_data="admin_users")],
        [InlineKeyboardButton(text="🎟 Управление промокодами", callback_data="admin_list_promos")] # Добавили сюда!
    ])
    
    try:
        await callback.message.edit_text(
            "👨‍💻 <b>Центр управления TrAIner Bot</b>\n\n"
            "Выбери нужный раздел:", 
            reply_markup=kb, 
            parse_mode="HTML"
        )
    except Exception:
        # Если сообщение нельзя отредактировать (например, оно старое), отправляем новое
        await callback.message.answer(
            "👨‍💻 <b>Центр управления TrAIner Bot</b>\n\n"
            "Выбери нужный раздел:", 
            reply_markup=kb, 
            parse_mode="HTML"
        )

# ==========================================
# 4. ГЛОБАЛЬНАЯ РАССЫЛКА
# ==========================================
@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_back_main")]
    ])
    
    await callback.message.edit_text(
        "📢 <b>Режим глобальной рассылки</b>\n\n"
        "Отправь мне сообщение, которое хочешь разослать.\n"
        "<i>Можно прикрепить фото, видео или кружочек — бот скопирует всё один в один.</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(AdminBroadcast.waiting_for_message)

@router.message(AdminBroadcast.waiting_for_message)
async def preview_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    
    # Сохраняем данные сообщения
    await state.update_data(msg_id=message.message_id, from_chat_id=message.chat.id)
    
    # Показываем предпросмотр
    await message.bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ НАЧАТЬ РАССЫЛКУ", callback_data="admin_confirm_broadcast")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_back_main")]
    ])
    
    await message.answer("👆 <b>Предпросмотр.</b>\n\nИменно так пользователи увидят твое сообщение. Начинаем?", reply_markup=kb, parse_mode="HTML")
    await state.set_state(AdminBroadcast.waiting_for_confirm)

@router.callback_query(F.data == "admin_confirm_broadcast", AdminBroadcast.waiting_for_confirm)
async def execute_broadcast(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not is_admin(callback.from_user.id): return
    
    data = await state.get_data()
    msg_id = data.get("msg_id")
    from_chat_id = data.get("from_chat_id")
    
    await callback.message.edit_text("⏳ <i>Рассылка запущена... Это займет какое-то время.</i>", parse_mode="HTML")
    
    users = await UserCRUD.get_all_users(session)
    success = 0
    failed = 0
    
    for user in users:
        try:
            await callback.bot.copy_message(
                chat_id=user.telegram_id,
                from_chat_id=from_chat_id,
                message_id=msg_id
            )
            success += 1
            await asyncio.sleep(0.05) # Защита от спам-фильтра Telegram (не больше 20 сообщ/сек)
        except Exception:
            failed += 1 # Юзер заблокировал бота или удалил аккаунт
            
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="admin_back_main")]
    ])
    
    await callback.message.answer(
        f"📢 <b>Рассылка успешно завершена!</b>\n\n"
        f"✅ Доставлено: <b>{success}</b>\n"
        f"❌ Ошибок (ботов заблокировали): <b>{failed}</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

# ==========================================
# 5. УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
# ==========================================
@router.callback_query(F.data == "admin_users")
async def start_user_manage(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    
    await callback.message.edit_text(
        "🔎 <b>Поиск пользователя</b>\n\n"
        "Пришли мне Telegram ID пользователя.\n"
        "<i>Его можно узнать в профиле пользователя или из логов.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(UserManagement.waiting_for_id)

@router.message(UserManagement.waiting_for_id)
async def show_user_card(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id): return
    
    try:
        target_id = int(message.text.strip())
        user = await UserCRUD.get_user(session, target_id)
        
        if not user:
            await message.answer("❌ Пользователь не найден в базе.")
            return

        text = (
            f"👤 <b>Карточка пользователя</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: <code>{user.telegram_id}</code>\n"
            f"💎 Тариф: <b>{user.subscription_level.upper() if user.subscription_level else 'FREE'}</b>\n"
            f"🍏 Генераций: <b>{user.workout_limit}</b>\n"
            f"💬 Вопросов: <b>{user.chat_limit}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚖️ Вес: {user.weight} | 📏 Рост: {user.height}\n"
            f"🎯 Цель: {user.goal}"
        )

        # Клавиатура с разделенными кнопками добавления лимитов
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Сделать ULTRA", callback_data=f"set_level_ultra_{target_id}")],
            [InlineKeyboardButton(text="🥈 Сделать STANDARD", callback_data=f"set_level_standard_{target_id}")],
            [InlineKeyboardButton(text="🥉 Сделать LITE", callback_data=f"set_level_lite_{target_id}")],
            [
                InlineKeyboardButton(text="➕ +5 генераций", callback_data=f"add_workouts_{target_id}"),
                InlineKeyboardButton(text="➕ +10 вопросов", callback_data=f"add_chats_{target_id}")
            ],
            [InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data=f"admin_delete_user_{target_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users")]
        ])
        
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
        await state.clear()
        
    except ValueError:
        await message.answer("⚠️ Введи корректный числовой ID.")

# --- ВЫДАЧА ТАРИФОВ И ОБНОВЛЕНИЕ ЛИМИТОВ ---
@router.callback_query(F.data.startswith("set_level_"))
async def change_user_level(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id): return
    
    parts = callback.data.split("_")
    new_level = parts[2]
    target_id = int(parts[3])
    
    user = await UserCRUD.get_user(session, target_id)
    if user:
        user.subscription_level = new_level
        
        # Строгая установка лимитов по новым правилам
        if new_level == 'ultra':
            user.workout_limit = 30
            user.chat_limit = 100
        elif new_level == 'standard':
            user.workout_limit = 20
            user.chat_limit = 50
        elif new_level == 'lite':
            user.workout_limit = 10
            user.chat_limit = 20
        elif new_level == 'free':
            user.workout_limit = 3
            user.chat_limit = 5
            
        await session.commit()
        await callback.answer(f"✅ Уровнь {new_level.upper()} установлен!", show_alert=True)
        
        # Обновляем карточку без переотправки сообщения
        text = (
            f"👤 <b>Карточка пользователя</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: <code>{user.telegram_id}</code>\n"
            f"💎 Тариф: <b>{user.subscription_level.upper()}</b>\n"
            f"🍏 Генераций: <b>{user.workout_limit}</b>\n"
            f"💬 Вопросов: <b>{user.chat_limit}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚖️ Вес: {user.weight} | 📏 Рост: {user.height}\n"
            f"🎯 Цель: {user.goal}"
        )
        try:
            await callback.message.edit_text(text, reply_markup=callback.message.reply_markup, parse_mode="HTML")
        except:
            pass

# --- РУЧНОЕ ДОБАВЛЕНИЕ ЛИМИТОВ ---
@router.callback_query(F.data.startswith("add_workouts_"))
async def add_admin_workouts(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id): return
    
    target_id = int(callback.data.split("_")[2])
    user = await UserCRUD.get_user(session, target_id)
    if user:
        user.workout_limit = (user.workout_limit or 0) + 5
        await session.commit()
        await callback.answer("✅ Добавлено +5 генераций!", show_alert=True)
        
        # Динамическое обновление текста карточки
        new_text = callback.message.html_text.replace(
            f"🍏 Генераций: <b>{user.workout_limit - 5}</b>",
            f"🍏 Генераций: <b>{user.workout_limit}</b>"
        )
        try:
            await callback.message.edit_text(new_text, reply_markup=callback.message.reply_markup, parse_mode="HTML")
        except: pass

@router.callback_query(F.data.startswith("add_chats_"))
async def add_admin_chats(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id): return
    
    target_id = int(callback.data.split("_")[2])
    user = await UserCRUD.get_user(session, target_id)
    if user:
        user.chat_limit = (user.chat_limit or 0) + 10
        await session.commit()
        await callback.answer("✅ Добавлено +10 вопросов!", show_alert=True)
        
        # Динамическое обновление текста карточки
        new_text = callback.message.html_text.replace(
            f"💬 Вопросов: <b>{user.chat_limit - 10}</b>",
            f"💬 Вопросов: <b>{user.chat_limit}</b>"
        )
        try:
            await callback.message.edit_text(new_text, reply_markup=callback.message.reply_markup, parse_mode="HTML")
        except: pass

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

# --- ИНТЕРФЕЙС ПРОМОКОДОВ ---
@router.callback_query(F.data == "admin_list_promos")
async def admin_promo_menu(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id): return
    promos = await UserCRUD.get_all_promos(session)
    
    text = "🎟 <b>Управление промокодами</b>\n\n"
    if not promos:
        text += "<i>Список пуст</i>"
    else:
        for p in promos:
            text += f"▪️ <code>{p.code}</code> ({p.target_level}) | 👥 {p.uses_left}\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать новый", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="🗑 Удалить код", callback_data="admin_delete_promo_start")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

# --- СОЗДАНИЕ ЧЕРЕЗ КНОПКИ ---
@router.callback_query(F.data == "admin_create_promo")
async def create_promo_step1(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✨ Введи текст нового промокода (например, <code>ULTRA2026</code>):", parse_mode="HTML")
    await state.set_state(PromoCreation.waiting_for_code)

@router.message(PromoCreation.waiting_for_code)
async def create_promo_step2(message: Message, state: FSMContext):
    await state.update_data(code=message.text.upper())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Lite", callback_data="set_promo_lite"),
         InlineKeyboardButton(text="Standard", callback_data="set_promo_standard")],
        [InlineKeyboardButton(text="Ultra", callback_data="set_promo_ultra")]
    ])
    await message.answer(f"Код: <b>{message.text.upper()}</b>\nВыбери тариф:", reply_markup=kb, parse_mode="HTML")
    await state.set_state(PromoCreation.waiting_for_level)

@router.callback_query(PromoCreation.waiting_for_level)
async def create_promo_step3(callback: CallbackQuery, state: FSMContext):
    level = callback.data.replace("set_promo_", "")
    await state.update_data(level=level)
    await callback.message.edit_text(f"Тариф: <b>{level.upper()}</b>\nВведи количество активаций (число):", parse_mode="HTML")
    await state.set_state(PromoCreation.waiting_for_uses)

@router.message(PromoCreation.waiting_for_uses)
async def create_promo_final(message: Message, state: FSMContext, session: AsyncSession):
    if not message.text.isdigit():
        return await message.answer("⚠️ Введи число!")
    
    data = await state.get_data()
    expiry = datetime.datetime.now() + datetime.timedelta(days=30)
    new_p = PromoCode(code=data['code'], target_level=data['level'], uses_left=int(message.text), expiry_date=expiry)
    session.add(new_p)
    await session.commit()
    await message.answer(f"✅ Готово! Код <code>{data['code']}</code> создан.")
    await state.clear()
    await admin_promo_menu(message, session)
    await state.clear()
    # Возвращаем админа в меню управления промокодами
    await admin_promo_menu(message, session)

# --- УДАЛЕНИЕ ЧЕРЕЗ КНОПКИ ---
@router.callback_query(F.data == "admin_delete_promo_start")
async def delete_promo_list(callback: CallbackQuery, session: AsyncSession):
    promos = await UserCRUD.get_all_promos(session)
    buttons = [[InlineKeyboardButton(text=f"❌ {p.code}", callback_data=f"del_p_{p.code}")] for p in promos]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_list_promos")])
    await callback.message.edit_text("Нажми на код для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("del_p_"))
async def delete_promo_confirm(callback: CallbackQuery, session: AsyncSession):
    code = callback.data.replace("del_p_", "")
    await UserCRUD.delete_promo(session, code)
    await callback.answer(f"Удалено: {code}")
    await admin_promo_menu(callback, session)

@router.message(Command("del"))
async def admin_delete_user(message: Message, session: AsyncSession):
    # Проверка на админа (у тебя в боте она уже должна быть реализована)
    # if message.from_user.id not in ADMIN_IDS: return 

    # Достаем ID из текста команды: /del 123456789
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Введи ID: <code>/del 123456789</code>", parse_mode="HTML")
        return

    try:
        target_id = int(args[1])
        success = await UserCRUD.delete_user(session, target_id)
        
        if success:
            await message.answer(f"✅ Пользователь <code>{target_id}</code> полностью удален из базы.", parse_mode="HTML")
        else:
            await message.answer("❌ Пользователь с таким ID не найден.")
            
    except ValueError:
        await message.answer("⚠️ ID должен быть числом.")    

# --- 1. ПРЕДУПРЕЖДЕНИЕ И ЗАПРОС ПОДТВЕРЖДЕНИЯ ---
@router.callback_query(F.data.startswith("admin_delete_user_"))
async def process_admin_delete_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): 
        await callback.answer("У вас нет прав!", show_alert=True)
        return
    
    try:
        data_parts = callback.data.split("_")
        target_id = int(data_parts[-1]) 
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    
    # Создаем клавиатуру с подтверждением
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{target_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_delete_{target_id}")
        ]
    ])
    
    # Меняем сообщение на вопрос
    await callback.message.edit_text(
        f"⚠️ <b>ВНИМАНИЕ!</b>\n\nВы точно хотите <b>безвозвратно</b> удалить пользователя <code>{target_id}</code> и всю его историю?",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

# --- 2. ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ (Реальное удаление) ---
@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_admin_delete_user(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id): 
        await callback.answer("У вас нет прав!", show_alert=True)
        return
    
    try:
        target_id = int(callback.data.split("_")[-1]) 
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    
    # Реальное удаление из базы
    success = await UserCRUD.delete_user(session, target_id)
    
    if success:
        await callback.answer("💥 Пользователь удален", show_alert=True)
        await callback.message.edit_text(
            f"✅ Пользователь <code>{target_id}</code> полностью удален из базы.", 
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Ошибка удаления", show_alert=True)
        await callback.message.edit_text("❌ Пользователь с таким ID не найден или уже удален.")

# --- 3. ОТМЕНА УДАЛЕНИЯ ---
@router.callback_query(F.data.startswith("cancel_delete_"))
async def cancel_admin_delete_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): 
        await callback.answer("У вас нет прав!", show_alert=True)
        return
        
    try:
        target_id = int(callback.data.split("_")[-1]) 
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    await callback.answer("Действие отменено")
    await callback.message.edit_text(
        f"🛡 Удаление пользователя <code>{target_id}</code> отменено.", 
        parse_mode="HTML"
    )        

# ==========================================
# МАССОВАЯ РАССЫЛКА
# ==========================================
@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    
    await callback.message.answer(
        "📢 <b>Режим рассылки</b>\n\n"
        "Отправь мне сообщение, которое нужно разослать всем пользователям бота.\n"
        "<i>(Можно отправить текст, фото, видео или голосовое сообщение)</i>\n\n"
        "Для отмены нажми /cancel",
        parse_mode="HTML"
    )
    await state.set_state(AdminBroadcast.waiting_for_message)
    await callback.answer()

@router.message(AdminBroadcast.waiting_for_message)
async def preview_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    
    # Сохраняем данные сообщения для копирования
    await state.update_data(broadcast_message_id=message.message_id, from_chat_id=message.chat.id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Начать рассылку", callback_data="confirm_broadcast")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")]
    ])
    
    await message.answer("👀 <b>Предпросмотр:</b> Вот так пользователи увидят сообщение 👇", parse_mode="HTML")
    await message.copy_to(message.chat.id, reply_markup=kb)
    await state.set_state(AdminBroadcast.waiting_for_confirm)

@router.callback_query(F.data == "confirm_broadcast", AdminBroadcast.waiting_for_confirm)
async def execute_broadcast(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    if not is_admin(callback.from_user.id): return
    
    data = await state.get_data()
    msg_id = data.get("broadcast_message_id")
    chat_id = data.get("from_chat_id")
    
    await callback.message.edit_reply_markup(reply_markup=None)
    status_msg = await callback.message.answer("⏳ <i>Рассылка запущена... Это может занять время.</i>", parse_mode="HTML")
    
    # Получаем ID всех пользователей из базы
    stmt = select(User.telegram_id)
    result = await session.execute(stmt)
    user_ids = result.scalars().all()
    
    success = 0
    failed = 0
    
    for uid in user_ids:
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=chat_id, message_id=msg_id)
            success += 1
            await asyncio.sleep(0.05) # Защита от бана (лимит Telegram: ~30 сообщений в секунду)
        except Exception:
            failed += 1 # Юзер заблокировал бота или удалил аккаунт
            
    await status_msg.edit_text(
        f"📢 <b>Рассылка завершена!</b>\n\n"
        f"✅ Доставлено: <b>{success}</b>\n"
        f"❌ Ошибок (блокировки): <b>{failed}</b>",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "cancel_broadcast", AdminBroadcast.waiting_for_confirm)
async def cancel_broadcast_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Рассылка отменена.")
    await callback.answer()