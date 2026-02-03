import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
print(f"🔑 Ключ из .env: {api_key[:10]}...")

if api_key and api_key.startswith("gsk_"):
    try:
        from groq import Groq
        print("✅ Библиотека groq импортирована")
        
        client = Groq(api_key=api_key)
        print("✅ Клиент Groq создан")
        
        # Тестируем с НОВОЙ моделью
        print("🔄 Тестирую новую модель llama-3.1-70b-versatile...")
        
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",  # НОВАЯ МОДЕЛЬ
            messages=[{"role": "user", "content": "Скажи коротко 'Тест пройден'"}],
            max_tokens=10,
            temperature=0
        )
        
        print(f"✅ API запрос работает! Ответ: {response.choices[0].message.content}")
        print("🚀 Groq API готов к использованию в боте!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
else:
    print("❌ Ключ не найден или невалидный")