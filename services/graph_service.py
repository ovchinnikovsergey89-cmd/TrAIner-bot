import matplotlib
# 🔥 ЭТА СТРОКА ОБЯЗАТЕЛЬНА ДЛЯ БОТОВ
# Она говорит: "Рисуй в памяти, не пытайся открыть окно"
matplotlib.use('Agg') 

import matplotlib.pyplot as plt
import matplotlib.dates as mdates  # Добавили для работы с датами
import io
import datetime

class GraphService:
    @staticmethod
    async def create_weight_graph(history_data: list) -> io.BytesIO:
        """
        Рисует график веса.
        history_data: список объектов WeightHistory
        Возвращает буфер с картинкой (PNG).
        """
        if not history_data or len(history_data) < 2:
            return None

        try:
            # 1. Подготовка данных
            dates = [r.date for r in history_data]
            weights = [r.weight for r in history_data]

            # 2. Настройка стиля графика
            plt.figure(figsize=(10, 6))
            plt.style.use('bmh') # Стиль

            # Рисуем линию и точки
            plt.plot(dates, weights, marker='o', linestyle='-', color='#2ecc71', linewidth=2, label='Вес (кг)')
            
            # Добавляем подписи значений (кг) над точками
            for x, y in zip(dates, weights):
                plt.annotate(f"{y}", xy=(x, y), xytext=(0, 5), textcoords="offset points", ha='center', weight='bold')

            # --- НАСТРОЙКА ОСИ ДАТ (ЧТОБЫ БЫЛО ТОЧНО) ---
            ax = plt.gca()
            # Устанавливаем формат даты "День.Месяц" (например, 17.02)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            # Устанавливаем метки так, чтобы они распределялись автоматически, но красиво
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())

            # Поворачиваем даты, чтобы они не слипались
            plt.gcf().autofmt_xdate()

            # Заголовки
            plt.title('Динамика изменения веса', fontsize=16, pad=20)
            plt.xlabel('Дата замера', fontsize=12)
            plt.ylabel('Вес (кг)', fontsize=12)
            plt.grid(True, linestyle='--', alpha=0.6)
            plt.legend()

            # 3. Сохранение в буфер
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            plt.close() # Важно закрыть график, чтобы не копились в памяти
            return buf

        except Exception as e:
            print(f"Ошибка при создании графика: {e}")
            return None