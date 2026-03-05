import io
import os
import logging
import datetime
import re
from datetime import timedelta
import asyncio
from openai import AsyncOpenAI
from config import Config
from utils.text_tools import clean_text

# --- НОВОЕ: ИМПОРТИРУЕМ ЛОКАЛЬНЫЙ WHISPER ---
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# 🔥 ГЛОБАЛЬНАЯ ПЕРЕМЕННАЯ: Загружаем модель ОДИН РАЗ при старте.
# compute_type="int8" сильно снизит нагрузку на процессор и оперативку VDS!
try:
    whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
except Exception as e:
    logger.error(f"Не удалось загрузить Whisper: {e}")
    whisper_model = None

class AIManager:
    """
    Единый менеджер для работы с AI.
    Отвечает за генерацию тренировок, питания, анализ прогресса и распознавание голоса.
    """
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
                logger.error(f"AI Generation Error: {e}")
                self.client = None

    # --- ТЕХНИЧЕСКИЙ МЕТОД: РАЗДЕЛЕНИЕ НА СТРАНИЦЫ ---
    def _smart_split(self, text: str) -> list[str]:
        text = clean_text(text)
        pages = text.split("===PAGE_BREAK===")
        final_pages = [p.strip() for p in pages if len(p.strip()) > 5]
        return final_pages if final_pages else [text]
    
    # --- 1. АНАЛИЗ ПРОГРЕССА ---
    async def analyze_progress(self, user_data: dict, current_weight: float, workouts_count: int = 0) -> str:
        if not self.client: return "Ошибка API: Ключ не настроен"
        
        old_weight = user_data.get('weight', current_weight)
        goal = user_data.get('goal', 'maintenance')
        name = user_data.get('name', 'Атлет')
        plan_days = user_data.get('workout_days', 3)
        diff = current_weight - old_weight
        
        prompt = f"""
        Ты — элитный фитнес-коуч. Проанализируй прогресс клиента {name}.
        ДАННЫЕ: Вес: {old_weight} кг -> {current_weight} кг (Разница: {diff:.1f} кг). Цель: {goal}.
        План тренировок: {plan_days} раз в неделю. Выполнено тренировок: {workouts_count}.
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
                model=self.model, temperature=0.7, timeout=90.0
            )
            return clean_text(r.choices[0].message.content)
        except Exception: 
            return "📈 <b>Данные обновлены!</b>\n\nТренер зафиксировал новый вес и активность."

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
        АНКЕТА КЛИЕНТА: Имя: {user_data.get('name')}, Пол: {user_data.get('gender')}, Возраст: {user_data.get('age')} лет, Вес: {user_data.get('weight')} кг, Рост: {user_data.get('height')} см, Цель: {goal}, Уровень: {level}, График: {days_per_week} тр/нед, Пожелания: {wishes}

        ЛОГИКА ИНДИВИДУАЛЬНОСТИ:
        1. ИМТ > 28 — ЗАПРЕЩЕНЫ прыжки.
        2. Новичок — акцент на нейромышечную связь.
        3. Набор массы — "Прогрессия весов".
        4. 40+ лет — разминка и контроль давления.
        5. Строго придерживайся локации из пожеланий.
        
        ЗАДАЧА: Создай программу на СЕМЬ ДНЕЙ. Ровно {days_per_week} тренировочных дней.
        Начиная с СЕГОДНЯ ({today_name} {today_date}).
        
        СТРОГИЕ ПРАВИЛА ОФОРМЛЕНИЯ:
        1. СРАЗУ начинай с программы по дням. Формат отдыха: 📅 <b>[Дата], День [Номер] ([День недели]) — ВОССТАНОВЛЕНИЕ</b>
        2. Формат упражнения:
        <b>[Номер]. [Название]</b>
        <i>[Сеты] х [Повторы] (Отдых [сек])</i>
        Техника: [Короткий совет]
        3. В дни ВОССТАНОВЛЕНИЯ: 1-2 совета по активности.
        4. В САМОМ КОНЦЕ добавь "💡 Советы тренера" (3-4 пункта).
        Разделяй дни СТРОГО тегом: ===PAGE_BREAK===
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": user_prompt}], 
                model=self.model, temperature=0.3, timeout=90.0
            )
            return self._smart_split(r.choices[0].message.content)
        except Exception:
            return ["❌ Ошибка при составлении программы."]
        
    # --- НОВОЕ: ГЕНЕРАЦИЯ РАЗОВОЙ ТРЕНИРОВКИ ---
    async def generate_single_workout(self, user_data: dict) -> str:
        if not self.client: return "❌ Ошибка API"
        level = user_data.get('workout_level', 'beginner')
        goal = user_data.get('goal', 'maintenance')
        wishes = user_data.get('wishes', 'Стандартная тренировка')

        user_prompt = f"""
        СОСТАВЬ ОДНУ РАЗОВУЮ ТРЕНИРОВКУ.
        АНКЕТА: Имя: {user_data.get('name')}, Вес: {user_data.get('weight')} кг, Цель: {goal}, Уровень: {level}.
        УСЛОВИЯ СЕГОДНЯ: {wishes}

        Формат:
        <b>[Номер]. [Название]</b>
        <i>[Сеты] х [Повторы] (Отдых [сек])</i>
        Техника: [Короткий совет]
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": user_prompt}], 
                model=self.model, temperature=0.5, timeout=60.0
            )
            return r.choices[0].message.content
        except Exception:
            return "❌ Ошибка при составлении тренировки."    

    # --- 3. ГЕНЕРАЦИЯ ПИТАНИЯ ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        goal = user_data.get('goal', 'maintenance')
        wishes = user_data.get('wishes', 'Нет особых предпочтений')
        
        prompt = f"""
        Ты — фитнес-диетолог. Составь рацион. 
        ДАННЫЕ: Вес: {user_data.get('weight')} кг, Рост: {user_data.get('height')} см, Цель: {goal}, Пожелания: {wishes}
        
        ЗАДАЧА:
        1. РАССЧИТАЙ КБЖУ.
        2. Меню на день: Завтрак, Обед, Ужин, Перекусы. По 3 варианта.

        СТРОЖАЙШЕЕ ПРАВИЛО:
        Каждая страница начинается с: <b>Твой КБЖУ ~[Число] ккал (Б: [мин]-[макс], Ж: [мин]-[макс], У: [мин]-[макс])</b>
        
        ФОРМАТ ВАРИАНТА:
        Вариант X: <b>[Название]</b>
        - [Ингредиенты с весом]
        - <b>КБЖУ: ~[ккал] (Б:..г, Ж:..г, У:..г)</b>
        Разделяй приемы пищи тегом ===PAGE_BREAK===. В конце добавь Shopping List.
        """
        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], 
                model=self.model, temperature=0.4, timeout=90.0
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

            if gender == 'male': bmr = 10 * w + 6.25 * h - 5 * a + 5
            else: bmr = 10 * w + 6.25 * h - 5 * a - 161
            
            target = int(bmr * 1.375)
            if goal == 'weight_loss': target -= 400
            elif goal == 'muscle_gain': target += 300
            elif goal == 'recomposition': target -= 150
            return max(target, 1200) 
        except Exception: 
            return 2000

    # --- 5. ЧАТ С ТРЕНЕРОМ ---
    async def get_chat_response(self, history: list, user_context: dict) -> str:
        if not self.client: return "Ошибка: API не настроен"
        
        name = user_context.get('name', 'атлет')
        goal = user_context.get('goal', 'фитнес')
        
        system_prompt = (
            f"Ты — тренер TrAIner. Твой клиент: {name}, цель: {goal}. "
            "Отвечай на ВСЕ вопросы. Пиши простым текстом без звездочек."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}] + history[-6:],
                temperature=0.7, timeout=30.0
            )
            result = response.choices[0].message.content
            if not result: return "Я тут, готов к работе!"
            return result.replace("*", "").replace("#", "")
        except Exception as e:
            logger.error(f"DeepSeek Error: {e}")
            return f"❌ Ошибка связи с ИИ. Попробуй еще раз."
        
    # --- 6. НОВОЕ: БЕЗОПАСНОЕ РАСПОЗНАВАНИЕ ГОЛОСА (ЛОКАЛЬНО В ФОНЕ) ---
    async def transcribe_voice(self, file_data) -> str:
        """
        Берет аудиофайл, запускает Whisper в фоновом потоке (чтобы не блокировать бота),
        и возвращает текст. Блокировок по IP больше не боимся!
        """
        if not whisper_model:
            return ""
            
        try:
            if isinstance(file_data, str):
                file_path = file_data
                
                # 🔥 МАГИЯ: Запускаем тяжелую нейросеть в ОТДЕЛЬНОМ потоке
                def run_transcription():
                    segments, _ = whisper_model.transcribe(file_path, beam_size=5, language="ru")
                    return "".join([segment.text for segment in segments]).strip()

                transcription_text = await asyncio.to_thread(run_transcription)
                return transcription_text
                
            # Защита на случай, если какой-то хендлер всё ещё передает байты
            elif isinstance(file_data, io.BytesIO):
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp:
                    tmp.write(file_data.read())
                    tmp_path = tmp.name
                    
                def run_transcription_bytes():
                    segments, _ = whisper_model.transcribe(tmp_path, beam_size=5, language="ru")
                    return "".join([segment.text for segment in segments]).strip()
                    
                transcription_text = await asyncio.to_thread(run_transcription_bytes)
                os.remove(tmp_path)
                return transcription_text
                
            else:
                return ""
                
        except Exception as e:
            logger.error(f"Ошибка распознавания голоса: {e}")
            return ""