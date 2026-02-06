from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def get_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    
    # 1 ряд
    builder.row(
        KeyboardButton(text="🤖 AI Тренировка"),
        KeyboardButton(text="🍏 Питание")
    )
    
    # 2 ряд
    builder.row(
        KeyboardButton(text="📅 Моя программа"),
        KeyboardButton(text="🍽 Мое меню")
    )
    
    # 3 ряд
    builder.row(
        KeyboardButton(text="💬 Чат с тренером"),
        KeyboardButton(text="🎥 Техника")
    )

    # 4 ряд (Анализ и Профиль)
    builder.row(
        KeyboardButton(text="📊 Анализ"),
        KeyboardButton(text="👤 Профиль")
    )
    
    # 5-го ряда нет!
    
    return builder.as_markup(resize_keyboard=True, input_field_placeholder="Выберите действие...")