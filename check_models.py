import google.generativeai as genai
import os
from dotenv import load_dotenv

# Загружаем ключ
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ Ключ не найден!")
else:
    genai.configure(api_key=api_key)
    print("🔍 Ищу доступные модели...")
    try:
        for m in genai.list_models():
            # Нам нужны только модели, которые умеют генерировать текст
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
    except Exception as e:
        print(f"Ошибка: {e}")