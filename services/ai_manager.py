import logging
import datetime
import re
from datetime import timedelta
from openai import AsyncOpenAI
from config import Config
from utils.text_tools import clean_text

logger = logging.getLogger(__name__)

class AIManager:
    """
    Единый менеджер для работы с AI (DeepSeek).
    Отвечает за генерацию тренировок, питания и анализ прогресса.
    """
    def __init__(self):
        self.api_key = Config.DEEPSEEK_API_KEY
        self.client = None
        self.model = "deepseek-chat"
        
        if self.api_key:
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url="https://api.deepseek.com"
                )
            except Exception as e:
                import logging
                logging.error(f"AI Init Error: {e}")

    # --- 1. АНАЛИЗ ПРОГРЕССА ---
    # ВАЖНО: Добавлен аргумент workouts_count=0
    async def analyze_progress(self, user_data: dict, current_weight: float, workouts_count: int = 0) -> str:
        if not self.client: return "Ошибка API: Ключ не настроен"
        
        old_weight = user_data.get('weight', current_weight)
        goal = user_data.get('goal', 'maintenance')
        name = user_data.get('name', 'Атлет')
        plan_days = user_data.get('workout_days', 3)
        diff = current_weight - old_weight
        
        prompt = f"""
        Ты — элитный фитнес-коуч. Проанализируй прогресс клиента {name}.
        
        ДАННЫЕ:
        - Вес: {old_weight} кг -> {current_weight} кг (Разница: {diff:.1f} кг). 
        - Цель: {goal}.
        - План тренировок: {plan_days} раз в неделю.
        - Выполнено тренировок: {workouts_count}.

        ТВОЯ ЗАДАЧА: Дай краткий анализ динамики.
        
        СТРОГИЙ ФОРМАТ ОТВЕТА (HTML):
        1. Первая строка: Эмодзи + вердикт.
        2. Вторая строка: ОБЯЗАТЕЛЬНО ПУСТАЯ СТРОКА.
        3. Третья строка: <b>Анализ:</b> (Свяжи вес и активность).
        4. Четвертая строка: <b>Рекомендация:</b> (Один совет).
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model, temperature=0.7
            )
            from utils.text_tools import clean_text
            return clean_text(r.choices[0].message.content)
        except Exception: 
            return "📈 <b>Данные обновлены!</b>\n\nТренер зафиксировал новый вес и активность."

    # ... (остальные методы: generate_workout_pages и т.д.)

    # --- 2. ГЕНЕРАЦИЯ ТРЕНИРОВКИ ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        level = user_data.get('workout_level', 'beginner')
        days_per_week = user_data.get('workout_days', 3)
        goal = user_data.get('goal', 'maintenance')
        
        now = datetime.datetime.now()
        weekdays_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        today_name = weekdays_ru[now.weekday()]
        today_date = now.strftime("%d.%m")
        wishes = user_data.get('wishes', 'Нет особых пожеланий.')

        user_prompt = f"""
        СОСТАВЬ ПЕРСОНАЛЬНЫЙ ПЛАН ТРЕНИРОВОК.
        
        АНКЕТА КЛИЕНТА:
        - Имя: {user_data.get('name')}
        - Пол: {user_data.get('gender')}
        - Возраст: {user_data.get('age')} лет
        - Вес: {user_data.get('weight')} кг
        - Рост: {user_data.get('height')} см
        - Цель: {goal}
        - Уровень подготовки: {level}
        - График: {days_per_week} тренировок в неделю
        - Пожелания: {user_data.get('wishes')}

        ЗАДАЧА: Создай программу, которая строго учитывает физические данные из анкеты (ИМТ, возраст), но при этом адаптирована под текущее пожелание (например, акцент на конкретную группу мышц или изменение интенсивности).
        Распредели тренировки, начиная с СЕГОДНЯ ({today_name} {today_date}). 
        
        СТРОГИЕ ПРАВИЛА ОФОРМЛЕНИЯ:
        1. СРАЗУ начинай с программы тренировок по дням.
        2. Название дня: 📅 <b>[День недели], [Дата] — [Тип тренировки]</b>.
        3. Между упражнениями ОБЯЗАТЕЛЬНО ПУСТАЯ СТРОКА.
        4. ЗАПРЕЩЕНО писать вступление, анализ ИМТ, расчеты калорий или принципы плана в самом начале.
        5. СРАЗУ начинай с программы тренировок по дням.
        6. Формат упражнения:
        <b>[Номер]. [Название]</b>
        <i>[Сеты] х [Повторы] (Отдых [сек])</i>
        Техника: [Короткий совет]
        7. В САМОМ КОНЦЕ (на последней странице после всех дней) добавь блок "💡 Советы тренера".
        8. В советах ОЧЕНЬ КРАТКО (3-4 пункта) укажи рекомендации по питанию и технике, основываясь на данных клиента.
        
        Разделяй дни СТРОГО тегом: ===PAGE_BREAK===
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": user_prompt}], 
                model=self.model, temperature=0.3
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception:
            return ["❌ Ошибка при составлении программы."]

    # --- 3. ГЕНЕРАЦИЯ ПИТАНИЯ (3 ВАРИАНТА + ПЕРЕКУСЫ + СПИСОК) ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        kcal = self._calculate_target_calories(user_data)
        goal = user_data.get('goal', 'maintenance')
        
        prompt = f"""
        Ты — профессиональный диетолог. Составь подробный рацион питания на {kcal} ккал. 
        Цель клиента: {goal}.
        
        ТРЕБОВАНИЯ К КОНТЕНТУ:
        1. Для КАЖДОГО блока (Завтрак, Обед, Ужин, Перекусы) предоставь ровно 3 РАЗНЫХ варианта на выбор.
        2. Указывай точные ингредиенты в граммах и КБЖУ для каждого варианта.
        3. В конце добавь расширенный список продуктов на неделю (Shopping List).
        
        СТРОГИЕ ПРАВИЛА ОФОРМЛЕНИЯ:
        1. Между вариантами блюд (включая ПЕРЕКУСЫ) ОБЯЗАТЕЛЬНО делай ПУСТУЮ СТРОКУ для читабельности.
        2. Используй HTML (<b>, <i>). Без вступлений.
        3. Разделяй блоки (Завтрак, Обед, Ужин, Перекусы, Список покупок) СТРОГО тегом: ===PAGE_BREAK===
        
        ФОРМАТ ВАРИАНТА:
        Вариант X: <b>[Название]</b>
        * [Ингредиенты с весом]
        * <b>КБЖУ: ~[ккал] (Б:..г, Ж:..г, У:..г)</b>
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], 
                model=self.model, temperature=0.4
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception:
            return ["❌ Ошибка генерации рациона."]

    # --- 4. РАСЧЕТ КАЛОРИЙ ---
    def _calculate_target_calories(self, user_data: dict) -> int:
        try:
            w = float(user_data.get('weight', 70))
            h = float(user_data.get('height', 170))
            a = int(user_data.get('age', 30))
            gender = user_data.get('gender', 'male')
            goal = user_data.get('goal', 'maintenance')

            if gender == 'male':
                bmr = 10 * w + 6.25 * h - 5 * a + 5
            else:
                bmr = 10 * w + 6.25 * h - 5 * a - 161
            
            target = int(bmr * 1.375)

            if goal == 'weight_loss': target -= 400
            elif goal == 'muscle_gain': target += 300
            elif goal == 'recomposition': target -= 150
            
            return max(target, 1200) 
        except Exception: 
            return 2000

    # --- 5. ЧАТ С ТРЕНЕРОМ ---
    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Ошибка API"
        name = user_context.get('name', 'атлет')
        goal = user_context.get('goal', 'здоровье')
        system = f"Ты тренер TrAIner. Твой подопечный: {name}. Цель: {goal}. Отвечай кратко и профессионально."
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "system", "content": system}] + history[-6:], 
                model=self.model
            )
            return clean_text(r.choices[0].message.content)
        except Exception: 
            return "Связь прервалась."