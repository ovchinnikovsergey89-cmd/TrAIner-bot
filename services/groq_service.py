import logging
import datetime
import re
from datetime import timedelta
from openai import AsyncOpenAI
from config import Config
from utils.text_tools import clean_text

logger = logging.getLogger(__name__)

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
                logger.error(f"Init Error: {e}")

    def _smart_split(self, text: str) -> list[str]:
        text = clean_text(text)
        pages = text.split("===PAGE_BREAK===")
        return [p.strip() for p in pages if len(p.strip()) > 20]

    def _get_dates_list(self, days_count: int) -> list[str]:
        today = datetime.date.today()
        dates = []
        months = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
        weekdays = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
        
        current_date = today 
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
        Ты — TrAIner. Анализ веса: {old_weight} -> {current_weight} (Цель: {goal}).
        Дай краткую оценку динамики и 1 совет. Используй теги <b> и <i>.
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model, temperature=0.7
            )
            return clean_text(r.choices[0].message.content)
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return "Тренер записал вес."

    # --- ТРЕНИРОВКА ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        level = user_data.get('workout_level', 'Новичок')
        days = user_data.get('workout_days', 3)
        
        dates_list = self._get_dates_list(days)
        dates_str = ", ".join(dates_list)

        system_prompt = "Ты — TrAIner. Пиши программу, используя HTML теги (b, i)."

        user_prompt = f"""
        СОСТАВЬ ПРОГРАММУ ({level}, {user_data.get('goal')}, {days} дн).
        
        ДАТЫ ТРЕНИРОВОК (Обязательно подставь их в заголовки!): 
        {dates_str}

        ФОРМАТ ДНЯ (Строго соблюдай):
        📅 <b>[Дата из моего списка] — [Группа мышц]</b>
        
        1. <b>[Упражнение]</b>
        <i>[Подходы] x [Повторения]</i>
        Техника: [Очень кратко]
        (ТУТ ПУСТАЯ СТРОКА)
        2. <b>[Упражнение]</b>...

        Раздели дни строкой ===PAGE_BREAK===.
        В конце добавь блок "Советы".
        """
        
        try:
            r = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ], model=self.model, temperature=0.3
            )
            return self._smart_split(r.choices[0].message.content)
        except: return ["❌ Ошибка генерации."]

    # --- ПИТАНИЕ ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        kcal = self._calculate_target_calories(user_data)
        
        # 🔥 ОБНОВЛЕННЫЙ ПРОМПТ: Жирные названия и КБЖУ
        prompt = f"""
        Составь рацион на ~{kcal} ккал.
        ВАЖНО: НЕ ПИШИ ВСТУПЛЕНИЕ.
        
        ФОРМАТ ВЫВОДА ДЛЯ КАЖДОГО БЛЮДА (СТРОГО):
        Вариант X: <b>[Название блюда]</b>
        * [Ингредиенты/Рецепт кратко]
        * <b>КБЖУ: ~[ккал] (Б:.., Ж:.., У:..)</b>
        
        СТРУКТУРА МЕНЮ (Без полдников!):
        
        🍳 <b>ЗАВТРАК (3 варианта)</b>
        (вставь 3 варианта по формату выше)
        
        ===PAGE_BREAK===
        🍲 <b>ОБЕД (3 варианта)</b>
        (вставь 3 варианта по формату выше)
        
        ===PAGE_BREAK===
        🥗 <b>УЖИН (3 варианта)</b>
        (вставь 3 варианта по формату выше)
        
        ===PAGE_BREAK===
        🥪 <b>ПЕРЕКУСЫ (3 варианта)</b>
        (вставь 3 варианта по формату выше)
        
        ===PAGE_BREAK===
        🛒 <b>СПИСОК ПРОДУКТОВ</b>
        """
        
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], 
                model=self.model, temperature=0.4
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception as e: return [f"Ошибка: {e}"]

    def _calculate_target_calories(self, user_data: dict) -> int:
        try:
            weight = float(user_data.get('weight', 70))
            height = float(user_data.get('height', 170))
            age = int(user_data.get('age', 30))
            if user_data.get('gender') == 'male':
                bmr = 10 * weight + 6.25 * height - 5 * age + 5
            else:
                bmr = 10 * weight + 6.25 * height - 5 * age - 161
            return int(bmr * 1.375)
        except: return 2000

    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Ошибка конфигурации API"
        try:
            msgs = [{"role": "system", "content": "Ты — фитнес-тренер TrAIner."}] + history[-5:]
            r = await self.client.chat.completions.create(messages=msgs, model=self.model)
            return clean_text(r.choices[0].message.content)
        except: return "Ошибка сети"