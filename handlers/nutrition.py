import os
import asyncio
import datetime
import time
import json
import re
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from sqlalchemy import select, func

from database.models import NutritionLog
from handlers.admin import is_admin
from database.crud import UserCRUD
from services.ai_manager import AIManager 
from keyboards.main_menu import get_main_menu
from states.workout_states import WorkoutRequest, WorkoutPagination 
from services.recipe_service import search_recipe_video
from keyboards.pagination import get_pagination_kb

router = Router()

class RecipeState(StatesGroup):
    waiting_for_dish = State()
    waiting_for_nutrition_data = State()

# 🔥 НОВАЯ ФУНКЦИЯ: Аккуратно склеивает листалку и кнопки дневника
def get_nutrition_kb_with_diary(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    # 1. Получаем базовую клавиатуру (стрелочки и прочее)
    base_kb = get_pagination_kb(current_page, total_pages, page_type="nutrition")
    
    # 2. Наши 2 новые кнопки
    extra_buttons = [
        [InlineKeyboardButton(text="📝 Записать прием пищи", callback_data="log_nutrition_press")],
        [InlineKeyboardButton(text="📊 Сводка КБЖУ за день", callback_data="show_today_nutrition")]
    ]
    
    # 3. Приклеиваем их на самый верх
    return InlineKeyboardMarkup(inline_keyboard=extra_buttons + base_kb.inline_keyboard)

def clean_text(text: str) -> str:
    """Чистильщик текста для питания"""
    if not text: return ""
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    text = re.sub(r'(^|\n)(🍳|🍲|🥗|🛒|🥪)(.*?)(?=\n|$)', r'\1\2<b>\3</b>', text)
    text = text.replace("###", "").replace("Menu:", "")
    return text.strip()

async def show_pages(message: Message, state: FSMContext, pages: list, from_db: bool = False):
    if isinstance(pages, str):
        pages = [pages]
        
    await state.update_data(nutrition_pages=pages, current_nutrition_page=0)
    await state.set_state(WorkoutPagination.active)
    
    prefix = "💾 <b>Твое меню:</b>\n\n" if from_db else "✅ <b>Тренер составил меню:</b>\n\n"
    
    try:
        await message.answer(
            text=prefix + pages[0],
            reply_markup=get_nutrition_kb_with_diary(0, len(pages)), # <-- ИСПОЛЬЗУЕМ ХЕЛПЕР
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await message.answer(f"{prefix}{str(pages[0])[:3000]}...\n(обрезано)", parse_mode=ParseMode.HTML)

# --- ПРОСМОТР ---
@router.message(F.text == "🍽 Мое меню")
async def show_my_nutrition(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Сначала заполни профиль! (/start)")
        return

    if user.current_nutrition_program:
        try:
            pages = json.loads(user.current_nutrition_program)
            await show_pages(message, state, pages, from_db=True)
        except: 
            pages = [user.current_nutrition_program]
            await show_pages(message, state, pages, from_db=True)
    else:
        # Показываем кнопки дневника даже если меню еще не сгенерировано!
        empty_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Записать прием пищи", callback_data="log_nutrition_press")],
            [InlineKeyboardButton(text="📊 Сводка КБЖУ за день", callback_data="show_today_nutrition")]
        ])
        await message.answer("🤷‍♂️ Нет сохраненного меню. Нажми <b>🍏 Питание</b> или начни вести дневник прямо сейчас!", reply_markup=empty_kb, parse_mode=ParseMode.HTML)

# --- ГЕНЕРАЦИЯ ---
@router.message(F.text == "🍏 Питание")
@router.message(Command("ai_nutrition"))
async def request_ai_nutrition(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user: 
        await message.answer("Сначала заполни профиль!")
        return

    if user.current_nutrition_program:
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Новое меню", callback_data="confirm_new_nutrition")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_nutrition")]
        ])
        await message.answer("Тренер уже составлял меню. Сделать новое?", reply_markup=confirm_kb)
    else:
        await ask_nutrition_wishes(message, state)

