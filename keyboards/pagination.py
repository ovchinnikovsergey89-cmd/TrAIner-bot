from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_pagination_kb(current_page: int, total_pages: int, page_type: str = "workout") -> InlineKeyboardMarkup:
    """
    Генерирует кнопки листания + доп. кнопки (Техника/Рецепты/Чат)
    """
    builder = InlineKeyboardBuilder()
    
    # --- РЯД 1: Листалка (⬅️ 1/3 ➡️) ---
    prev_page = current_page - 1
    next_page = current_page + 1
    
    prefix = "workout_page" if page_type == "workout" else "nutrition_page"
    
    # Кнопка НАЗАД
    if prev_page >= 0:
        builder.add(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}_{prev_page}"))
    else:
        builder.add(InlineKeyboardButton(text="▪️", callback_data="noop")) # Заглушка
        
    # Счетчик
    builder.add(InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="noop"))
    
    # Кнопка ВПЕРЕД
    if next_page < total_pages:
        builder.add(InlineKeyboardButton(text="➡️", callback_data=f"{prefix}_{next_page}"))
    else:
        builder.add(InlineKeyboardButton(text="▪️", callback_data="noop"))
    
    # Делаем этот ряд (3 кнопки)
    builder.adjust(3)
    
    # --- РЯД 2: Дополнительные функции ---
    extra_buttons = []
    
    if page_type == "workout":
        # В тренировках добавляем Технику
        extra_buttons.append(InlineKeyboardButton(text="🎥 Техника", callback_data="video_search"))
        
    elif page_type == "nutrition":
        # В питании добавляем Рецепты
        extra_buttons.append(InlineKeyboardButton(text="👨‍🍳 Найти рецепт", callback_data="recipe_search"))
    
    # Везде добавляем чат с тренером (удобно спросить совет)
    extra_buttons.append(InlineKeyboardButton(text="💬 Вопрос тренеру", callback_data="ai_chat"))
    
    # Добавляем второй ряд кнопок
    builder.row(*extra_buttons)
        
    return builder.as_markup()