from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_pagination_kb(current_page: int, total_pages: int, page_type: str = "workout") -> InlineKeyboardMarkup:
    """
    Умная клавиатура:
    - Для Тренировок: обычная листалка.
    - Для Питания: Меню (3 стр) отдельно, Список покупок (последняя стр) отдельно.
    """
    builder = InlineKeyboardBuilder()
    
    # === ЛОГИКА ДЛЯ ПИТАНИЯ ===
    if page_type == "nutrition":
        shopping_list_index = total_pages - 1 # Индекс последней страницы (Списка)
        
        # 1. Если мы СМОТРИМ СПИСОК ПОКУПОК
        if current_page == shopping_list_index:
            # Показываем только кнопку "Назад"
            builder.row(InlineKeyboardButton(text="🔙 Вернуться к меню", callback_data="nutrition_page_0"))
            
        # 2. Если мы в КОНСТРУКТОРЕ МЕНЮ (Завтрак/Обед/Ужин)
        else:
            # -- Листалка (только среди блюд, не пуская на список) --
            prev_page = current_page - 1
            next_page = current_page + 1
            
            # Кнопка НАЗАД
            if prev_page >= 0:
                builder.add(InlineKeyboardButton(text="⬅️", callback_data=f"nutrition_page_{prev_page}"))
            else:
                builder.add(InlineKeyboardButton(text="▪️", callback_data="noop"))
                
            # Счетчик (показываем 1/3, а не 1/4, чтобы не путать)
            builder.add(InlineKeyboardButton(text=f"{current_page + 1}/{total_pages - 1}", callback_data="noop"))
            
            # Кнопка ВПЕРЕД (если следующая стр - это еще не список)
            if next_page < shopping_list_index:
                builder.add(InlineKeyboardButton(text="➡️", callback_data=f"nutrition_page_{next_page}"))
            else:
                builder.add(InlineKeyboardButton(text="▪️", callback_data="noop"))
                
            builder.adjust(3)
            
            # -- Кнопка перехода к СПИСКУ --
            builder.row(InlineKeyboardButton(text="🛒 Список продуктов", callback_data=f"nutrition_page_{shopping_list_index}"))
            
            # Доп функции (Рецепты, Чат)
            builder.row(
                InlineKeyboardButton(text="👨‍🍳 Найти рецепт", callback_data="recipe_search"),
                InlineKeyboardButton(text="💬 Вопрос тренеру", callback_data="ai_chat")
            )
            
            # Кнопка сброса
            builder.row(InlineKeyboardButton(text="🔄 Новый рацион (Сброс)", callback_data="regen_nutrition"))

        return builder.as_markup()

    # === ЛОГИКА ДЛЯ ТРЕНИРОВОК (Обычная) ===
    prev_page = current_page - 1
    next_page = current_page + 1
    
    if prev_page >= 0:
        builder.add(InlineKeyboardButton(text="⬅️", callback_data=f"workout_page_{prev_page}"))
    else:
        builder.add(InlineKeyboardButton(text="▪️", callback_data="noop"))
        
    builder.add(InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="noop"))
    
    if next_page < total_pages:
        builder.add(InlineKeyboardButton(text="➡️", callback_data=f"workout_page_{next_page}"))
    else:
        builder.add(InlineKeyboardButton(text="▪️", callback_data="noop"))
    
    builder.adjust(3)
    
    # Доп кнопки для тренировок
    builder.row(
        InlineKeyboardButton(text="🎥 Техника", callback_data="video_search"),
        InlineKeyboardButton(text="💬 Вопрос тренеру", callback_data="ai_chat")
    )
    builder.row(InlineKeyboardButton(text="🔄 Новая программа", callback_data="regen_workout"))
        
    return builder.as_markup()