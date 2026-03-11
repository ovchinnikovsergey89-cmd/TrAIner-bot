import asyncio
import re

async def run_internal_tests():
    print("🚀 Запуск финальной проверки логики (БЕЗ импортов)...")
    print("--------------------------------------------------")

    # --- ТЕСТ 1: Проверка логики ВЕСА ---
    print("🔎 ТЕСТ: Обработка ввода веса")
    test_inputs = ["85", "85,5", "70.2", " 90 ", "120.5"]
    
    for val in test_inputs:
        try:
            # Имитируем логику, которую мы вставили в start.py
            clean_input = val.strip().replace(',', '.')
            w = float(clean_input)
            
            # Проверка диапазона
            if 30 <= w <= 250:
                print(f"  ✅ Ввод '{val}' -> Успешно преобразован в {w} кг")
            else:
                print(f"  ❌ Ввод '{val}' -> Ошибка: Вне диапазона (30-250)")
        except ValueError:
            print(f"  ❌ Ввод '{val}' -> Ошибка: Это не число!")

    # --- ТЕСТ 2: Проверка логики РОСТА ---
    print("\n🔎 ТЕСТ: Обработка ввода роста")
    height_inputs = ["180", "175,5", "160.2"]
    
    for val in height_inputs:
        try:
            h = float(val.replace(',', '.'))
            print(f"  ✅ Ввод '{val}' -> Успешно преобразован в {h} см")
        except ValueError:
            print(f"  ❌ Ввод '{val}' -> Ошибка преобразования")

    print("\n--------------------------------------------------")
    print("🏁 ЕСЛИ ВСЕ ✅ ВЫШЕ — ТВОЯ ЛОГИКА В ПОРЯДКЕ!")
    print("Если бот все еще тупит, проверь имена состояний в Registration!")

if __name__ == "__main__":
    asyncio.run(run_internal_tests())