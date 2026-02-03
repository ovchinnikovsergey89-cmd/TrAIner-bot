import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test():
    print("🧪 Тестирую персонализацию ИИ...")
    
    from services.groq_new import GroqAITrainerService
    ai_service = GroqAITrainerService()
    
    # Тест 1: Мужчина 120 кг
    print("\n🔴 ТЕСТ 1: Мужчина 120 кг (похудение)")
    data1 = {
        "gender": "male",
        "weight": 120,
        "goal": "weight_loss",
        "workout_level": "beginner",
        "workout_days": 3,
        "age": 35,
        "height": 185
    }
    result1 = await ai_service.generate_personalized_workout(data1)
    print(f"Результат (первые 300 символов):\n{result1[:300]}...")
    
    # Тест 2: Женщина 55 кг  
    print("\n🟣 ТЕСТ 2: Женщина 55 кг (набор массы)")
    data2 = {
        "gender": "female",
        "weight": 55,
        "goal": "muscle_gain",
        "workout_level": "intermediate",
        "workout_days": 4,
        "age": 25,
        "height": 165
    }
    result2 = await ai_service.generate_personalized_workout(data2)
    print(f"Результат (первые 300 символов):\n{result2[:300]}...")
    
    # Сравнение
    print("\n📊 СРАВНЕНИЕ:")
    if result1[:200] == result2[:200]:
        print("❌ ОШИБКА: ИИ дает одинаковые ответы!")
    else:
        print("✅ УСПЕХ: ИИ дает разные ответы!")

if __name__ == "__main__":
    asyncio.run(test())