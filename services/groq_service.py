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

    # --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
    def _calculate_target_calories(self, user_data: dict) -> int:
        try:
            w = float(user_data.get('weight', 70))
            h = float(user_data.get('height', 170))
            a = int(user_data.get('age', 30))
            g = user_data.get('gender', 'male')
            act = user_data.get('activity_level', 'medium')
            goal = user_data.get('goal', 'maintenance')
            
            if 'Муж' in str(g) or 'male' in str(g): bmr = 10*w + 6.25*h - 5*a + 5
            else: bmr = 10*w + 6.25*h - 5*a - 161
            
            multipliers = {"sedentary": 1.2, "light": 1.375, "medium": 1.55, "high": 1.725}
            tdee = bmr * multipliers.get(str(act), 1.55)
            
            if goal == "weight_loss": return int(tdee * 0.85)
            if goal == "muscle_gain": return int(tdee * 1.15)
            return int(tdee)
        except: return 2000

    def _clean_response(self, text: str) -> str:
        if not text: return ""
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'^```html', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```', '', text, flags=re.MULTILINE)
        
        match = re.search(r'(📅)', text)
        if match: text = text[match.start():]
            
        return text.strip()

    def _smart_split(self, text: str) -> list[str]:
        text = self._clean_response(text)
        
        # Бьем по разделам
        pages = re.split(r'(?=\n(?:🍳|🍲|🥗|🥪|🛒))', text)
        
        # Фильтруем
        pages = [p.strip() for p in pages if len(p.strip()) > 20]
        
        # Страховка если разбивка не сработала
        if len(pages) < 2:
            if len(text) > 3000:
                pages = [text[i:i+3000] for i in range(0, len(text), 3000)]
            else:
                pages = [text]

        # Финальная проверка длины
        final_pages = []
        for p in pages:
            if len(p) > 3800:
                chunks = [p[i:i+3800] for i in range(0, len(p), 3800)]
                final_pages.extend(chunks)
            else:
                final_pages.append(p)
                
        return final_pages

    def _calculate_dates(self, days_per_week: int):
        today = datetime.date.today()
        offsets = {1:[0], 2:[0,3], 3:[0,2,4], 4:[0,1,3,4], 5:[0,1,2,3,4], 6:[0,1,2,3,4,5]}.get(days_per_week, [0,2,4])
        schedule = []
        months = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
        weekdays = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
        for off in offsets:
            d = today + timedelta(days=off)
            schedule.append(f"{d.day} {months[d.month-1]} ({weekdays[d.weekday()]})")
        return schedule

    # --- ЛИЧНОСТИ ТРЕНЕРА ---
    def _get_persona_prompt(self, style: str) -> str:
        if style == "tough":
            return (
                "Ты — 'Батя'. Суровый тренер. "
                "Твой стиль: Еда — это топливо. "
                "Смайлы: 👊, 💀, 🦍, 🗿, 💢, 🔨, 🩸. Запрещены: 🔥, 🚀, ❤️. "
                "Пиши коротко, жестко."
            )
        elif style == "scientific":
            return (
                "Ты — 'Доктор'. Биохакер. "
                "Твой стиль: Еда — это химия. Макронутриенты. "
                "Смайлы: 🧠, 🧬, 📈, 🧪, 🩺, ⚖️."
            )
        else: # supportive
            return (
                "Ты — 'Тони'. Друг и мотиватор. "
                "Твой стиль: Еда — это энергия! "
                "Смайлы: 🔥, 🚀, 💪, 🏆, 🎯, 💯."
            )

    # --- 🔥 ГЕНЕРАЦИЯ ПИТАНИЯ (ОБНОВЛЕН СПИСОК ПОКУПОК) 🔥 ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        style = user_data.get("trainer_style", "supportive")
        persona = self._get_persona_prompt(style)
        kcal = self._calculate_target_calories(user_data)
        
        prompt = f"""
        {persona}
        ЗАДАЧА: Создай КОНСТРУКТОР ПИТАНИЯ на день (Ккал: {kcal}).
        Клиент: {user_data.get('weight')}кг, цель: {user_data.get('goal')}.
        
        ТЫ ОБЯЗАН:
        1. ВСТУПЛЕНИЕ ЗАПРЕЩЕНО.
        2. Предложить ПО 3 ВАРИАНТА на каждый прием.
        3. Выделяй названия блюд жирным.
        4. Пиши КБЖУ в скобках.
        
        ФОРМАТ ОТВЕТА (СТРОГО):
        🍳 <b>ЗАВТРАКИ</b>
        1. <b>Блюдо</b> (КБЖУ)
        — Коммент
        
        2. <b>Блюдо</b> (КБЖУ)
        — Коммент
        
        3. <b>Блюдо</b> (КБЖУ)
        — Коммент
        
        🍲 <b>ОБЕДЫ</b>
        (3 варианта)
        
        🥗 <b>УЖИНЫ</b>
        (3 варианта)
        
        🥪 <b>ПЕРЕКУСЫ</b>
        (3 варианта)
        
        🛒 <b>СПИСОК ПОКУПОК (СТРОГО ПО КАТЕГОРИЯМ!)</b>
        🥩 <b>Белки (Мясо/Рыба/Яйца):</b>
        — ...
        — ...
        
        🥦 <b>Овощи и Фрукты:</b>
        — ...
        
        🌾 <b>Крупы и Хлеб:</b>
        — ...
        
        🥛 <b>Молочка и Прочее:</b>
        — ...
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model, temperature=0.7
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception as e: return [f"Ошибка: {e}"]

    # --- ГЕНЕРАЦИЯ ТРЕНИРОВКИ ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        style = user_data.get("trainer_style", "supportive")
        persona = self._get_persona_prompt(style)
        days = user_data.get('workout_days', 3)
        dates = ", ".join(self._calculate_dates(days))
        
        prompt = f"""
        {persona}
        ЗАДАЧА: Программа на {days} дн.
        Клиент: {user_data.get('gender')}, {user_data.get('workout_level')}.
        Даты: {dates}.
        
        ПРАВИЛА:
        1. Без вступления.
        2. Дни начинай с 📅.
        3. Упражнения <b>жирным</b>.
        4. Между упражнениями пустая строка.
        5. Советы в конце с 💡.
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model, temperature=0.7
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception as e: return [f"Ошибка: {e}"]

    # --- ЧАТ ---
    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Err"
        style = user_context.get("trainer_style", "supportive")
        persona = self._get_persona_prompt(style)
        system_msg = {
            "role": "system", 
            "content": f"{persona}\nКлиент: {user_context.get('name')}. Отвечай кратко."
        }
        try:
            msgs = [system_msg] + history[-6:]
            r = await self.client.chat.completions.create(messages=msgs, model=self.model)
            return self._clean_response(r.choices[0].message.content)
        except: return "Ошибка сети"