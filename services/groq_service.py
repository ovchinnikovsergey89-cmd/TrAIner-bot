import logging
import datetime
import re
from datetime import timedelta
from openai import AsyncOpenAI
from config import Config

class GroqService:
    def __init__(self):
        self.api_key = Config.DEEPSEEK_API_KEY
        self.client = None
        self.model = "deepseek-chat"
        
        if self.api_key:
            try:
                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url="https://api.deepseek.com"
                )
            except Exception as e:
                logging.error(f"Err: {e}")

    # --- ОЧИСТКА ОТВЕТА ---
    def _clean_response(self, text: str) -> str:
        if not text: return ""
        # Удаляем "мысли" (если модель r1) и маркеры кода
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'^```html', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```markdown', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```', '', text, flags=re.MULTILINE)
        return text.strip()

    # --- РАЗБИВКА ПО СТРАНИЦАМ ---
    def _smart_split(self, text: str) -> list[str]:
        text = self._clean_response(text)
        # Разбиваем по разделителю
        pages = text.split("===PAGE_BREAK===")
        
        clean_pages = []
        for p in pages:
            stripped = p.strip()
            if len(stripped) > 20:
                clean_pages.append(stripped)
        
        if not clean_pages: return [text]
        return clean_pages

    # --- ГЕНЕРАЦИЯ ДАТ ---
    def _get_dates_list(self, days_count: int) -> list[str]:
        today = datetime.date.today()
        dates = []
        months = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
        weekdays = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
        
        current_date = today + timedelta(days=1)
        step = 1
        if days_count <= 3: step = 2 
        
        for _ in range(days_count):
            d_str = f"{current_date.day} {months[current_date.month-1]} ({weekdays[current_date.weekday()]})"
            dates.append(d_str)
            current_date += timedelta(days=step)
        return dates

    # --- АНАЛИЗ ПРОГРЕССА (НОВОЕ) ---
    async def analyze_progress(self, user_data: dict, current_weight: float) -> str:
        if not self.client: return "Ошибка API"
        
        old_weight = user_data.get('weight', current_weight)
        goal = user_data.get('goal', 'Форма')
        
        prompt = f"""
        Ты — фитнес-эксперт. Проанализируй изменение веса.
        
        ДАННЫЕ:
        - Было: {old_weight} кг
        - Стало: {current_weight} кг
        - Цель клиента: {goal}
        
        ЗАДАЧА:
        Дай очень краткий комментарий (максимум 2-3 предложения).
        Если динамика положительная (к цели) — похвали.
        Если застой или откат — дай 1 конкретный совет без воды.
        """
        
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.6
            )
            return self._clean_response(r.choices[0].message.content)
        except Exception as e:
            logging.error(f"Analysis error: {e}")
            return "Данные приняты! Продолжаем работу."

    # --- ГЕНЕРАЦИЯ ТРЕНИРОВКИ ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка: API ключ не найден"]
        
        level = user_data.get('workout_level', 'Новичок')
        days = user_data.get('workout_days', 3)
        goal = user_data.get('goal', 'Форма')
        gender = user_data.get('gender', '—')
        age = user_data.get('age', '—')
        weight = user_data.get('weight', '—')
        
        dates_list = self._get_dates_list(days)
        dates_str = ", ".join(dates_list)

        system_prompt = (
            "Ты — профессиональный тренер. Твоя задача — генерировать сухие, четкие программы. "
            "Никакой воды. Никаких вступлений. Строгое форматирование."
        )

        user_prompt = f"""
        СОСТАВЬ ПРОГРАММУ (Уровень: {level}, Цель: {goal}, Дней: {days}).
        Данные клиента: {gender}, {age} лет, {weight} кг.
        Даты тренировок: {dates_str}

        ТРЕБОВАНИЯ К ФОРМАТУ:
        1. Раздели дни строкой ===PAGE_BREAK===.
        2. Всего должно быть {days} блоков тренировок + 1 блок советов в конце.
        3. Между упражнениями ОБЯЗАТЕЛЬНО делай пустую строку.
        4. После заголовка даты ОБЯЗАТЕЛЬНО пустая строка.

        ШАБЛОН ОДНОГО ДНЯ (СТРОГО):
        📅 **[Дата] — [Группа мышц]**
        
        1. **[Название упражнения]**
        *[Подходы] x [Повторения] (отдых [сек])*
        Техника: [Очень краткое описание, 1 предложение]

        2. **[Название упражнения]**
        *[Подходы] x [Повторения]*
        Техника: ...

        (и так далее 5-6 упражнений)
        
        🧘 **Заминка**: [1 предложение]

        ШАБЛОН БЛОКА СОВЕТОВ (ПОСЛЕДНЯЯ СТРАНИЦА):
        ===PAGE_BREAK===
        💡 **Сводка рекомендаций**
        
        1. [Совет по питанию - 1 строка]
        2. [Совет по режиму - 1 строка]
        3. [Совет по прогрессии - 1 строка]
        """
        
        try:
            r = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ], 
                model=self.model, 
                temperature=0.3
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception as e:
            logging.error(f"Workout Gen Error: {e}")
            return ["❌ Ошибка генерации."]

    # --- ГЕНЕРАЦИЯ ПИТАНИЯ ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        kcal = self._calculate_target_calories(user_data)
        goal = user_data.get('goal', 'Здоровье')
        
        prompt = f"""
        Составь конструктор рациона на ~{kcal} ккал (Цель: {goal}).
        
        СТРОГИЕ ПРАВИЛА:
        1. НИКАКИХ вступлений вроде "Вот ваш план". Сразу начинай с Завтрака.
        2. Для каждого приема пищи дай 3 равноценных варианта.
        3. Используй разделитель ===PAGE_BREAK=== между приемами пищи.
        4. Обязательно пустая строка после заголовка.

        ФОРМАТ ВЫВОДА:
        🍳 **ЗАВТРАК** (~[Ккал] ккал)
        
        1. **[Название блюда]**
        Состав: [Кратко ингредиенты] (КБЖУ: ...)
        
        2. **[Название блюда]**
        Состав: ...
        
        3. **[Название блюда]**
        Состав: ...

        ===PAGE_BREAK===
        🍲 **ОБЕД** (~[Ккал] ккал)
        
        1. ...
        2. ...
        3. ...

        ===PAGE_BREAK===
        🥗 **УЖИН** (~[Ккал] ккал)
        
        1. ...
        2. ...
        3. ...

        ===PAGE_BREAK===
        🛒 **СПИСОК ПРОДУКТОВ**
        
        - [Категория]: [Продукты]
        - [Категория]: [Продукты]
        (Только список, без лишних слов)
        """
        
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model, temperature=0.4
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception as e: return [f"Ошибка: {e}"]

    def _calculate_target_calories(self, user_data: dict) -> int:
        try:
            weight = float(user_data.get('weight', 70))
            height = float(user_data.get('height', 170))
            age = int(user_data.get('age', 30))
            gender = user_data.get('gender', 'male')
            
            if gender == 'male':
                bmr = 10 * weight + 6.25 * height - 5 * age + 5
            else:
                bmr = 10 * weight + 6.25 * height - 5 * age - 161
            
            return int(bmr * 1.375)
        except:
            return 2000

    # --- ЧАТ ---
    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Ошибка конфигурации API"
        
        system_msg = {
            "role": "system", 
            "content": "Ты тренер. Отвечай предельно кратко (макс 30 слов). Без воды."
        }
        
        try:
            msgs = [system_msg] + history[-5:]
            r = await self.client.chat.completions.create(messages=msgs, model=self.model)
            return self._clean_response(r.choices[0].message.content)
        except: return "Ошибка сети"