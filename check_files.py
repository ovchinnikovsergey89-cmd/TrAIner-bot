import os

required_files = [
    "handlers/ai_workout.py",
    "services/groq_service.py",
    "database/database.py",
    "database/models.py",
    "database/crud.py",
    "config.py",
    ".env"
]

print("🔍 Проверка файлов...")
for file in required_files:
    if os.path.exists(file):
        print(f"✅ {file}")
    else:
        print(f"❌ {file} - НЕ НАЙДЕН")

# Проверка содержимого .env
if os.path.exists(".env"):
    with open(".env", "r") as f:
        content = f.read()
        if "GROQ_API_KEY=gsk_" in content:
            print("✅ Groq API ключ найден в .env")
        else:
            print("⚠️  Groq API ключ не найден в .env")
