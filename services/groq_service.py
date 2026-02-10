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

    def _clean_response(self, text: str) -> str:
        if not text: return ""
        
        # 1. Удаляем блоки "мыслей" (для deepseek-reasoner)
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        # 2. Удаляем маркеры кода ```html и ```
        text = re.sub(r'```html', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```', '', text)
        
        # 3. Превращаем Markdown жирный в HTML жирный (на всякий случай)
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        
        # 4. ЧИСТКА ЗАПРЕЩЕННЫХ ТЕГОВ
        # Телеграм не понимает div, p, span. Удаляем их, оставляя содержимое.
        for tag in ['div', 'p', 'span', 'html', 'body', 'header', 'footer']:
            text = re.sub(f'</?{tag}.*?>', '', text, flags=re.IGNORECASE)
            
        # 5. Тег <br> меняем на перенос строки
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        
        return text.strip()

    def _smart_split(self, text: str) -> list[str]:
        text = self._clean_response(text)
        pages = text.split("===PAGE_BREAK===")
        clean_pages = [p.strip() for p in pages if len(p.strip()) > 20]
        if not clean_pages: return [text]
        return clean_pages

    def _get_dates_list(self, days_count: int) -> list[str]:
        today = datetime.date.today()
        dates = []
        months = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
        weekdays = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
        current_date = today + timedelta(days=1)
        step = 1 if days_count > 3 else 2
        
        for _ in range(days_count):
            d_str = f"{current_date.day} {months[current_date.month-1]} ({weekdays[current_date.weekday()]})"
            dates.append(d_str)
            current_date += timedelta(days=step)
        return dates

    # --- АНАЛИЗ ПРОГРЕССА ---
    async def analyze_progress(self, user_data: dict, current_weight: float) -> str:
        if not self.client: return "Ошибка API"
        
        old_weight = user_data.get('weight', current_weight)
        goal = user_data.get('goal', 'Форма')
        
        prompt = f"""
        Ты — фитнес-тренер. Проведи анализ веса.
        ДАННЫЕ: {old_weight} кг -> {current_weight} кг (Цель: {goal}).
        
        ЗАДАЧА:
        Дать развернутый ответ (10-12 предложений) с планом действий.
        
        СТРОГИЕ ПРАВИЛА ФОРМАТА:
        1. Используй ТОЛЬКО теги <b> и <i>.
        2. ЗАПРЕЩЕНО использовать <div>, <p>, <span>, markdown (**).
        3. Делай отступы пустыми строками.
        
        СТРУКТУРА:
        1. <b>Оценка</b>: Твой вердикт.
        2. <b>Причины</b>: Почему вес изменился (вода/жир/мышцы).
        3. <b>План</b> (3 пункта): Питание, Тренировки, Режим.
        """
        
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.7,
                timeout=50
            )
            return self._clean_response(r.choices[0].message.content)
        except Exception as e:
            logging.error(f"Analysis error: {e}")
            return "Результат зафиксирован. <b>Продолжаем работать!</b>"

    # --- ГЕНЕРАЦИЯ ТРЕНИРОВКИ ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка: API ключ не найден"]
        
        level = user_data.get('workout_level', 'Новичок')
        days = user_data.get('workout_days', 3)
        goal = user_data.get('goal', 'Форма')
        gender = user_data.get('gender', '—')
        age = user_data.get('age', '—')
        weight = user_data.get('weight', '—')
        dates_str = ", ".join(self._get_dates_list(days))

        system_prompt = "Ты — тренер. Пиши программы используя HTML теги: <b>для названий</b>, <i>для цифр</i>."

        user_prompt = f"""
        СОСТАВЬ ПРОГРАММУ ({level}, {goal}, {days} дней).
        Клиент: {gender}, {age} лет, {weight} кг.
        Даты: {dates_str}

        ТРЕБОВАНИЯ:
        1. Раздели дни строкой ===PAGE_BREAK===.
        2. Всего {days} тренировок + 1 блок советов.
        3. НИКАКОГО MARKDOWN. Только HTML (b, i).

        ШАБЛОН ДНЯ:
        📅 <b>[Дата] — [Мышечная группа]</b>
        
        1. <b>[Упражнение]</b>
        <i>[Подходы] x [Повторения]</i>
        Техника: [Кратко]

        (и так далее)
        
        🧘 <b>Заминка</b>: [1 предложение]

        ШАБЛОН СОВЕТОВ:
        ===PAGE_BREAK===
        💡 <b>Сводка рекомендаций</b>
        1. [Питание]
        2. [Режим]
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
            return ["❌ Ошибка генерации."]

    # --- ГЕНЕРАЦИЯ ПИТАНИЯ ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        kcal = self._calculate_target_calories(user_data)
        goal = user_data.get('goal', 'Здоровье')
        
        prompt = f"""
        Рацион на ~{kcal} ккал ({goal}). Используй HTML (b, i).
        
        ФОРМАТ:
        🍳 <b>ЗАВТРАК</b> (~[Ккал])
        1. <b>[Блюдо]</b> (КБЖУ: ...)
        2. <b>[Блюдо]</b>
        3. <b>[Блюдо]</b>

        ===PAGE_BREAK===
        🍲 <b>ОБЕД</b>
        ...
        ===PAGE_BREAK===
        🛒 <b>СПИСОК ПРОДУКТОВ</b>
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

    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Ошибка конфигурации API"
        try:
            msgs = [{"role": "system", "content": "Ты тренер. Отвечай кратко."}] + history[-5:]
            r = await self.client.chat.completions.create(messages=msgs, model=self.model)
            return self._clean_response(r.choices[0].message.content)
        except: return "Ошибка сети"