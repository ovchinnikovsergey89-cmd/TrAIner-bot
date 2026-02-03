import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
print(f"🔑 Ключ из .env: {api_key}")
print(f"📏 Длина ключа: {len(api_key) if api_key else 0}")

if api_key:
    print(f"✅ Ключ начинается с gsk_: {api_key.startswith('gsk_')}")
    
    try:
        from groq import Groq
        print("✅ Библиотека groq импортирована")
        
        # Пробуем разные способы
        try:
            client = Groq(api_key=api_key)
            print("✅ Клиент создан через Groq(api_key=key)")
            
            # Тестовый запрос
            response = client.chat.completions.create(
                model="llama-3.1-70b-versatile",  # НОВАЯ МОДЕЛЬ!
                messages=[{"role": "user", "content": "Скажи 'Работает'"}],
                max_tokens=10,
                temperature=0
            )
            print(f"✅ API запрос работает: {response.choices[0].message.content}")
            
        except Exception as e:
            print(f"❌ Ошибка создания клиента: {e}")
            
    except ImportError:
        print("❌ Библиотека groq не установлена")
        print("Установи: pip install groq")
else:
    print("❌ Ключ не найден в .env файле")