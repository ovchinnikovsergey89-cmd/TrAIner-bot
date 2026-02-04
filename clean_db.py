import os

db_file = "trainer.db"

if os.path.exists(db_file):
    try:
        os.remove(db_file)
        print(f"✅ УРА! Файл {db_file} успешно удален.")
        print("Теперь запускай main.py — бот создаст новую базу.")
    except PermissionError:
        print(f"❌ Ошибка! Файл {db_file} занят.")
        print("Сначала ОСТАНОВИ бота (нажми Ctrl + C в терминале), а потом запусти этот скрипт снова.")
    except Exception as e:
        print(f"❌ Ошибка при удалении: {e}")
else:
    print(f"⚠️ Файл {db_file} не найден. Похоже, его и так нет.")
    print("Попробуй просто запустить main.py")