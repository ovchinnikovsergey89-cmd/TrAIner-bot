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
    async def create_nutrition_graph(nut_days, user_sub="free"):
        if not nut_days: 
            return None
            
        import numpy as np
        from scipy.interpolate import make_interp_spline

        # 1. Агрегация данных по дням
        daily = {}
        for row in nut_days:
            day_str = str(row.day)[-5:]
            if day_str not in daily:
                daily[day_str] = {'k': 0, 'p': 0, 'f': 0, 'c': 0}
            daily[day_str]['k'] += float(row.kcal or 0)
            daily[day_str]['p'] += float(row.p or 0)
            daily[day_str]['f'] += float(row.f or 0)
            daily[day_str]['c'] += float(row.c or 0)

        days = sorted(daily.keys())
        if not days: return None
        
        # Создаем "двухэтажную" сетку (2 строки, 1 колонка)
        # Калории сверху (узкие), БЖУ снизу (высокие)
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [1, 2]})
        fig.patch.set_facecolor('#121212')

        # --- ВЕРХНИЙ ЭТАЖ: КАЛОРИИ ---
        kcals = [daily[d]['k'] for d in days]
        ax1.set_facecolor('#121212')
        ax1.bar(days, kcals, color='#00a8ff', alpha=0.3, width=0.5)
        
        avg_kcal = sum(kcals)/len(kcals)
        ax1.axhline(avg_kcal, color='#00a8ff', linestyle='--', alpha=0.5, linewidth=1)
        ax1.text(len(days)-1, avg_kcal, f' Ср: {int(avg_kcal)}', color='#00a8ff', va='bottom', fontsize=9)
        
        ax1.set_title('ПОТРЕБЛЕНИЕ ЭНЕРГИИ (ккал)', color='white', loc='left', fontsize=10, fontweight='bold')
        ax1.tick_params(colors='white', labelsize=8)
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.xaxis.set_visible(False) # Скрываем даты на верхнем графике

        # --- НИЖНИЙ ЭТАЖ: БЖУ ---
        ax2.set_facecolor('#121212')
        x_numeric = np.arange(len(days))
        x_smooth = np.linspace(x_numeric.min(), x_numeric.max(), 300)

        nutrients = [('Белки', 'p', '#ff4757'), ('Жиры', 'f', '#ffa502'), ('Углеводы', 'c', '#2ed573')]

        for label, key, color in nutrients:
            y_values = [daily[d][key] for d in days]
            
            # Линии и сглаживание
            if len(days) > 2:
                spl = make_interp_spline(x_numeric, y_values, k=2)
                y_smooth = np.clip(spl(x_smooth), 0, None)
                ax2.plot(x_smooth, y_smooth, color=color, linewidth=2.5, label=label)
                ax2.fill_between(x_smooth, y_smooth, color=color, alpha=0.07)
            else:
                ax2.plot(days, y_values, color=color, marker='o', linewidth=2, label=label)

            # Цифра над последней точкой
            ax2.annotate(f'{int(y_values[-1])}г', xy=(len(days)-1, y_values[-1]), 
                         xytext=(0, 7), textcoords='offset points', 
                         color=color, fontweight='bold', ha='center', fontsize=10)

        ax2.set_title('БАЛАНС НУТРИЕНТОВ (г)', color='white', loc='left', fontsize=10, fontweight='bold')
        ax2.legend(loc='upper left', facecolor='none', edgecolor='none', labelcolor='white', fontsize=9, ncol=3)
        ax2.tick_params(colors='white', labelsize=9)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.set_ylim(bottom=0)

        plt.tight_layout(pad=3.0)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=130, bbox_inches='tight', facecolor=fig.get_facecolor())
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