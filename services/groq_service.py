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
        
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'```html', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```', '', text)
        
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'__(.*?)__', r'<i>\1</i>', text)
        
        # Удаляем запрещенные теги
        for tag in ['div', 'p', 'span', 'html', 'body', 'header', 'footer', 'ul', 'li', 'ol']:
            text = re.sub(f'</?{tag}.*?>', '', text, flags=re.IGNORECASE)
            
        return text.strip()

    def _smart_split(self, text: str) -> list[str]:
        text = self._clean_response(text)
        pages = text.split("===PAGE_BREAK===")
        clean_pages = [p.strip() for p in pages if len(p.strip()) > 10]
        if not clean_pages: return [text]
        return clean_pages

    # --- УМНЫЙ КАЛЕНДАРЬ (ИСПРАВЛЕНО) ---
    def _get_dates_list(self, days_count: int) -> list[str]:
        """
        Генерирует логичные даты тренировок в зависимости от частоты.
        """
        today = datetime.date.today()
        dates = []
        months = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
        weekdays = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
        
        # Логика смещений (offsets) от сегодняшнего дня
        if days_count == 2:
            # Например: Сегодня и через 3 дня (Пн, Чт)
            offsets = [0, 3]
        elif days_count == 3:
            # Классика через день: Сегодня, +2, +4 (Пн, Ср, Пт)
            offsets = [0, 2, 4]
        elif days_count == 4:
            # Сплит: 2 дня work, 1 отдых, 2 work (Пн, Вт, Чт, Пт)
            offsets = [0, 1, 3, 4]
        elif days_count == 5:
            # Будни: 3 work, 1 отдых, 2 work
            offsets = [0, 1, 2, 4, 5]
        elif days_count == 6:
            offsets = [0, 1, 2, 3, 4, 5]
        else:
            offsets = range(days_count) # 1 или 7+ дней - подряд

        for i in offsets:
            date = today + timedelta(days=i)
            # Формат: 10 фев (Вт)
            d_str = f"{date.day} {months[date.month-1]} ({weekdays[date.weekday()]})"
            dates.append(d_str)
            
        return dates

    # --- АНАЛИЗ ПРОГРЕССА ---
    async def analyze_progress(self, user_data: dict, current_weight: float) -> str:
        if not self.client: return "Ошибка API"
        old_weight = user_data.get('weight', current_weight)
        goal = user_data.get('goal', 'Форма')
        
        prompt = f"""
        Проанализируй вес: {old_weight} -> {current_weight} (Цель: {goal}).
        Дай развернутый ответ (10-12 предложений).
        Используй HTML (<b>, <i>). Не используй Markdown (**).
        Структура: Оценка, Причины, План (3 пункта).
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model, temperature=0.7, timeout=50
            )
            return self._clean_response(r.choices[0].message.content)
        except Exception as e:
            return "Результат зафиксирован."

    # --- ГЕНЕРАЦИЯ ТРЕНИРОВКИ (ИНДИВИДУАЛЬНАЯ) ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        level = user_data.get('workout_level', 'Новичок')
        days = int(user_data.get('workout_days', 3))
        goal = user_data.get('goal', 'Форма')
        gender = user_data.get('gender', '—')
        age = user_data.get('age', '—')
        weight = user_data.get('weight', '—')
        
        # Получаем умные даты
        dates_list = self._get_dates_list(days)
        
        # Подсказываем ИИ тип сплита
        split_type = "Full Body (на все тело)"
        if days == 4: split_type = "Верх / Низ (2 дня верх, 2 дня низ)"
        elif days >= 5: split_type = "Сплит по группам мышц (Bro-split или PPL)"

        system_prompt = "Ты — персональный тренер. Пиши программу СТРОГО используя HTML теги <b> и <i>. Делай пустые строки между упражнениями."

        user_prompt = f"""
        СОСТАВЬ ИНДИВИДУАЛЬНУЮ ПРОГРАММУ.
        
        👤 **КЛИЕНТ**:
        - Пол: {gender}
        - Возраст: {age} лет
        - Вес: {weight} кг
        - Уровень: {level}
        - Цель: {goal}
        
        📅 **ГРАФИК**: {days} дней в неделю.
        🗓 **ДАТЫ ТРЕНИРОВОК (Используй их как заголовки!)**:
        {", ".join(dates_list)}

        🛠 **ЗАДАЧА**:
        1. Используй систему: {split_type}.
        2. Подбери нагрузку именно под цель "{goal}" для человека весом {weight}кг.
        3. Если цель "Похудение" — добавь интенсивность. Если "Масса" — объем.
        
        ТРЕБОВАНИЯ К ОФОРМЛЕНИЮ (СТРОГО):
        1. Раздели дни разделителем ===PAGE_BREAK===.
        2. Всего {days} страниц с тренировками + 1 страница с рекомендациями.
        3. Между упражнениями ОБЯЗАТЕЛЬНО пустая строка.
        4. Не используй Markdown (**), только HTML (<b>, <i>).

        ШАБЛОН ДНЯ:
        📅 <b>[Дата из списка] — [Мышечная группа]</b>
        
        1. <b>[Упражнение]</b>
        <i>[Подходы] x [Повторения]</i>
        Техника: [Очень кратко]
        
        (ПУСТАЯ СТРОКА)

        2. <b>[Упражнение]</b>
        ...
        
        🧘 <b>Заминка</b>: [Текст]

        ШАБЛОН РЕКОМЕНДАЦИЙ (ПОСЛЕДНЯЯ СТРАНИЦА):
        ===PAGE_BREAK===
        🎓 <b>Рекомендации тренера для тебя</b>
        
        1. <b>Стратегия тренировок ({split_type})</b>
        [Почему мы выбрали этот сплит и как по нему заниматься]
        
        (ПУСТАЯ СТРОКА)

        2. <b>Кардио и активность</b>
        [Сколько кардио нужно именно для цели "{goal}"]

        (ПУСТАЯ СТРОКА)
        
        3. <b>Восстановление</b>
        [Советы по сну и отдыху]
        """
        
        try:
            r = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ], 
                model=self.model, 
                temperature=0.4,
                timeout=70
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception as e:
            logging.error(f"Workout gen error: {e}")
            return ["❌ Ошибка генерации."]

    # --- ГЕНЕРАЦИЯ ПИТАНИЯ (Меню-конструктор) ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        kcal = self._calculate_target_calories(user_data)
        goal = user_data.get('goal', 'Здоровье')
        gender = user_data.get('gender', '—')
        weight = user_data.get('weight', '—')
        
        prompt = f"""
        Составь МЕНЮ-КОНСТРУКТОР на ~{kcal} ккал.
        
        👤 Клиент: {gender}, Вес: {weight} кг. Цель: {goal}.
        
        СТРУКТУРА ОТВЕТА (Разделитель ===PAGE_BREAK===):
        
        Стр 1: 3 варианта ЗАВТРАКА.
        ===PAGE_BREAK===
        Стр 2: 3 варианта ОБЕДА.
        ===PAGE_BREAK===
        Стр 3: 3 варианта УЖИНА.
        ===PAGE_BREAK===
        Стр 4: 3 варианта ПЕРЕКУСОВ.
        ===PAGE_BREAK===
        Стр 5: Список продуктов.

        ТРЕБОВАНИЯ:
        1. Между вариантами ПУСТАЯ СТРОКА.
        2. HTML теги <b> и <i>.
        3. Разнообразное меню.

        ПРИМЕР:
        🍳 <b>ВАРИАНТЫ ЗАВТРАКА</b> (~Ккал)
        
        1. <b>[Блюдо]</b>
        <i>Состав: ...</i>
        (КБЖУ: ...)
        
        (ПУСТАЯ СТРОКА)

        2. <b>[Блюдо]</b>
        ...
        """
        
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], 
                model=self.model, 
                temperature=0.5,
                timeout=60
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception as e: 
            return [f"Ошибка генерации питания: {e}"]

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
            
            target = int(bmr * 1.375)
            goal = user_data.get('goal', '').lower()
            
            if 'похуд' in goal or 'сброс' in goal or 'сушк' in goal:
                target -= 300
            elif 'набор' in goal or 'масс' in goal:
                target += 300
                
            return target
        except:
            return 2000

    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Ошибка конфигурации API"
        try:
            msgs = [{"role": "system", "content": "Ты тренер. Отвечай кратко."}] + history[-5:]
            r = await self.client.chat.completions.create(messages=msgs, model=self.model)
            return self._clean_response(r.choices[0].message.content)
        except: return "Ошибка сети"