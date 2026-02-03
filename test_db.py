import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.database import init_db, AsyncSessionLocal
from database.crud import UserCRUD
from database.models import User

async def test_db():
    print("🔍 Тестирую базу данных...")
    
    # Инициализация БД
    await init_db()
    
    async with AsyncSessionLocal() as session:
        # Тест 1: Создание пользователя
        print("1. Создаю тестового пользователя...")
        user = await UserCRUD.get_or_create_user(
            session,
            telegram_id=999999,
            username="test_user",
            full_name="Test User",
            age=30,
            gender="male",
            weight=85.5,
            height=180,
            activity_level="medium",
            goal="weight_loss",
            workout_level="beginner",
            workout_days=3
        )
        print(f"   ✅ Создан: {user}")
        print(f"   Вес: {user.weight}, Пол: {user.gender}")
        
        # Тест 2: Обновление пользователя
        print("\n2. Обновляю вес на 90 кг...")
        await UserCRUD.update_user(session, 999999, weight=90.0)
        
        # Тест 3: Получение пользователя
        print("3. Получаю обновленного пользователя...")
        updated = await UserCRUD.get_user(session, 999999)
        print(f"   ✅ Обновлен: вес={updated.weight}")
        
        # Тест 4: Проверка всех пользователей
        print("\n4. Все пользователи в БД:")
        from sqlalchemy import select
        result = await session.execute(select(User))
        users = result.scalars().all()
        for u in users:
            print(f"   👤 {u.telegram_id}: {u.full_name}, {u.weight}кг, {u.gender}")

if __name__ == "__main__":
    asyncio.run(test_db())