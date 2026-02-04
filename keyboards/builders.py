from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def get_gender_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Мужской"), KeyboardButton(text="Женский"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_activity_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Сидячий"), KeyboardButton(text="Малая активность"))
    builder.row(KeyboardButton(text="Средняя активность"), KeyboardButton(text="Высокая активность"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_goal_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Похудение"), KeyboardButton(text="Поддержание"))
    builder.row(KeyboardButton(text="Набор массы"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_workout_level_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Новичок"), KeyboardButton(text="Любитель"))
    builder.row(KeyboardButton(text="Продвинутый"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

# 🔥 ПЕРЕИМЕНОВАЛИ: было get_days_keyboard, стало get_workout_days_keyboard
def get_workout_days_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    # Кнопки от 1 до 7 дней
    for i in range(1, 8):
        builder.add(KeyboardButton(text=str(i)))
    builder.adjust(3, 4) # Красивое выравнивание: 3 кнопки в ряду, потом 4
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)