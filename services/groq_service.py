import logging
import datetime
import re
from datetime import timedelta
from openai import AsyncOpenAI
from config import Config

class GroqService:
    def __init__(self):
        self.api_key = Config.DEEPSEEK_API_KEY # Или GROQ_API_KEY
        self.client = None
        self.model = "deepseek-chat" # Или 'llama3-70b-8192' если через Groq
        
        if self.api_key:
            try:
                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url="https://api.deepseek.com" # Или "https://api.groq.com/openai/v1"
                )
            except Exception as e:
                logging.error(f"Err: {e}")

    # --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (Остаются без изменений) ---
    def _calculate_target_calories(self, user_data: dict) -> int:
        # (Код расчета калорий оставь прежним, он хороший)
        try:
            w = float(user_data.get('weight', 70))
            h = float(user_data.get('height', 170))
            a = int(user_data.get('age', 30))
            g = user_data.get('gender', 'male')
            act = user_data.get('activity_level', 'medium')
            goal = user_data.get('goal', 'maintenance')
            
            # BMR Mifflin-St Jeor
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
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL) # Удаляем мысли Deepseek
        text = re.sub(r'^```html', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```', '', text, flags=re.MULTILINE)
        return text.strip()

    def _smart_split(self, text: str) -> list[str]:
        text = self._clean_response(text)
        pages = re.split(r'(?=\n(?:🍳|🍲|🥗|🛒|📅|💡))', text)
        if len(pages) < 2: pages = re.split(r'(?=🍳|🍲|🥗|🛒|📅|💡)', text)
        return [p.strip() for p in pages if len(p.strip()) > 20] or [text]

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

    # --- 🔥 ПОЛУЧЕНИЕ ЛИЧНОСТИ ТРЕНЕРА 🔥 ---
    def _get_persona_prompt(self, style: str) -> str:
        if style == "tough":
            return (
                "Ты — 'Сержант'. ЖЕСТКИЙ тренер старой закалки. "
                "Ты не терпишь нытья. Обращайся на 'ты', говори коротко и по делу. "
                "Используй сленг качалки. Если клиент ленится — ругай его. "
                "Твоя цель — дисциплина. Никаких 'пожалуйста' и нежностей."
            )
        elif style == "scientific":
            return (
                "Ты — 'Доктор Наук'. Интеллектуальный тренер-биохакер. "
                "Ты опираешься только на факты, исследования и биомеханику. "
                "Твой тон вежливый, сдержанный, немного занудный. "
                "Используй термины (гипертрофия, профицит, кортизол). "
                "Обращайся на 'Вы'."
            )
        else: # supportive (default)
            return (
                "Ты — 'Тони', лучший друг и мотиватор. "
                "Ты очень позитивный, энергичный и добрый. "
                "Используй много эмодзи (🔥, 🚀, 💪). "
                "Твоя цель — вдохновить и поддержать. Обращайся на 'ты', по-дружески."
            )

    # --- ГЕНЕРАЦИЯ ПИТАНИЯ (С УЧЕТОМ ЛИЧНОСТИ) ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        style = user_data.get("trainer_style", "supportive")
        persona = self._get_persona_prompt(style)
        kcal = self._calculate_target_calories(user_data)
        
        prompt = f"""
        {persona}
        ЗАДАЧА: Составь меню на день.
        Клиент: {user_data.get('weight')}кг, цель: {user_data.get('goal')}. Калории: {kcal}.
        
        ФОРМАТ ОТВЕТА (СТРОГО):
        🍳 <b>ЗАВТРАКИ</b> (текст...)
        🍲 <b>ОБЕДЫ</b> (текст...)
        🥗 <b>УЖИНЫ</b> (текст...)
        🛒 <b>СПИСОК ПОКУПОК</b> (текст...)
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model
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
        ЗАДАЧА: Напиши программу тренировок на неделю ({days} дн).
        Клиент: {user_data.get('gender')}, {user_data.get('workout_level')}. Цель: {user_data.get('goal')}.
        Даты: {dates}.
        
        ФОРМАТ:
        Каждый день начинай со смайла 📅.
        В конце добавь блок "Советы" со смайлом 💡.
        Используй свой стиль общения в описании упражнений!
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception as e: return [f"Ошибка: {e}"]

    # --- АНАЛИЗ ПРОГРЕССА ---
    async def analyze_progress(self, user_data: dict, current_weight: float) -> str:
        if not self.client: return "Err"
        
        style = user_data.get("trainer_style", "supportive")
        persona = self._get_persona_prompt(style)
        
        prompt = f"""
        {persona}
        СИТУАЦИЯ: Клиент весил {user_data.get('weight')}кг, стал {current_weight}кг.
        Цель: {user_data.get('goal')}.
        Дай краткий комментарий и совет (максимум 3 предложения) в своем стиле.
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model
            )
            return self._clean_response(r.choices[0].message.content)
        except: return "Ошибка анализа"

    # --- ЧАТ (ВОПРОС-ОТВЕТ) ---
    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Err"
        
        style = user_context.get("trainer_style", "supportive")
        persona = self._get_persona_prompt(style)
        
        # Добавляем контекст о пользователе в системный промпт
        system_msg = {
            "role": "system", 
            "content": (
                f"{persona}\n"
                f"ТВОЙ КЛИЕНТ: {user_context.get('name', 'друг')}, {user_context.get('weight')}кг, "
                f"цель: {user_context.get('goal')}. "
                "Отвечай кратко, емко, не используй Markdown заголовки (###)."
            )
        }
        
        try:
            # Берем последние 6 сообщений, чтобы помнить контекст беседы
            msgs = [system_msg] + history[-6:]
            r = await self.client.chat.completions.create(messages=msgs, model=self.model)
            return self._clean_response(r.choices[0].message.content)
        except: return "Ошибка сети"