@router.callback_query(F.data == "confirm_new_nutrition")
async def confirm_generation(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await ask_nutrition_wishes(callback.message, state)

@router.callback_query(F.data == "log_nutrition_press")
async def start_log_nutrition(callback: CallbackQuery, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Завершить запись")]],
        resize_keyboard=True
    )
    
    await callback.message.answer(
        "🍎 <b>Дневник питания</b>\n\n"
        "Продиктуй или напиши, что ты съел. Я сам рассчитаю примерные калории.\n"
        "<i>Пример: 'Омлет из 3 яиц, кофе с сахаром и яблоко'</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(RecipeState.waiting_for_nutrition_data)
    await callback.answer()

async def ask_nutrition_wishes(message: Message, state: FSMContext):
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="⏩ Пропустить (ем всё)"))
    
    await message.answer(
        "🥗 <b>У тебя есть предпочтения по еде?</b>\n\n"
        "Напиши продукты, которые нужно <b>исключить</b> (например: <i>брокколи, лук, лактоза</i>) "
        "или просто нажми кнопку ниже 👇",
        reply_markup=kb.as_markup(resize_keyboard=True),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(WorkoutRequest.waiting_for_nutrition_wishes)

async def generate_nutrition_process(message: Message, session: AsyncSession, user, state: FSMContext, wishes: str, status_msg: Message = None):
    user_data = await state.get_data()
    last_gen_time = user_data.get("last_nutrition_gen_time", 0)
    current_time = time.time()

    if current_time - last_gen_time < 300 and not is_admin(message.from_user.id):
        wait_time = int((300 - (current_time - last_gen_time)) / 60)
        await message.answer(f"⏳ <b>Подождите {wait_time if wait_time > 0 else 1} мин.</b>\nНейросети нужно время.")
        return

    if user.workout_limit <= 0:
        if status_msg: await status_msg.delete()
        await message.answer(
            "🚀 <b>Упс! Попытки закончились</b>\n\n"
            "Вы использовали все бесплатные генерации.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Получить Premium", callback_data="buy_premium")]
            ]),
            parse_mode="HTML"
        )
        return
    
    await state.update_data(last_nutrition_gen_time=current_time)

    try:
        user_data = {
            "goal": user.goal, "gender": user.gender, "weight": user.weight, 
            "age": user.age, "activity_level": user.activity_level, "height": user.height,
            "name": user.name, "wishes": wishes 
        }
        
        ai_service = AIManager()
        raw_pages = await ai_service.generate_nutrition_pages(user_data)
        
        if not raw_pages or "❌" in raw_pages[0]:
            if status_msg: await status_msg.delete()
            await message.answer("❌ Сервер перегружен, попробуй позже.")
            return

        import json
        user.current_nutrition_program = json.dumps(raw_pages, ensure_ascii=False)
        user.workout_limit -= 1
        await session.commit()

        if status_msg:
            try: await status_msg.delete()
            except: pass

        await message.answer(
            raw_pages[0],
            parse_mode=ParseMode.HTML,
            reply_markup=get_nutrition_kb_with_diary(0, len(raw_pages)) # <-- ИСПОЛЬЗУЕМ ХЕЛПЕР
        )
            
        await state.clear()

    except Exception as e:
        if status_msg: await status_msg.delete()
        print(f"Ошибка: {e}")
        
        ai = AIManager()
        raw_pages = await ai.generate_nutrition_pages(user_data)
        cleaned_pages = [clean_text(p) for p in raw_pages if len(p) > 20]
        
        if not cleaned_pages:
            await status_msg.edit_text("⚠️ Тренер задумался и ничего не ответил. Попробуй еще раз.")
            return

        pages_json = json.dumps(cleaned_pages, ensure_ascii=False)
        await UserCRUD.update_user(session, user.telegram_id, current_nutrition_program=pages_json)
        
        await show_pages(message, state, cleaned_pages, from_db=False)

