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
        # Удаляем "мысли" нейросети
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'^```html', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```', '', text, flags=re.MULTILINE)
        return text.strip()

    # --- ЖЕСТКАЯ РАЗБИВКА ПО ДНЯМ ---
    def _smart_split(self, text: str) -> list[str]:
        text = self._clean_response(text)
        
        # Мы режем текст СТРОГО перед символом 📅
        # (?:^|\n) означает "начало текста или новая строка"
        pages = re.split(r'(?:^|\n)(?=📅)', text)
        
        # Выкидываем пустые куски (мусор в начале)
        pages = [p.strip() for p in pages if len(p.strip()) > 50]
        
        # Если вдруг ИИ не поставил 📅, возвращаем как есть (чтоб хоть что-то было)
        if not pages: pages = [text]

        return pages

    # --- ПРОФЕССИОНАЛЬНЫЕ ДАТЫ (СПЛИТЫ) ---
    def _calculate_dates(self, days_count: int):
        today = datetime.date.today()
        schedule = []
        months = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
        weekdays = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
        
        # Логика:
        # 1 день: Завтра
        # 2 дня: Пн, Чт (Фуллбоди)
        # 3 дня: Пн, Ср, Пт (Классика)
        # 4 дня: Пн, Вт + Чт, Пт (Верх/Низ) - ПРОФИ ВАРИАНТ
        # 5 дней: Пн-Пт
        # 6 дней: Пн-Сб
        
        offsets = []
        if days_count == 1: offsets = [1]
        elif days_count == 2: offsets = [0, 3]
        elif days_count == 3: offsets = [0, 2, 4]
        elif days_count == 4: offsets = [0, 1, 3, 4] # <-- Вот ваш сплит
        elif days_count == 5: offsets = [0, 1, 2, 4, 5]
        else: offsets = range(days_count)

        for off in offsets:
            d = today + timedelta(days=off)
            d_str = f"{d.day} {months[d.month-1]} ({weekdays[d.weekday()]})"
            schedule.append(d_str)
        return schedule

    # --- СТИЛЬ ТРЕНЕРА ---
    def _get_persona_prompt(self, style: str) -> str:
        if style == "tough": return "Ты 'Батя'. Жесткий, грубый. Смайл: 👊. Твой совет - это приказ."
        elif style == "scientific": return "Ты 'Доктор'. Умный, душный. Смайл: 🧬. Твой совет - это наука."
        else: return "Ты 'Тони'. Веселый братан. Смайл: 🔥. Твой совет - мотивация."

    # --- ГЕНЕРАЦИЯ ТРЕНИРОВКИ ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        days_count = user_data.get('workout_days', 3)
        dates_list = self._calculate_dates(days_count)
        dates_str = "\n".join(dates_list)
        style = user_data.get("trainer_style", "supportive")
        persona = self._get_persona_prompt(style)
        
        # ПРОМПТ НАСТРОЕН НА ТОЧНОСТЬ
        prompt = f"""
        Роль: Тренер. {persona}
        Задача: Программа на {days_count} дней.
        Даты:
        {dates_str}
        
        Клиент: {user_data.get('gender')}, {user_data.get('workout_level')}, Цель: {user_data.get('goal')}.

        ТРЕБОВАНИЯ К ФОРМАТУ (СТРОГО СОБЛЮДАЙ!):
        1. Напиши план для КАЖДОЙ даты из списка. Не пропускай дни!
        2. Жирным выделяй ТОЛЬКО название упражнения (пример: <b>Жим лежа</b>).
        3. Технику пиши обычным текстом.
        4. В конце каждого дня пиши "🗣 СОВЕТ ТРЕНЕРА".

        ШАБЛОН ОДНОГО ДНЯ:
        
        📅 <b>День 1 (Дата) — Название тренировки</b>
        🤸 Разминка: 5 мин.
        
        1. <b>Название упражнения</b>
        3 подхода x 12 повторений
        Техника: Спина прямая, локти в стороны.
        
        2. <b>Название упражнения</b>
        ...
        (минимум 5 упражнений)
        
        🧘 Заминка: Растяжка.
        🗣 СОВЕТ ТРЕНЕРА: (Твой уникальный комментарий в стиле {style})
        
        (Обязательно отступ перед следующим днем)
        """
        
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model, temperature=0.5
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception as e: return [f"Ошибка: {e}"]

    # --- КНОПКА "СОВЕТ ТРЕНЕРА" ---
    async def get_trainer_advice(self, user_context: dict) -> str:
        if not self.client: return "Ошибка..."
        style = user_context.get("trainer_style", "supportive")
        prompt = f"""
        {self._get_persona_prompt(style)}
        Дай ОДИН короткий, жесткий совет по тренировкам или питанию.
        Максимум 20 слов.
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model, temperature=0.8
            )
            return self._clean_response(r.choices[0].message.content)
        except: return "Ошибка сети."

    # --- ПИТАНИЕ ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        kcal = self._calculate_target_calories(user_data)
        style = user_data.get("trainer_style", "supportive")
        prompt = f"""
        {self._get_persona_prompt(style)}
        Рацион на {kcal} ккал.
        ФОРМАТ:
        🍳 ЗАВТРАК (3 варианта)
        🍲 ОБЕД (3 варианта)
        🥗 УЖИН (3 варианта)
        🛒 СПИСОК ПРОДУКТОВ
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model, temperature=0.7
            )
            # Разбиваем питание по иконкам еды
            pages = re.split(r'(?=\n(?:🍳|🍲|🥗|🛒))', self._clean_response(r.choices[0].message.content))
            return [p.strip() for p in pages if len(p.strip()) > 20]
        except Exception as e: return [f"Ошибка: {e}"]
        
    def _calculate_target_calories(self, user_data: dict) -> int:
        try: return 2000 # Упрощенная заглушка
        except: return 2000

    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Err"
        style = user_context.get("trainer_style", "supportive")
        system_msg = {"role": "system", "content": f"Ты тренер. {self._get_persona_prompt(style)}"}
        try:
            msgs = [system_msg] + history[-6:]
            r = await self.client.chat.completions.create(messages=msgs, model=self.model)
            return self._clean_response(r.choices[0].message.content)
        except: return "Ошибка сети"