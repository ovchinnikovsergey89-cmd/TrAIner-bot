from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def get_main_menu() -> ReplyKeyboardMarkup:
    """
    Главное меню бота.
    """
    builder = ReplyKeyboardBuilder()
    
    # 1-й ряд: Самые главные функции
    builder.row(
        KeyboardButton(text="🤖 AI Тренировка"),
        KeyboardButton(text="📅 Моя программа")
    )
    
    # 2-й ряд: Питание
    builder.row(
        KeyboardButton(text="🍏 Питание"),      # Генерирует новое
        KeyboardButton(text="🍽 Мое меню")   # Показывает старое
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
    
      
    return builder.as_markup(resize_keyboard=True)

def get_gender_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="👨 Мужской"), KeyboardButton(text="👩 Женский"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_activity_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🪑Сидячая (нет тренировок)"))
    builder.add(KeyboardButton(text="🚶Малая (1-3 тренировки)"))
    builder.add(KeyboardButton(text="🏃Средняя (3-5 тренировок)"))
    builder.add(KeyboardButton(text="🏋️‍♂️Высокая (6-7 тренировок)"))
    builder.add(KeyboardButton(text="🔥Экстремальная (физ. труд)"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_goal_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📉 Похудение"), KeyboardButton(text="⚖️ Поддержание"))
    builder.row(KeyboardButton(text="💪 Набор массы"), KeyboardButton(text="🔄 Рекомпозиция")) # Добавлено
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_workout_level_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🐣 Новичок"), KeyboardButton(text="🏃 Любитель"))
    builder.row(KeyboardButton(text="🏋️‍♂️ Продвинутый"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_workout_days_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for i in range(1, 8):
        day_text = "день" if i == 1 else "дня" if 2 <= i <= 4 else "дней"
        builder.add(KeyboardButton(text=f"{i} {day_text}"))
    builder.adjust(3)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)