import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_db():
    print("🔍 Тестирую базу данных...")
    
    try:
        from database.database import init_db, AsyncSessionLocal
        from database.crud import UserCRUD
        
        # Инициализация БД
        await init_db()
        print("✅ База инициализирована")
        
        async with AsyncSessionLocal() as session:
            # Тест 1: Создание
            print("\n1. Создаю тестового пользователя...")
            user = await UserCRUD.get_or_create_user(
                session,
                telegram_id=999999,
                username="test_user",
                full_name="Test User",
                age=30,
                gender="male",
                weight=85.5
            )
            print(f"   Создан: ID={user.id}, вес={user.weight}кг")
            
            # Тест 2: Обновление
            print("\n2. Обновляю вес...")
            success = await UserCRUD.update_user(session, 999999, weight=95.0, height=180)
            print(f"   Обновление: {'успешно' if success else 'не удалось'}")
            
            # Тест 3: Получение
            print("\n3. Получаю обновленного...")
            updated = await UserCRUD.get_user(session, 999999)
            if updated:
                print(f"   Данные: вес={updated.weight}кг, рост={updated.height}см")
            else:
                print("   ❌ Не найден")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_db())