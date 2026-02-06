from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def get_main_menu() -> ReplyKeyboardMarkup:
    """
    Создает главную клавиатуру бота.
    """
    builder = ReplyKeyboardBuilder()
    
    # 1 ряд: Генерация (AI)
    builder.row(
        KeyboardButton(text="🤖 AI Тренировка"),
        KeyboardButton(text="🍏 Питание")
    )
    
    # 2 ряд: Сохраненное (Личное)
    builder.row(
        KeyboardButton(text="📅 Моя программа"),
        KeyboardButton(text="🍽 Мое меню")
    )
    
    # 3 ряд: Активные функции (Чат и видео)
    builder.row(
        KeyboardButton(text="💬 Чат с тренером"),
        KeyboardButton(text="🎥 Техника")
    )

    # 4 ряд: Аналитика и Профиль
    builder.row(
        KeyboardButton(text="📊 Анализ"),
        KeyboardButton(text="👤 Профиль")
    )
    
    # 5-ГО РЯДА БОЛЬШЕ НЕТ (Удалены "Изменить данные" и "Помощь")
    
    return builder.as_markup(resize_keyboard=True, input_field_placeholder="Выберите действие...")