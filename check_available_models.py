import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if api_key:
    from groq import Groq
    client = Groq(api_key=api_key)
    
    print("🔍 Получаю список доступных моделей...")
    
    try:
        # Попробуем получить список моделей через API
        models = client.models.list()
        
        print("✅ Доступные модели:")
        for model in models.data:
            print(f"  • {model.id}")
            
        # Или попробуем популярные новые модели
        new_models = [
            "llama-3.2-90b-text-preview",  # Текстовая версия
            "llama-3.2-11b-vision-preview",
            "llama-3.2-3b-preview",
            "llama-3.2-1b-preview",
            "llama-3.2-90b-vision-preview",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
            "llama3-70b-8192",
            "llama3-8b-8192"
        ]
        
        print("\n🔄 Тестирую возможные модели...")
        for model in new_models:
            try:
                test = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "."}],
                    max_tokens=1
                )
                print(f"✅ {model} - РАБОТАЕТ!")
                break
            except:
                pass
                
    except Exception as e:
        print(f"❌ Ошибка получения моделей: {e}")
        
        # Попробуем вручную самые новые
        latest_models = [
            "llama-3.2-90b-text-preview",
            "llama-3.2-11b-vision-preview", 
            "llama-3.2-3b-preview",
            "llama-3.2-1b-preview",
            "llama-3.1-8b-instant",
            "llama-3.1-70b-instant",
            "mixtral-8x7b-instruct-v0.1"
        ]
        
        print("\n🔄 Тестирую самые новые модели...")
        for model in latest_models:
            try:
                print(f"Пробую: {model}")
                test = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "."}],
                    max_tokens=1
                )
                print(f"🎉 НАЙДЕНА РАБОЧАЯ МОДЕЛЬ: {model}")
                print(f"Ответ: {test.choices[0].message.content}")
                break
            except Exception as e:
                print(f"  ❌ {model}: {str(e)[:80]}")