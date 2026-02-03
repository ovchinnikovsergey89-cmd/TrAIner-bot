# test_groq.py
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
print(f"Ключ: {api_key[:10]}..." if api_key else "Ключ не найден")

if api_key and api_key.startswith("gsk_"):
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        print("✅ Groq клиент создан успешно")
        
        # Быстрый тест запроса
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": "Привет! Ответь коротко."}],
            max_tokens=10
        )
        print(f"✅ Тестовый запрос выполнен: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"❌ Ошибка Groq: {e}")
else:
    print("❌ Ключ Groq невалидный или отсутствует")
