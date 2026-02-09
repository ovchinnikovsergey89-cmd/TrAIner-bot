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
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'^```html', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```', '', text, flags=re.MULTILINE)
        return text.strip()

    def _smart_split(self, text: str) -> list[str]:
        text = self._clean_response(text)
        # Разбиваем по дням (смайлик календаря)
        pages = re.split(r'(?=\n(?:📅))', text)
        if len(pages) < 2: pages = re.split(r'(?=📅)', text)
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

    # --- 🔥 ЛИЧНОСТИ ТРЕНЕРОВ (ОБНОВЛЕНО) 🔥 ---
    def _get_persona_prompt(self, style: str) -> str:
        print(f"DEBUG: Генерация в стиле '{style}'")
        
        if style == "tough": # Батя
            emojis = "👊 💀 🦍 🗿 💢 🔨 🩸🔩💥☠️"
            return (
                f"Ты — 'Батя'. ЖЕСТКИЙ тренер старой школы. "
                f"Твои фирменные смайлы: {emojis}. Вставляй их часто! "
                "Ты не терпишь нытья. Говори коротко, грубо и по делу. "
                "Используй сленг качалки."
            )
        elif style == "scientific": # Доктор
            emojis = "🧠 🧬 📈 🧪 🩺 ⚖️ 🔬💡📊"
            return (
                f"Ты — 'Доктор Наук'. Интеллектуальный тренер-биохакер. "
                f"Твои фирменные смайлы: {emojis}. Вставляй их часто! "
                "Ты опираешься на факты и биомеханику. Тон вежливый, но занудный."
            )
        else: # supportive (Тони)
            emojis = "🔥 🚀 💪 🏆 🎯 💯😎⚡🔝🥇"
            return (
                f"Ты — 'Тони', лучший друг и мотиватор. "
                f"Твои фирменные смайлы: {emojis}. Вставляй их часто! "
                "Ты максимально позитивный и энергичный."
            )

    # --- ГЕНЕРАЦИЯ ПИТАНИЯ ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        style = user_data.get("trainer_style") or "supportive"
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
            text = self._clean_response(r.choices[0].message.content)
            pages = re.split(r'(?=\n(?:🍳|🍲|🥗|🛒))', text)
            if len(pages) < 2: pages = [text]
            return [p.strip() for p in pages if len(p.strip()) > 20]
        except Exception as e: return [f"Ошибка: {e}"]

    # --- ГЕНЕРАЦИЯ ТРЕНИРОВКИ (ИСПРАВЛЕНЫ ЖИРНЫЙ ШРИФТ И СОВЕТЫ) ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        style = user_data.get("trainer_style") or "supportive"
        persona = self._get_persona_prompt(style)
        days = user_data.get('workout_days', 3)
        dates = ", ".join(self._calculate_dates(days))
        
        prompt = f"""
        {persona}
        ЗАДАЧА: Напиши программу тренировок на неделю ({days} дн).
        Клиент: {user_data.get('gender')}, {user_data.get('workout_level')}. Цель: {user_data.get('goal')}.
        Даты: {dates}.
        
        ФОРМАТ СТРОГО:
        1. Каждый день начинай с заголовка: 📅 ДАТА (День недели).
        2. НАЗВАНИЯ УПРАЖНЕНИЙ выделяй жирным шрифтом (оборачивай в **звездочки**). Пример: **Жим лежа**
        3. Рядом с каждым названием ставь свой фирменный смайл.
        4. Каждое упражнение пиши с новой строки.
        5. МЕЖДУ УПРАЖНЕНИЯМИ ОБЯЗАТЕЛЬНО ДЕЛАЙ ПУСТУЮ СТРОКУ! (Double line break).
        6. НЕ ПИШИ "Советы" или "Итоги" в конце дня. Только упражнения.
        
        Пример:
        📅 10 фев (Пн)
        
        **Жим лежа** (смайл): 3x12
        (описание)
        
        **Приседания** (смайл): 4x10
        (описание)
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception as e: return [f"Ошибка: {e}"]

    # --- ЧАТ И АНАЛИЗ ---
    async def analyze_progress(self, user_data: dict, current_weight: float) -> str:
        if not self.client: return "Err"
        style = user_data.get("trainer_style") or "supportive"
        persona = self._get_persona_prompt(style)
        prompt = f"{persona}\nКлиент весил {user_data.get('weight')}кг, стал {current_weight}кг. Цель: {user_data.get('goal')}. Дай комментарий (макс 3 предл)."
        try:
            r = await self.client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model=self.model)
            return self._clean_response(r.choices[0].message.content)
        except: return "Ошибка анализа"

    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Err"
        style = user_context.get("trainer_style") or "supportive"
        persona = self._get_persona_prompt(style)
        system_msg = {"role": "system", "content": f"{persona}\nТВОЙ КЛИЕНТ: {user_context.get('name')}, {user_context.get('weight')}кг. Отвечай кратко."}
        try:
            msgs = [system_msg] + history[-6:]
            r = await self.client.chat.completions.create(messages=msgs, model=self.model)
            return self._clean_response(r.choices[0].message.content)
        except: return "Ошибка сети"