import matplotlib.pyplot as plt
import io
import datetime

class GraphService:
    @staticmethod
    async def create_weight_graph(history_data: list) -> bytes:
        """
        Рисует график веса.
        history_data: список объектов WeightHistory
        Возвращает байты картинки (PNG).
        """
        if not history_data or len(history_data) < 2:
            return None

        # 1. Подготовка данных
        dates = [r.date for r in history_data]
        weights = [r.weight for r in history_data]

        # 2. Настройка стиля графика
        plt.figure(figsize=(10, 6))
        plt.style.use('bmh') # Красивый стиль "Bayesian Methods for Hackers"

        # Рисуем линию и точки
        plt.plot(dates, weights, marker='o', linestyle='-', color='#2ecc71', linewidth=2, label='Вес (кг)')
        
        # Добавляем подписи значений над точками
        for x, y in zip(dates, weights):
            plt.annotate(f"{y}", xy=(x, y), xytext=(0, 5), textcoords="offset points", ha='center')

        # Заголовки
        plt.title('Динамика веса', fontsize=16)
        plt.xlabel('Дата', fontsize=12)
        plt.ylabel('Вес (кг)', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.legend()

        # Форматирование дат на оси X
        plt.gcf().autofmt_xdate()

        # 3. Сохранение в буфер (в память, не в файл)
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        buf.seek(0)
        plt.close()

        return buf