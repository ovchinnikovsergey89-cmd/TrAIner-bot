from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_pagination_kb(current_page: int, total_pages: int, page_type: str = "workout") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # === ЛОГИКА ДЛЯ ПИТАНИЯ ===
    if page_type == "nutrition":
        shopping_list_index = total_pages - 1
        
        if current_page == shopping_list_index:
            builder.row(InlineKeyboardButton(text="🔙 К меню", callback_data="nutrition_page_0"))
        else:
            prev_page = current_page - 1
            next_page = current_page + 1
            
            if prev_page >= 0:
                builder.add(InlineKeyboardButton(text="⬅️", callback_data=f"nutrition_page_{prev_page}"))
            else:
                builder.add(InlineKeyboardButton(text="▪️", callback_data="noop"))
                
            builder.add(InlineKeyboardButton(text=f"{current_page + 1}/{total_pages - 1}", callback_data="noop"))
            
            if next_page < shopping_list_index:
                builder.add(InlineKeyboardButton(text="➡️", callback_data=f"nutrition_page_{next_page}"))
            else:
                builder.add(InlineKeyboardButton(text="▪️", callback_data="noop"))
                
            builder.adjust(3)
            builder.row(InlineKeyboardButton(text="🛒 Список продуктов", callback_data=f"nutrition_page_{shopping_list_index}"))
            
            builder.row(
                InlineKeyboardButton(text="👨‍🍳 Найти рецепт", callback_data="recipe_search"),
                InlineKeyboardButton(text="💬 Вопрос тренеру", callback_data="ai_chat")
            )
            builder.row(InlineKeyboardButton(text="🔄 Новый рацион", callback_data="regen_nutrition"))

        return builder.as_markup()

    # === ЛОГИКА ДЛЯ ТРЕНИРОВОК (ОБНОВЛЕНА) ===
    # Последняя страница - это "Советы тренера"
    advice_index = total_pages - 1
    
    # 1. Если мы читаем СОВЕТЫ
    if current_page == advice_index:
        builder.row(InlineKeyboardButton(text="🔙 Вернуться к программе", callback_data="workout_page_0"))
        
    # 2. Если мы листаем ДНИ ТРЕНИРОВОК
    else:
        prev_page = current_page - 1
        next_page = current_page + 1
        
        # Стрелка влево
        if prev_page >= 0:
            builder.add(InlineKeyboardButton(text="⬅️", callback_data=f"workout_page_{prev_page}"))
        else:
            builder.add(InlineKeyboardButton(text="▪️", callback_data="noop"))
            
        # Счетчик (показываем кол-во дней, исключая страницу советов)
        display_total = total_pages - 1 if total_pages > 1 else 1
        builder.add(InlineKeyboardButton(text=f"День {current_page + 1}/{display_total}", callback_data="noop"))
        
        # Стрелка вправо (не пускаем на страницу советов стрелкой)
        if next_page < advice_index:
            builder.add(InlineKeyboardButton(text="➡️", callback_data=f"workout_page_{next_page}"))
        else:
            builder.add(InlineKeyboardButton(text="▪️", callback_data="noop"))
        
        builder.adjust(3)
        
        # Кнопка перехода к Советам
        builder.row(InlineKeyboardButton(text="💡 Советы тренера", callback_data=f"workout_page_{advice_index}"))
        
        # Доп кнопки
        builder.row(
            InlineKeyboardButton(text="🎥 Техника", callback_data="video_search"),
            InlineKeyboardButton(text="💬 Вопрос тренеру", callback_data="ai_chat")
        )
        builder.row(InlineKeyboardButton(text="🔄 Новая программа", callback_data="regen_workout"))
        
    return builder.as_markup()