# --- ЛИСТАЛКА ---
@router.callback_query(F.data.startswith("nutrition_page_"))
async def change_nutrition_page(callback: CallbackQuery, session: AsyncSession):
    try:
        page = int(callback.data.split("_")[-1])
        user = await UserCRUD.get_user(session, callback.from_user.id)
        if not user or not user.current_nutrition_program:
            await callback.answer("❌ Программа не найдена.", show_alert=True)
            return

        pages = json.loads(user.current_nutrition_program)
        
        if page < 0 or page >= len(pages):
            await callback.answer()
            return

        await callback.message.edit_text(
            pages[page],
            parse_mode=ParseMode.HTML,
            reply_markup=get_nutrition_kb_with_diary(page, len(pages)) # <-- ИСПОЛЬЗУЕМ ХЕЛПЕР
        )
        await callback.answer()

    except TelegramBadRequest:
        await callback.answer()
    except Exception as e:
        print(f"Ошибка пагинации: {e}")
        await callback.answer()

@router.message(WorkoutRequest.waiting_for_nutrition_wishes)
async def process_nutrition_wishes(message: Message, state: FSMContext, session: AsyncSession):
    user_wishes = message.text
    data = await state.get_data()
    old_wishes = data.get("wishes", "")
    
    if old_wishes and user_wishes.lower() != "без изменений":
        combined_wishes = f"{old_wishes}. Дополнительно: {user_wishes}"
    else:
        combined_wishes = user_wishes

    await state.update_data(wishes=combined_wishes)
    user = await UserCRUD.get_user(session, message.from_user.id)
    
    status_msg = await message.answer("👨‍🍳 <b>Тренер составляет меню...</b>", parse_mode="HTML")
    await generate_nutrition_process(message, session, user, state, wishes=combined_wishes, status_msg=status_msg)

# --- ПОИСК РЕЦЕПТОВ ---
@router.callback_query(F.data == "recipe_search")
async def start_recipe_search(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("👨‍🍳 <b>Введи название блюда:</b>\n(например: <i>Сырники с изюмом</i>)", parse_mode=ParseMode.HTML)
    await state.set_state(RecipeState.waiting_for_dish)

@router.message(RecipeState.waiting_for_dish)
async def process_recipe_search(message: Message, state: FSMContext):
    if message.text.startswith('/'): 
        await state.clear()
        return
    
    loading = await message.answer("🔎 Ищу...")
    try:
        link, title, desc = await search_recipe_video(message.text)
        await loading.delete()
        
        if link:
            await message.answer(f"🎬 <b>{title}</b>\n\n{desc}\n\n<a href='{link}'>Смотреть видео</a>", parse_mode=ParseMode.HTML)
            search_again_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔍 Найти еще", callback_data="recipe_search")]])
            await message.answer("✅ Поиск завершен. Найти что-то еще?", reply_markup=search_again_kb)
            await state.clear()
        else:
            retry_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="recipe_search")]])
            await message.answer("❌ Ничего не нашлось. Попробуешь другое название?", reply_markup=retry_kb)
            await state.clear()
            
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        if 'loading' in locals(): await loading.delete()
        await message.answer("❌ Ошибка при поиске. Попробуй позже.")
        await state.clear()

@router.callback_query(F.data == "ai_chat")
async def redirect_to_chat(callback: CallbackQuery, state: FSMContext):
    from handlers.ai_chat import start_chat_logic
    await callback.answer()
    await start_chat_logic(callback.message, state)        
         
# --- БЛОКИ ЗАПИСИ ПИТАНИЯ (ИИ ДНЕВНИК КБЖУ) ---
@router.message(F.text == "🔙 Завершить запись", RecipeState.waiting_for_nutrition_data)
async def exit_log_nutrition(message: Message, state: FSMContext):
    await message.answer("✅ <b>Запись питания завершена.</b>\nДанные проанализированы и учтены!", reply_markup=get_main_menu(), parse_mode="HTML")
    await state.clear()

