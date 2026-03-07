import io
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
        
        # Группируем веса по упражнениям
        ex_dict = defaultdict(list)
        for ex in exercises:
            if not ex.exercise_name:  # ДОБАВЛЕНО
                continue
            name = ex.exercise_name.capitalize()
            ex_dict[name].append((ex.date, ex.weight))
            
        # Берем Топ-3 самых частых упражнения, чтобы не захламлять график
        top_exercises = sorted(ex_dict.keys(), key=lambda k: len(ex_dict[k]), reverse=True)[:3]
        colors = ['#00a8ff', '#e84118', '#fbc531']
        
        for i, name in enumerate(top_exercises):
            data = sorted(ex_dict[name], key=lambda x: x[0]) # Сортируем по дате
            dates = [d[0] for d in data]
            weights = [d[1] for d in data]
            
            if len(dates) > 1:
                ax.plot(dates, weights, marker='o', label=name, color=colors[i%3], linewidth=2)
            else:
                ax.scatter(dates, weights, label=name, color=colors[i%3], s=60)
                
        if not ax.has_data(): return None

        ax.set_title('Прогресс рабочих весов (Топ-3)', color='white', pad=15, fontsize=14)
        ax.grid(color='white', alpha=0.1)
        ax.tick_params(colors='white')
        ax.legend(facecolor='#2f3640', edgecolor='none', labelcolor='white')
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
        ax3.set_facecolor('#1e1e1e')
        if exercises:
            ex_dict = defaultdict(list)
            for ex in exercises:
                ex_dict[ex.exercise_name.capitalize()].append((ex.date, ex.weight))
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