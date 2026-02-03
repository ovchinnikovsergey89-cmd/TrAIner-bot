# fix_handlers.py
import os

files = [
    "handlers/start.py",
    "handlers/profile.py", 
    "handlers/nutrition.py",
    "handlers/edit.py",
    "handlers/workout.py",
    "handlers/help.py"
]

for file in files:
    if os.path.exists(file):
        print(f"🔧 Проверяем {file}...")
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Убираем  - бот и так использует HTML
        # Но можно оставить, должно работать
        if '' in content:
            print(f"  ⚠️  В {file} есть parse_mode='Markdown' - оставляем, должно работать")
        
print("✅ Проверка завершена")