@router.message(F.voice | F.text, RecipeState.waiting_for_nutrition_data)
async def process_nutrition_input(message: Message, session: AsyncSession, state: FSMContext, bot: Bot):
    if message.text == "🔙 Завершить запись": return

    status_msg = await message.answer("📡 <i>Раскладываю еду на белки, жиры и углеводы...</i>", parse_mode="HTML")
    manager = AIManager()
    
    try:
        if message.voice:
            file_id = message.voice.file_id
            file = await bot.get_file(file_id)
            temp_filename = f"voice_nut_{message.from_user.id}.ogg"
            
            # Сохраняем физически на диск, чтобы Groq не ловил пустые байты
            await bot.download_file(file.file_path, temp_filename)
            await asyncio.sleep(0.1)
            
            user_text = await manager.transcribe_voice(temp_filename)
            
            # Удаляем мусор за собой
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
        else:
            user_text = message.text

        # 🔥 ТВОИ НАСТРОЙКИ ВРЕМЕНИ
        current_time = datetime.datetime.now().strftime("%H:%M")

        parse_prompt = (
            f"Ты — строгий калькулятор калорий. Текущее время пользователя: {current_time}.\n"
            "Пользователь перечислил съеденные продукты. Определи тип приема пищи строго по времени:\n"
            "- 06:00-10:00 — Завтрак\n"
            "- 10:00-12:00 — Перекус\n"
            "- 12:00-15:00 — Обед\n"
            "- 15:00-17:00 — Перекус\n"
            "- 17:00-20:00 — Ужин\n"
            "- 20:00-06:00 — Перекус\n\n"
            "Если пользователь сам указал тип (например, 'съел на обед...'), приоритет отдавай его словам.\n"
            "Вычлени каждый продукт и рассчитай для него: Вес(г), Калории, Белки(г), Жиры(г), Углеводы(г).\n"
            "СТРОГОЕ ПРАВИЛО: Верни результат списком. Каждая строка строго в формате:\n"
            "Тип | Название | Вес | Калории | Белки | Жиры | Углеводы\n"
            "ПРИМЕР: Завтрак | Яйцо куриное вареное | 150 | 235 | 19.5 | 16.3 | 1.0\n"
            "Используй только цифры, разделяй символом |. Никаких лишних слов.\n"
            f"Текст пользователя: {user_text}"
        )
        
        parsed_response = await manager.get_chat_response([{"role": "user", "content": parse_prompt}], {})
        
        lines = parsed_response.strip().split('\n')
        report = "📝 <b>Добавлено в дневник КБЖУ:</b>\n\n"
        
        added_logs_ids = [] # <-- Собираем ID добавленных записей
        
        for line in lines:
            parts = line.split('|')
            if len(parts) >= 7:
                try:
                    meal = parts[0].strip().capitalize()
                    name = parts[1].strip().capitalize()
                    weight = float(parts[2].strip().replace(',', '.'))
                    kcal = float(parts[3].strip().replace(',', '.'))
                    p = float(parts[4].strip().replace(',', '.'))
                    f = float(parts[5].strip().replace(',', '.'))
                    c = float(parts[6].strip().replace(',', '.'))
                    
                    new_log = NutritionLog(
                        user_id=message.from_user.id, meal_type=meal,
                        product_name=name, weight=weight,
                        calories=kcal, protein=p, fat=f, carbs=c
                    )
                    session.add(new_log)
                    await session.flush() # Получаем ID из базы до коммита
                    added_logs_ids.append(new_log.id)
                    
                    report += f"🕒 <b>{meal}</b> | 🍽 <b>{name}</b> ({weight}г)\n├ 🔥 {kcal} ккал\n└ 🥩 Б:{p} | 🧈 Ж:{f} | 🍞 У:{c}\n\n"
                except ValueError: continue
        
        await session.commit()
        
        # 🔥 СОХРАНЯЕМ ID В ПАМЯТЬ СОСТОЯНИЯ ДЛЯ КНОПКИ "ОТМЕНА"
        if added_logs_ids:
            await state.update_data(last_added_nut_ids=added_logs_ids)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Ошибка, отменить добавление", callback_data="undo_last_nutrition")]
            ])
            await status_msg.edit_text(f"{report}<i>🎤 Можно диктовать дальше...</i>", reply_markup=kb, parse_mode="HTML")
        else:
            await status_msg.edit_text(f"{report}<i>🎤 Можно диктовать дальше...</i>", parse_mode="HTML")

    except Exception as e:
        print(f"Ошибка КБЖУ: {e}")
        await status_msg.edit_text("❌ Ошибка при анализе. Попробуй написать текстом.")

