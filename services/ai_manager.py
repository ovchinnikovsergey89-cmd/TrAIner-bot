import io
import os
import logging
import datetime
import re
from datetime import timedelta
import asyncio
from aiogram.enums import ChatAction
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
        Ты — элитный фитнес-тренер бота TrAIner. Проанализируй прогресс клиента {name}.
        ДАННЫЕ: Вес: {old_weight} кг -> {current_weight} кг (Разница: {diff:.1f} кг). Цель: {goal}.
        План тренировок: {plan_days} раз в неделю. Выполнено тренировок: {workouts_count}.
        ТВОЯ ЗАДАЧА: Дай краткий анализ динамики. СТРОГО не используй слово "Вердикт".
        СТРОГИЙ ФОРМАТ ОТВЕТА (HTML):
        1. Первая строка: Эмодзи + краткая суть.
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

    # --- 1.5. МГНОВЕННЫЙ АНАЛИЗ КАТЕГОРИЙ (ТРЕНИРОВКИ / ПИТАНИЕ) ---
    async def analyze_category(self, user_data: dict, category: str, data_text: str) -> str:
        if not self.client: return "❌ Ошибка API: Ключ не настроен"
        
        goal = user_data.get('goal', 'фитнес')
        name = user_data.get('name', 'Атлет')
        weight = user_data.get('weight', 'неизвестен')

        if category == "workouts":
            prompt = (f"Ты элитный фитнес-тренер бота TrAIner. Оцени недавние тренировки клиента {name}.\n"
                      f"Цель: {goal}. Вес: {weight} кг.\n"
                      f"Данные из дневника:\n{data_text}\n\n"
                      f"Дай профессиональный, мотивирующий совет по рабочим весам и частоте. "
                      f"Пиши сразу по делу, структурированно, без общих фраз.")
        else:
            prompt = (f"Ты фитнес-нутрициолог бота TrAIner. Оцени рацион клиента {name} за последние 7 дней.\n"
                      f"Цель: {goal}. Текущий вес: {weight} кг.\n"
                      f"Сводка КБЖУ по дням:\n{data_text}\n\n"
                      f"Дай профессиональный анализ рациона. "
                      f"Пиши сразу по делу, структурированно, укажи на перекосы (если есть).")

        try:
            r = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model, temperature=0.6, timeout=60.0
            )
            return clean_text(r.choices[0].message.content)
        except Exception as e:
            logger.error(f"Category analysis error: {e}")
            return "❌ Тренер временно не может составить отчет из-за нагрузки на сервер. Попробуй позже."

    # --- 2. ГЕНЕРАЦИЯ ТРЕНИРОВКИ ---
    async def generate_workout_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        
        level = user_data.get('workout_level', 'beginner')
        days_per_week = user_data.get('workout_days', 3)
        goal = user_data.get('goal', 'maintenance')
        
        # --- НОВОЕ: ДОСТАЕМ ИСТОРИЮ ---
        past_programs = user_data.get('past_programs', '')
        
        now = datetime.datetime.now()
        weekdays_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        today_name = weekdays_ru[now.weekday()]
        today_date = now.strftime("%d.%m")
        wishes = user_data.get('wishes', 'Нет особых пожеланий.')

        # Базовая анкета
        user_prompt = f"""
        СОСТАВЬ ПЕРСОНАЛЬНЫЙ ПЛАН ТРЕНИРОВОК.
        АНКЕТА КЛИЕНТА: Имя: {user_data.get('name')}, Пол: {user_data.get('gender')}, Возраст: {user_data.get('age')} лет, Вес: {user_data.get('weight')} кг, Рост: {user_data.get('height')} см, Цель: {goal}, Уровень: {level}, График: {days_per_week} тр/нед, Пожелания: {wishes}
        """

        # --- НОВОЕ: БЛОК ПАМЯТИ (ПЕРИОДИЗАЦИЯ) ---
        if past_programs:
            user_prompt += f"""
        ⚠️ ИСТОРИЯ ПРОШЛЫХ ПРОГРАММ:
        {past_programs}
        
        ЗАДАЧА ПО ПЕРИОДИЗАЦИИ:
        Выше представлены программы, по которым клиент занимался в прошлые недели. 
        Твоя задача — составить НОВУЮ программу на следующую неделю. 
        СТРОГО запрещено выдавать точно такую же программу! Примени принцип прогрессивной перегрузки и ротации: измени углы нагрузки (например, замени жим штанги на жим гантелей или тренажер), поменяй порядок упражнений или диапазон повторений, чтобы избежать плато. 
        САМОЕ ГЛАВНОЕ! Учитывай пожелания на сегодня: {wishes}
        """

        # Правила оформления (остались без изменений)
        user_prompt += f"""
        ЛОГИКА ИНДИВИДУАЛЬНОСТИ:
        1. ЗАПРЕЩЕНО вычислять или упоминать ИМТ (индекс массы тела). При объективно большом весе минимизируй прыжки и ударную нагрузку.
        2. Новичок — акцент на нейромышечную связь.
        3. Набор массы — "Прогрессия весов".
        4. 40+ лет — разминка и контроль давления.
        5. Строго придерживайся локации из пожеланий.
        
        ЗАДАЧА: Создай программу на СЕМЬ ДНЕЙ. Ровно {days_per_week} тренировочных дней.
        Начиная с СЕГОДНЯ ({today_name} {today_date}).
        
        СТРОГИЕ ПРАВИЛА ОФОРМЛЕНИЯ:
        1. СРАЗУ начинай с программы по дням. Формат отдыха: 📅 <b>[Дата], День [Номер] ([День недели]) — ВОССТАНОВЛЕНИЕ</b>
        2. После каждого упражнения отступ строки.
        3. Формат упражнения:
        <b>[Номер]. [Название]</b>
        <i>[Сеты] х [Повторы] (Отдых [сек])</i>
        Техника: [Короткий совет]
        4. В дни ВОССТАНОВЛЕНИЯ: 1-2 совета по активности.
        5. В САМОМ КОНЦЕ добавь "💡 Советы тренера" (3-4 пункта).
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

    # --- 3. ГЕНЕРАЦИЯ ПИТАНИЯ (С РЕЖИМОМ РЕДАКТИРОВАНИЯ И ПАМЯТЬЮ!) ---
    async def generate_nutrition_pages(self, user_data: dict) -> list[str]:
        if not self.client: return ["❌ Ошибка API"]
        goal = user_data.get('goal', 'maintenance')
        wishes = user_data.get('wishes', 'Нет особых предпочтений')
        
        # Получаем старый план, если он есть (берем из БД)
        prev_plan = user_data.get('current_nutrition_program', user_data.get('previous_plan', ''))
        
        # --- НОВОЕ: ДОСТАЕМ ИСТОРИЮ ИЗ БД ---
        past_programs = user_data.get('past_programs', '')
        
        # Проверяем, это создание с нуля или запрос на изменение старого меню (длина пожелания > 3 символов)
        is_edit_mode = bool(prev_plan) and len(wishes) > 3 and not any(skip in wishes.lower() for skip in ['пропустить', 'нет особых', 'ем всё', 'ем все'])

        prompt = f"""
        Ты — профессиональный фитнес-диетолог. Твоя задача — составить или скорректировать рацион. 
        
        ДАННЫЕ КЛИЕНТА: 
        - Вес: {user_data.get('weight')} кг, Рост: {user_data.get('height')} см
        - Возраст: {user_data.get('age')} лет, Пол: {user_data.get('gender')}
        - Цель: {goal}
        """

        # Если меню уже было и клиент написал пожелания, заставляем ИИ работать в режиме редактора
        if is_edit_mode:
            prompt += f"""
        ⚠️ У КЛИЕНТА УЖЕ ЕСТЬ СОСТАВЛЕННЫЙ РАЦИОН:
        {prev_plan}
        
        🔥 КЛИЕНТ ПРОСИТ ВНЕСТИ ПРАВКИ В ЭТОТ РАЦИОН: 
        "{wishes}"
        
        ЗАДАЧА:
        Не создавай меню полностью с нуля! Возьми ТЕКУЩИЙ рацион (предоставлен выше) и внеси в него ТОЛЬКО те изменения, о которых просит клиент в своих правках. 
        Например: если клиент просит поменять только обеды — измени варианты обедов, а завтраки, ужины и перекусы оставь точно такими же, как в текущем рационе. Сохраняй структуру.
        """
        else:
            prompt += f"""
        ЗАДАЧА:
        1. Пожелания/Ограничения: {wishes} - Это самое главное что нужно учитывать!
        2. РАССЧИТАЙ суточную норму калорий и диапазоны БЖУ.
        3. Составь меню на день: Завтрак, Обед, Ужин, Перекусы. В каждом блоке по 3 варианта. 
        """
            # --- НОВОЕ: Включаем память только для новых генераций! ---
            if past_programs:
                prompt += f"""
        ⚠️ ИСТОРИЯ ПРОШЛЫХ МЕНЮ КЛИЕНТА:
        {past_programs}
        
        ЗАДАЧА ПО РАЗНООБРАЗИЮ: Выше показаны конструкторы меню, которые клиент использовал ранее. Постарайся предложить НОВЫЕ варианты блюд (другие источники белка, другие гарниры), чтобы меню не повторялось на 100% и клиенту не было скучно, но при этом строго соблюдай его пожелания!
        """

        prompt += """
        СТРОГИЕ ПРАВИЛА ОФОРМЛЕНИЯ (ЧИТАЙ ВНИМАТЕЛЬНО!):
        1. СТРОГО, сразу начинай с заголовка.
        2. При составлении списка продуктов, заголовок: <b>Список покупок:</b>, заместо "*" используй "-", разделяй белки жиры углеводы (используй пример: <b>Белки</b>, <b>Жиры</b>, <b>Углеводы</b> ) делай отступ строки между ними.
        3. ЗАПРЕЩЕНО ставить ===PAGE_BREAK=== между вариантами одного и того же приема пищи! Варианты разделяй просто пустой строкой.
        4. Каждая новая страница (Завтрак, Обед, Ужин, Перекусы) ОБЯЗАТЕЛЬНО начинается с заголовка: 
        <b>Твой КБЖУ ~[Число] ккал (Б: [мин]-[макс], Ж: [мин]-[макс], У: [мин]-[макс])</b>
        5. Каждый ингридиент с новой строки
        ФОРМАТ ВАРИАНТА:
        Вариант X: <b>[Название]</b>
        - [Ингредиенты с весом]
        - <b>КБЖУ: ~[ккал] (Б:..г, Ж:..г, У:..г)</b>
        - Разделяй приемы пищи тегом ===PAGE_BREAK===. В конце добавь Shopping List.
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
        
    # --- 6. БЕЗОПАСНОЕ РАСПОЗНАВАНИЕ ГОЛОСА (ЛОКАЛЬНО В ФОНЕ) ---
    async def transcribe_voice(self, file_data) -> str:
        if not whisper_model:
            return ""
            
        try:
            if isinstance(file_data, str):
                file_path = file_data
                
                def run_transcription():
                    segments, _ = whisper_model.transcribe(
                        file_path, 
                        beam_size=5, 
                        language="ru",
                        initial_prompt="Жим лежа, присед, становая тяга, гантели, штанга, КБЖУ, спагетти, углеводы, калории, повторения.",
                        vad_filter=True, # 🔥 Отрезаем тишину
                        vad_parameters=dict(min_silence_duration_ms=500)
                    )
                    return "".join([segment.text for segment in segments]).strip()

                transcription_text = await asyncio.to_thread(run_transcription)
                return transcription_text
                
            elif isinstance(file_data, io.BytesIO):
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp:
                    tmp.write(file_data.read())
                    tmp_path = tmp.name
                    
                def run_transcription_bytes():
                    segments, _ = whisper_model.transcribe(
                        tmp_path, # Исправлена старая опечатка
                        beam_size=5, 
                        language="ru",
                        initial_prompt="Жим лежа, присед, становая тяга, гантели, штанга, КБЖУ, спагетти, углеводы, калории, повторения.",
                        vad_filter=True, # 🔥 Отрезаем тишину
                        vad_parameters=dict(min_silence_duration_ms=500)
                    )
                    return "".join([segment.text for segment in segments]).strip()
                    
                transcription_text = await asyncio.to_thread(run_transcription_bytes)
                import re
                transcription_text = re.sub(r'(?i)\b\d*\s*подход[а-я]*\b', '', transcription_text)
                os.remove(tmp_path)
                return transcription_text
                
            else:
                return ""
                
        except Exception as e:
            logger.error(f"Ошибка распознавания голоса: {e}")
            return ""