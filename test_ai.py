# Создайте тестовый файл test_ai.py
import asyncio
from ai import get_ai_client

async def test_ai():
    client = get_ai_client()
    print(f"Клиент: {client}")
    print(f"use_mock: {client.use_mock if hasattr(client, 'use_mock') else 'Нет атрибута'}")
    print(f"client: {client.client if hasattr(client, 'client') else 'Нет клиента'}")
    
    # Тестовая генерация
    user_data = {'gender': 'male', 'weight': 75, 'height': 180, 'age': 30}
    try:
        result = await client.generate_personalized_workout(user_data)
        print(f"\n✅ Результат: {result[:100]}...")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

asyncio.run(test_ai())