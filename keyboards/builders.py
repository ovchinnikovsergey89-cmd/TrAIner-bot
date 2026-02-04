from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def get_main_menu():
    """
    Главное меню бота.
    """
    builder = ReplyKeyboardBuilder()
    
    # 1-й ряд: Самые главные функции (Генерация и Просмотр)
    builder.row(
        KeyboardButton(text="🤖 AI Тренировка"),
        KeyboardButton(text="📅 Моя программа") # <--- НОВАЯ КНОПКА
    )
    
    # 2-й ряд: Питание
    builder.row(
        KeyboardButton(text="🍏 Питание")
    )
    
    # 3-й ряд: Инструменты
    builder.row(
        KeyboardButton(text="💬 Чат с тренером"),
        KeyboardButton(text="🎥 Техника")
    )
    
    # 4-й ряд: Профиль и Анализ
    builder.row(
        KeyboardButton(text="👤 Профиль"),
        KeyboardButton(text="📊 Анализ")
    )
    
    # 5-й ряд: Настройки
    builder.row(
        KeyboardButton(text="🔄 Изменить данные")
    )
    
    return builder.as_markup(resize_keyboard=True)

# --- (Остальные функции клавиатур оставь без изменений) ---
def get_gender_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="👨 Мужской"), KeyboardButton(text="👩 Женский"))
    return builder.as_markup(resize_keyboard=True)

def get_activity_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Сидячий (без спорта)"))
    builder.add(KeyboardButton(text="Малая (1-3 тренировки)"))
    builder.add(KeyboardButton(text="Средняя (3-5 тренировок)"))
    builder.add(KeyboardButton(text="Высокая (6-7 тренировок)"))
    builder.add(KeyboardButton(text="Экстремальная (физ. труд)"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def get_goal_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📉 Похудение"), KeyboardButton(text="⚖️ Поддержание"))
    builder.row(KeyboardButton(text="💪 Набор массы"))
    return builder.as_markup(resize_keyboard=True)

def get_workout_level_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🐣 Новичок"), KeyboardButton(text="🏃 Любитель"))
    builder.row(KeyboardButton(text="🏋️‍♂️ Продвинутый"))
    return builder.as_markup(resize_keyboard=True)

def get_workout_days_keyboard():
    builder = ReplyKeyboardBuilder()
    for i in range(1, 8):
        day_text = "день" if i == 1 else "дня" if 2 <= i <= 4 else "дней"
        builder.add(KeyboardButton(text=f"{i} {day_text}"))
    builder.adjust(3)
    return builder.as_markup(resize_keyboard=True)