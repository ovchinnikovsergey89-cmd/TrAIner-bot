# data/gifs.py

# Мы используем прямые ссылки. Telegram сам их кэширует.
# Это работает быстро и не требует ручной загрузки.

EXERCISE_DB = {
    # --- НОГИ ---
    "приседания": "https://media.giphy.com/media/1yMvhR4M47Okw4n8tt/giphy.gif",
    "присед": "https://media.giphy.com/media/1yMvhR4M47Okw4n8tt/giphy.gif",
    "выпады": "https://i.imgur.com/8E89k56.gif",
    "жим ногами": "https://i.imgur.com/5w5Zf5M.gif",
    "румынская тяга": "https://i.imgur.com/5yKxG8a.gif",
    "становая тяга": "https://media.giphy.com/media/pVPkaB65C5Xfq/giphy.gif",
    "становая": "https://media.giphy.com/media/pVPkaB65C5Xfq/giphy.gif",
    "икры": "https://i.imgur.com/1GzW15A.gif",
    "ягодичный мост": "https://i.imgur.com/7gX8X8o.gif",

    # --- ГРУДЬ ---
    "жим лежа": "https://media.giphy.com/media/zCK3iQqYVwxRu/giphy.gif",
    "жим": "https://media.giphy.com/media/zCK3iQqYVwxRu/giphy.gif",
    "жим гантелей": "https://i.imgur.com/0v8v8v8.gif", # Пример (нужно заменить если битая)
    "отжимания": "https://media.giphy.com/media/KtsOP8M5t3QYJmY5V4/giphy.gif",
    "брусья": "https://i.imgur.com/5yKxG8a.gif", # Условная ссылка, лучше найти точную
    "разводка": "https://i.imgur.com/example.gif",

    # --- СПИНА ---
    "подтягивания": "https://media.giphy.com/media/xT8qB4c7m4p0Q/giphy.gif",
    "тяга блока": "https://i.imgur.com/3q123.gif", 
    "тяга в наклоне": "https://media.giphy.com/media/UHL3pSjC8sP4s/giphy.gif",
    "тяга гантели": "https://i.imgur.com/example_row.gif",
    "гиперэкстензия": "https://i.imgur.com/example_hyper.gif",

    # --- ПЛЕЧИ ---
    "жим вверх": "https://media.giphy.com/media/3o7TKs8u8Qx4e/giphy.gif",
    "жим армейский": "https://media.giphy.com/media/3o7TKs8u8Qx4e/giphy.gif",
    "махи": "https://i.imgur.com/example_fly.gif",
    "протяжка": "https://i.imgur.com/example_pull.gif",

    # --- РУКИ ---
    "бицепс": "https://media.giphy.com/media/l41lUjUgLLwWp/giphy.gif",
    "молотки": "https://i.imgur.com/example_hammer.gif",
    "трицепс": "https://media.giphy.com/media/3o7TKs8u8Qx4e/giphy.gif",
    "французский жим": "https://i.imgur.com/example_french.gif",

    # --- ПРЕСС / КАРДИО ---
    "планка": "https://media.giphy.com/media/xT5LMxq82zW4C5tS6Y/giphy.gif",
    "скручивания": "https://media.giphy.com/media/l41lUjUgLLwWp/giphy.gif",
    "берпи": "https://media.giphy.com/media/23hPPmr8AztMScYDHu/giphy.gif",
    "джампинг джек": "https://media.giphy.com/media/3o6Zxp/giphy.gif"
}

def search_exercise_gif(query: str):
    """Ищет упражнение по части названия"""
    query = query.lower().strip()
    
    # 1. Прямое совпадение ключей
    for name, url in EXERCISE_DB.items():
        if query in name:
            return url, name.capitalize()
            
    return None, None