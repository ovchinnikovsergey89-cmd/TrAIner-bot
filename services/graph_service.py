import matplotlib
# 🔥 ЭТА СТРОКА ОБЯЗАТЕЛЬНА ДЛЯ БОТОВ
# Она говорит: "Рисуй в памяти, не пытайся открыть окно"
matplotlib.use('Agg') 

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import datetime
from collections import Counter # Добавили для подсчета тренировок по дням

class GraphService:
    @staticmethod
    async def create_combined_dashboard(weight_data: list, workout_data: list) -> io.BytesIO:
        """
        Рисует двойной дашборд: график веса (сверху) и гистограмму тренировок (снизу).
        weight_data: список объектов WeightHistory
        workout_data: список объектов WorkoutLog
        Возвращает буфер с картинкой (PNG).
        """
        if not weight_data and not workout_data:
            return None

        try:
            # Настройка стиля (светлая и приятная тема)
            plt.style.use('bmh')
            
            # Создаем окно с двумя графиками друг под другом (2 строки, 1 колонка)
            # gridspec_kw задает пропорции: верхний график (вес) будет чуть больше нижнего
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 9), gridspec_kw={'height_ratios': [2, 1.2]})
            fig.tight_layout(pad=5.0) # Отступы между графиками

            # ==========================================
            # 1. ВЕРХНИЙ ГРАФИК: ВЕС (Линия)
            # ==========================================
            if weight_data and len(weight_data) >= 2:
                w_dates = [r.date for r in weight_data]
                weights = [r.weight for r in weight_data]

                ax1.plot(w_dates, weights, marker='o', linestyle='-', color='#2ecc71', linewidth=2, label='Вес (кг)')
                
                # Подписи точных значений над точками
                for x, y in zip(w_dates, weights):
                    ax1.annotate(f"{y}", xy=(x, y), xytext=(0, 5), textcoords="offset points", ha='center', weight='bold')

                ax1.set_title('📉 Динамика изменения веса', fontsize=14, pad=10, weight='bold')
                ax1.set_ylabel('Вес (кг)', fontsize=12)
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
                ax1.grid(True, linestyle='--', alpha=0.6)
                ax1.legend()
            else:
                # Заглушка, если замеров веса пока не хватает
                ax1.text(0.5, 0.5, "Недостаточно данных о весе\n(нужно минимум 2 замера)", 
                         ha='center', va='center', fontsize=12, color='gray')
                ax1.set_title('📉 Динамика изменения веса', fontsize=14, pad=10, weight='bold')
                ax1.set_xticks([])
                ax1.set_yticks([])

            # ==========================================
            # 2. НИЖНИЙ ГРАФИК: ТРЕНИРОВКИ (Столбцы)
            # ==========================================
            if workout_data:
                # Берем только дату без времени, чтобы сгруппировать тренировки по дням
                wk_dates = [r.date.date() for r in workout_data]
                wk_counts = Counter(wk_dates) # Считаем: {дата: кол-во тренировок}
                
                bar_dates = list(wk_counts.keys())
                bar_counts = list(wk_counts.values())

                # Рисуем стильные столбцы
                ax2.bar(bar_dates, bar_counts, color='#3498db', alpha=0.8, width=0.4)
                
                # Настройка осей
                ax2.set_title('💪 Выполненные тренировки', fontsize=14, pad=10, weight='bold')
                ax2.set_ylabel('Кол-во', fontsize=12)
                
                # Делаем шкалу Y целыми числами (1, 2, 3...)
                max_count = max(bar_counts) if bar_counts else 1
                ax2.set_yticks(range(0, max_count + 2))
                
                ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
                ax2.grid(True, linestyle='--', alpha=0.6, axis='y') # Оставляем только горизонтальную сетку
            else:
                # Заглушка, если тренировок еще нет
                ax2.text(0.5, 0.5, "Пока нет выполненных тренировок", 
                         ha='center', va='center', fontsize=12, color='gray')
                ax2.set_title('💪 Выполненные тренировки', fontsize=14, pad=10, weight='bold')
                ax2.set_xticks([])
                ax2.set_yticks([])

            # Поворачиваем даты по оси X на обоих графиках, чтобы они не слипались
            fig.autofmt_xdate()

            fig.text(0.98, 0.02, 'Создано в TrAIner bot', 
                     ha='right', va='bottom', fontsize=10, color='gray', alpha=0.6, weight='bold')

            # ==========================================
            # 3. Сохранение картинки
            # ==========================================
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=150) # dpi=150 для хорошего качества в Телеграме
            buf.seek(0)
            plt.close(fig) # Закрываем именно эту фигуру (fig), чтобы не забивать память сервера
            return buf

        except Exception as e:
            print(f"Ошибка при создании дашборда: {e}")
            return None