import time
import io
import subprocess

def test_system():
    print("--- Начинаем тест системы ---")
    
    # 1. Проверка FFmpeg
    start = time.time()
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        print(f"✅ FFmpeg найден (проверка заняла {time.time()-start:.2f}с)")
    except Exception:
        print("❌ FFmpeg НЕ НАЙДЕН! Установи его: sudo apt install ffmpeg")
        return

    # 2. Тест скорости процессора (Симуляция обработки аудио)
    start = time.time()
    _ = [sum(range(10000)) for _ in range(500)] 
    print(f"⚙️ Тест процессора: {time.time()-start:.2f}с (норма до 0.5с)")

    # 3. Тест "памяти"
    try:
        dummy_data = b"0" * (10 * 1024 * 1024) # 10 MB
        audio_io = io.BytesIO(dummy_data)
        print(f"🧠 Память: выделение 10МБ прошло успешно")
    except MemoryError:
        print("❌ ОШИБКА ПАМЯТИ! Нужен Swap файл.")

if __name__ == "__main__":
    test_system()