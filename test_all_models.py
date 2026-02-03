import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if api_key:
    from groq import Groq
    client = Groq(api_key=api_key)
    
    models_to_test = [
        "llama-3.1-70b-versatile",
        "llama-3.2-90b-vision-preview", 
        "llama-3.2-1b-preview",
        "mixtral-8x7b-32768",
        "gemma2-9b-it"
    ]
    
    print("🔍 Тестирую доступные модели Groq...")
    
    for model in models_to_test:
        try:
            print(f"\n🔄 Тест модели: {model}")
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Привет"}],
                max_tokens=5
            )
            print(f"✅ {model} - работает: {response.choices[0].message.content}")
        except Exception as e:
            print(f"❌ {model} - ошибка: {str(e)[:100]}")