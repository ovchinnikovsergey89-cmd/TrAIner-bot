import whisper
import os
import sys

def test():
    print("--- ГЛУБОКАЯ ДИАГНОСТИКА WHISPER ---")
    
    # Путь, куда Whisper качает модели по умолчанию
    model_path = os.path.expanduser("~/.cache/whisper/tiny.pt")
    
    if not os.path.exists(model_path):
        print(f"⏳ Модель еще не скачана. Сейчас начнется загрузка в {model_path}...")
        print("ℹ️ Это может занять от 1 до 5 минут. Не прерывай процесс!")
    else:
        print(f"✅ Файл модели найден: {os.path.getsize(model_path) // 1024 // 1024} МБ")

    try:
        print("🧠 Загружаем модель в память...")
        # device="cpu" принудительно, так как на VDS нет видеокарты
        model = whisper.load_model("tiny", device="cpu")
        print("✅ МОДЕЛЬ УСПЕШНО ЗАГРУЖЕНА!")
        
        print("🚀 Система полностью готова к работе с аудио.")
        
    except Exception as e:
        print(f"❌ Произошла ошибка: {str(e)}")
        # Проверим специфические ошибки импорта
        if "torch" in str(e).lower():
            print("💡 Похоже, проблема с библиотекой PyTorch. Попробуй: pip install torch")

if __name__ == "__main__":
    test()