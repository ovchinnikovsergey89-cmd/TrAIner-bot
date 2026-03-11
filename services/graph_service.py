import io
import re  # <--- Обязательно добавь это!
import matplotlib
matplotlib.use('Agg') # Анти-GUI бэкенд для сервера
import matplotlib.pyplot as plt
from collections import defaultdict

class GraphService:
    
    @staticmethod
    async def create_weight_graph(history_data):
        if not history_data or len(history_data) < 2: 
            return None
            
        fig, ax = plt.subplots(figsize=(8, 4))
        fig.patch.set_facecolor('#1e1e1e')
        ax.set_facecolor('#1e1e1e')
        
        dates = [h.date for h in history_data]
        weights = [h.weight for h in history_data]
        
        ax.plot(dates, weights, marker='o', color='#00a8ff', linewidth=2, markersize=6)
        ax.set_title('Динамика веса тела', color='white', pad=15, fontsize=14)
        ax.grid(color='white', alpha=0.1)
        ax.tick_params(colors='white')
        fig.autofmt_xdate()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf
        
    @staticmethod
    async def create_workouts_graph(exercises):
        if not exercises: 
            return None
            
        fig, ax = plt.subplots(figsize=(8, 4))
        fig.patch.set_facecolor('#1e1e1e')
        ax.set_facecolor('#1e1e1e')
        
        ex_dict = defaultdict(list)
        for ex in exercises:
                # 1. Берем нормализованное имя (если есть), иначе обычное
                raw_name = ex.canonical_name if ex.canonical_name else ex.exercise_name
                if not raw_name:
                    raw_name = "Упражнение"
                    
                # 2. ЖЕСТКАЯ ОЧИСТКА (удаляем лишние пробелы, приводим всё к нижнему регистру, меняем Ё на Е)
                import re
                clean_name = re.sub(r'\s+', ' ', str(raw_name)).strip().lower().replace('ё', 'е').capitalize()
                
                # 3. Добавляем в словарь уже идеально чистое имя
                ex_dict[clean_name].append((ex.date, ex.weight))
            
        # Берем Топ-3 упражнения
        top_ex = sorted(ex_dict.keys(), key=lambda k: len(ex_dict[k]), reverse=True)[:3]
        colors = ['#00a8ff', '#e84118', '#fbc531']
        
        plotted = False
        for i, name in enumerate(top_ex):
            data = sorted(ex_dict[name], key=lambda x: x[0])
            if len(data) > 0:
                plotted = True
                dates = [d[0] for d in data]
                weights = [d[1] for d in data]
                if len(data) > 1:
                    ax.plot(dates, weights, marker='o', label=name, color=colors[i%3])
                else:
                    # Если всего 1 подход, рисуем точку и она 100% отобразится
                    ax.scatter(dates, weights, label=name, color=colors[i%3], zorder=5)

        if not plotted:
            plt.close(fig)
            return None

        ax.set_title('Прогресс рабочих весов (Топ-3)', color='white', pad=15, fontsize=14)
        ax.grid(color='white', alpha=0.1)
        ax.tick_params(colors='white')
        ax.legend(facecolor='#1e1e1e', edgecolor='white', labelcolor='white') # Добавили легенду
        fig.autofmt_xdate()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf

    @staticmethod
    async def create_nutrition_graph(nut_days):
        if not nut_days: 
            return None
            
        fig, ax = plt.subplots(figsize=(8, 4))
        fig.patch.set_facecolor('#1e1e1e')
        ax.set_facecolor('#1e1e1e')
        
        # Оставляем только Месяц-День (например, 02-27), чтобы график был красивым
        days = [str(d.day)[-5:] for d in nut_days] 
        kcals = [d.kcal for d in nut_days]
        
        ax.bar(days, kcals, color='#4cd137', alpha=0.8, width=0.5)
        
        # Добавляем пунктирную линию среднего значения калорий
        if kcals:
            avg_kcal = sum(kcals) / len(kcals)
            ax.axhline(avg_kcal, color='#e84118', linestyle='--', linewidth=1.5, label=f'Среднее: {int(avg_kcal)} ккал')
            
        ax.set_title('Потребление калорий (7 дней)', color='white', pad=15, fontsize=14)
        ax.grid(color='white', alpha=0.1, axis='y')
        ax.tick_params(colors='white')
        ax.legend(facecolor='#2f3640', edgecolor='none', labelcolor='white')
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf

    @staticmethod
    async def create_combined_dashboard(history_data, exercises, nut_days):
        # Рисуем огромный дашборд из 3 графиков друг под другом
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 12))
        fig.patch.set_facecolor('#1e1e1e')
        
        # 1. Вес
        ax1.set_facecolor('#1e1e1e')
        if history_data and len(history_data) >= 2:
            dates = [h.date for h in history_data]
            weights = [h.weight for h in history_data]
            ax1.plot(dates, weights, marker='o', color='#00a8ff', linewidth=2)
        ax1.set_title('Динамика веса', color='white', fontsize=12)
        ax1.grid(color='white', alpha=0.1)
        ax1.tick_params(colors='white')
        
        # 2. Питание
        ax2.set_facecolor('#1e1e1e')
        if nut_days:
            days = [str(d.day)[-5:] for d in nut_days]
            kcals = [d.kcal for d in nut_days]
            ax2.bar(days, kcals, color='#4cd137', alpha=0.8, width=0.5)
        ax2.set_title('Калории (7 дней)', color='white', fontsize=12)
        ax2.grid(color='white', alpha=0.1, axis='y')
        ax2.tick_params(colors='white')
            
        # 3. Тренировки
        # 3. Тренировки
        ax3.set_facecolor('#1e1e1e')
        if exercises:
            ex_dict = defaultdict(list)
            for ex in exercises:
                # 1. Достаем имя
                raw_name = ex.canonical_name if ex.canonical_name else ex.exercise_name
                if not raw_name:
                    continue
                
                # 2. ЖЕСТКАЯ ОЧИСТКА
                # Убираем все пробелы, приводим к нижнему регистру, меняем Ё на Е
                clean_name = re.sub(r'\s+', ' ', raw_name).strip().lower().replace('ё', 'е').capitalize()
                
                ex_dict[clean_name].append((ex.date, ex.weight))

            top_ex = sorted(ex_dict.keys(), key=lambda k: len(ex_dict[k]), reverse=True)[:3]
            colors = ['#00a8ff', '#e84118', '#fbc531']
            for i, name in enumerate(top_ex):
                data = sorted(ex_dict[name], key=lambda x: x[0])
                if len(data) > 1:
                    ax3.plot([d[0] for d in data], [d[1] for d in data], marker='o', label=name, color=colors[i%3])
                else:
                    ax3.scatter([d[0] for d in data], [d[1] for d in data], label=name, color=colors[i%3])
            ax3.legend(facecolor='#2f3640', edgecolor='none', labelcolor='white')
        ax3.set_title('Прогресс весов (Топ-3)', color='white', fontsize=12)
        ax3.grid(color='white', alpha=0.1)
        ax3.tick_params(colors='white')

        plt.tight_layout(pad=3.0)
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf