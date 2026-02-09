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

    # --- ОЧИСТКА МУСОРА ---
    def _clean_response(self, text: str) -> str:
        if not text: return ""
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'^```html', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```', '', text, flags=re.MULTILINE)
        return text.strip()

    # --- БЕЗОПАСНАЯ РАЗБИВКА (FIX CRASH) ---
    def _smart_split(self, text: str) -> list[str]:
        text = self._clean_response(text)
        
        # 1. Режем строго по значку календаря 📅 (неважно, что идет дальше)
        # (?:^|\n) означает "начало строки"
        pages = re.split(r'(?:^|\n)(?=📅)', text)
        
        # Убираем пустые куски (мусор в начале)
        pages = [p.strip() for p in pages if len(p.strip()) > 50]
        
        # Если разбивка не сработала (например, нет значков), берем весь текст
        if not pages: pages = [text]

        # 2. АВАРИЙНАЯ ПРОВЕРКА ДЛИНЫ (Telegram Limit = 4096)
        final_pages = []
        for p in pages:
            if len(p) > 4000:
                # Если страница всё равно огромная, режем её принудительно
                chunks = [p[i:i+4000] for i in range(0, len(p), 4000)]
                final_pages.extend(chunks)
            else:
                final_pages.append(p)
                
        return final_pages

    # --- РАСЧЕТ ДАТ (ПРОФЕССИОНАЛЬНЫЙ) ---
    def _calculate_dates(self, days_count: int):
        today = datetime.date.today()
        schedule = []
        months = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
        weekdays = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
        
        offsets = []
        if days_count == 1: offsets = [1]
        elif days_count == 2: offsets = [0, 3] # Пн, Чт
        elif days_count == 3: offsets = [0, 2, 4] # Пн, Ср, Пт
        elif days_count == 4: offsets = [0, 1, 3, 4] # Пн, Вт + Чт, Пт
        elif days_count == 5: offsets = [0, 1, 2, 4, 5]
        elif days_count == 6: offsets = [0, 1, 2, 3, 4, 5]
        else: offsets = range(days_count)

        for off in offsets:
            d = today + timedelta(days=off)
            d_str = f"{d.day} {months[d.month-1]} ({weekdays[d.weekday()]})"
            schedule.append(d_str)
        return schedule

    # --- ОПРЕДЕЛЕНИЕ ТИПА СПЛИТА ---
    def _get_split_name(self, days: int) -> str:
        if days <= 2: return "Full Body (Все тело)"
        if days == 3: return "Full Body или Push/Pull"
        if days == 4: return "Сплит Верх / Низ"
        if days == 5: return "Сплит по группам мышц"
        return "Push / Pull / Legs"

    # --- ГЕНЕРАЦИЯ ТРЕНИРОВКИ ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        days_count = user_data.get('workout_days', 3)
        dates_list = self._calculate_dates(days_count)
        dates_str = "\n".join(dates_list)
        split_name = self._get_split_name(days_count)
        
        # ПРОМПТ: СТРОГИЙ, БЕЗ ЛИШНЕЙ БОЛТОВНИ
        prompt = f"""
        Ты профессиональный тренер.
        Задача: Составить программу на {days_count} дней.
        Сплит: {split_name}.
        Клиент: {user_data.get('gender')}, Уровень: {user_data.get('workout_level')}, Цель: {user_data.get('goal')}.
        
        ДАТЫ (СТРОГО):
        {dates_str}

        ТРЕБОВАНИЯ:
        1. Напиши план для КАЖДОЙ даты. Не обрывай ответ.
        2. Формат заголовка: "📅 День X (Дата) — Название".
        3. Никаких вступлений. Сразу к делу.
        4. В конце каждого дня: "🔥 СОВЕТ ПРОФИ".

        ШАБЛОН ОДНОГО ДНЯ:
        
        📅 <b>День 1 (Дата) — Название</b>
        🤸 Разминка: 5 мин.
        
        1. <b>Упражнение</b>
        3 x 12
        Техника: (Кратко).
        
        2. <b>Упражнение</b>
        ...
        (5-6 упражнений)
        
        🧘 Заминка: Растяжка.
        🔥 СОВЕТ ПРОФИ: (Текст совета).
        
        (Обязательно отступ)
        """
        
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model, temperature=0.5
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception as e: return [f"Ошибка: {e}"]

    # --- ГЕНЕРАЦИЯ ПИТАНИЯ ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        kcal = self._calculate_target_calories(user_data)
        
        prompt = f"""
        Рацион на {kcal} ккал. Цель: {user_data.get('goal')}.
        ФОРМАТ:
        🍳 <b>ЗАВТРАК (3 варианта)</b>
        ...
        🍲 <b>ОБЕД (3 варианта)</b>
        ...
        🥗 <b>УЖИН (3 варианта)</b>
        ...
        🛒 <b>СПИСОК ПРОДУКТОВ</b>
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model, temperature=0.6
            )
            pages = re.split(r'(?=\n(?:🍳|🍲|🥗|🛒))', self._clean_response(r.choices[0].message.content))
            # Тоже защищаем от переполнения
            final_pages = []
            for p in pages:
                if len(p) > 50:
                    if len(p) > 4000:
                        final_pages.extend([p[i:i+4000] for i in range(0, len(p), 4000)])
                    else:
                        final_pages.append(p)
            return final_pages
        except Exception as e: return [f"Ошибка: {e}"]
        
    def _calculate_target_calories(self, user_data: dict) -> int:
        try: return 2000
        except: return 2000

    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Ошибка"
        system_msg = {"role": "system", "content": "Ты профессиональный тренер. Отвечай кратко."}
        try:
            msgs = [system_msg] + history[-6:]
            r = await self.client.chat.completions.create(messages=msgs, model=self.model)
            return self._clean_response(r.choices[0].message.content)
        except: return "Ошибка сети"