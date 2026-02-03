async def search_recipe_video(query_text: str):
    """
    Генерирует ссылку на поиск рецептов в RuTube.
    """
    # Чистим запрос и добавляем слово "рецепт"
    clean_query = query_text.strip().replace(" ", "+")
    search_query = f"{clean_query}+рецепт+приготовления"
    
    # Формируем ссылку
    link = f"https://rutube.ru/search/?query={search_query}"
    
    title = f"🍽 Поиск рецепта: {query_text}"
    description = "Видео-рецепты на RuTube 📺" 
    
    return link, title, description