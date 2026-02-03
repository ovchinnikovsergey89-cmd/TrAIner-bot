# keyboards/main_menu.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard():
    """Основная клавиатура"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Мой профиль")],
            [KeyboardButton(text="🏋️ Тренировки")],
            [KeyboardButton(text="🍎 Питание")],
            [KeyboardButton(text="🤖 AI Тренировка"), KeyboardButton(text="🍎 AI Питание")],
            [KeyboardButton(text="📊 AI Анализ"), KeyboardButton(text="🆘 Помощь")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def get_gender_keyboard():
    """Клавиатура для выбора пола"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👨 Мужской"), KeyboardButton(text="👩 Женский")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_activity_keyboard():
    """Клавиатура для выбора активности"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛌 Сидячий образ жизни")],
            [KeyboardButton(text="🚶 Легкая активность (1-3 тренировки/неделю)")],
            [KeyboardButton(text="🏃 Средняя активность (3-5 тренировок/неделю)")],
            [KeyboardButton(text="🏋️ Высокая активность (6-7 тренировок/неделю)")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_goal_keyboard():
    """Клавиатура для выбора цели"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚖️ Похудение")],
            [KeyboardButton(text="💪 Набор массы")],
            [KeyboardButton(text="🏃 Поддержание формы")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_level_keyboard():
    """Клавиатура для выбора уровня подготовки"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👶 Начинающий")],
            [KeyboardButton(text="👨‍🎓 Продолжающий")],
            [KeyboardButton(text="🏆 Продвинутый")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_days_keyboard():
    """Клавиатура для выбора дней тренировок"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="2 дня"), KeyboardButton(text="3 дня")],
            [KeyboardButton(text="4 дня"), KeyboardButton(text="5 дней")],
            [KeyboardButton(text="6 дней")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# Алиасы для обратной совместимости
get_main_menu = get_main_keyboard
get_workout_level_keyboard = get_level_keyboard
get_workout_days_keyboard = get_days_keyboard