# --- УДАЛЕНИЕ ЗАПИСЕЙ ПИТАНИЯ ---

# 1. Мгновенная отмена последнего добавления
@router.callback_query(F.data == "undo_last_nutrition")
async def undo_last_nutrition(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    ids_to_delete = data.get("last_added_nut_ids", [])

    if not ids_to_delete:
        return await callback.answer("⏳ Время вышло или записи уже отменены.", show_alert=True)

    # Удаляем записи из базы
    stmt = select(NutritionLog).where(NutritionLog.id.in_(ids_to_delete), NutritionLog.user_id == callback.from_user.id)
    result = await session.execute(stmt)
    logs = result.scalars().all()

    for log in logs:
        await session.delete(log)
    
    await session.commit()
    await state.update_data(last_added_nut_ids=[]) # Очищаем память

    await callback.message.edit_text("🗑 <b>Записи отменены!</b>\nНичего не попало в сводку. Можешь продиктовать заново.", parse_mode="HTML")

# 2. Точечное удаление через команду в Сводке
@router.message(F.text.regexp(r'^/del_\d+$'))
async def delete_single_log(message: Message, session: AsyncSession):
    log_id = int(message.text.split('_')[1])
    log = await session.get(NutritionLog, log_id)
    
    if log and log.user_id == message.from_user.id:
        name = log.product_name
        await session.delete(log)
        await session.commit()
        await message.answer(f"🗑 Запись <b>{name}</b> успешно удалена из дневника!", parse_mode="HTML")
    else:
        await message.answer("❌ Запись не найдена или уже удалена.")

@router.callback_query(F.data == "show_today_nutrition")
async def show_today_nutrition(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    today = datetime.date.today()
    
    stmt = select(NutritionLog).where(NutritionLog.user_id == user_id, func.date(NutritionLog.date) == today)
    result = await session.execute(stmt)
    logs = result.scalars().all()
    
    if not logs:
        return await callback.answer("Твой дневник питания на сегодня пуст!", show_alert=True)

    # 🔥 ГРУППИРУЕМ ПО ТИПУ ПРИЕМА ПИЩИ
    meals = {"Завтрак": [], "Обед": [], "Ужин": [], "Перекус": []}
    total_kcal = total_p = total_f = total_c = 0.0
    
    for log in logs:
        meal_key = log.meal_type if log.meal_type in meals else "Перекус"
        meals[meal_key].append(log)
        total_kcal += log.calories
        total_p += log.protein
        total_f += log.fat
        total_c += log.carbs

    text = f"📊 <b>Твой рацион за сегодня ({today.strftime('%d.%m')}):</b>\n\n"
    
    for meal_name, meal_logs in meals.items():
        if meal_logs:
            meal_kcal = sum(l.calories for l in meal_logs)
            text += f"🕒 <b>{meal_name}</b> ({int(meal_kcal)} ккал):\n"
            for log in meal_logs:
                # 🔥 ТЕПЕРЬ РЯДОМ С КАЖДЫМ БЛЮДОМ ЕСТЬ КОМАНДА /del_ID
                text += f"  • {log.product_name} ({log.weight}г) — {log.calories} ккал  ❌ /del_{log.id}\n"
            text += "\n"
        
    text += "═════════════════\n"
    text += f"🔥 <b>ВСЕГО КАЛОРИЙ: {round(total_kcal)} ккал</b>\n\n"
    text += f"🥩 <b>Белки:</b> {round(total_p)} г\n"
    text += f"🧈 <b>Жиры:</b> {round(total_f)} г\n"
    text += f"🍞 <b>Углеводы:</b> {round(total_c)} г\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Добавить прием пищи", callback_data="log_nutrition_press")],
        [InlineKeyboardButton(text="🔙 Закрыть", callback_data="cancel_nutrition")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")