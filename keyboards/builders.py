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

def get_gender_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора пола"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="👨 Мужской"),
        KeyboardButton(text="👩 Женский")
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_activity_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура уровня активности"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Сидячий (без спорта)"))
    builder.add(KeyboardButton(text="Малая (1-3 тренировки)"))
    builder.add(KeyboardButton(text="Средняя (3-5 тренировок)"))
    builder.add(KeyboardButton(text="Высокая (6-7 тренировок)"))
    builder.add(KeyboardButton(text="Экстремальная (физ. труд)"))
    builder.adjust(1) # Кнопки в 1 столбик
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_goal_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора цели"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📉 Похудение"),
        KeyboardButton(text="⚖️ Поддержание")
    )
    builder.row(
        KeyboardButton(text="💪 Набор массы")
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_workout_level_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура уровня подготовки"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🐣 Новичок"),
        KeyboardButton(text="🏃 Любитель")
    )
    builder.row(
        KeyboardButton(text="🏋️‍♂️ Продвинутый")
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_workout_days_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора количества дней тренировок (1-7)"""
    builder = ReplyKeyboardBuilder()
    for i in range(1, 8):
        # Склонение слова "день"
        if i == 1:
            day_text = "день"
        elif 2 <= i <= 4:
            day_text = "дня"
        else:
            day_text = "дней"
            
        builder.add(KeyboardButton(text=f"{i} {day_text}"))
    
    builder.adjust(3) # По 3 кнопки в ряд
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_profile_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура меню профиля (если нужна отдельно)"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🔄 Изменить данные"))
    builder.row(KeyboardButton(text="🔙 В главное меню"))
    return builder.as_markup(resize_keyboard=True)