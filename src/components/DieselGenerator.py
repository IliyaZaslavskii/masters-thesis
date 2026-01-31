from typing import Tuple
import numpy as np

class DieselGenerator:
    def __init__(self, num_DGs: int, r_capacity: float, a1: float, a2: float, start_stop_price: float, fuel_price: float):
        """
        Класс моделирования системы накопления электрической энергии (СНЭЭ)
        A class that models a diesel generator (DG).
        num_DGs: int
            Количество генераторов, шт
            Number of diesel generators, pcs
        r_capacity: float
            Номинальная мощность каждого генератора (кВт)
            The nominal power of each diesel generator (kW)
        a1: float
            Эмпирический коэффициент, л/кВт·ч.
            The fuel curve intercept coefficient, l/kWh
        a2: float
            Эмпирический коэффициент, л/кВт·ч.
            The fuel curve slope, l/kWh
        start_stop_price: float
            Стоимость пуска-останова одного двигателя
        fuel_price: float
            Стоимость литра топлива
        """

        self.num_DGs = num_DGs
        self.r_capacity = r_capacity
        self.p_min = 0.35 * self.r_capacity
        self.p_max = 0.95 * self.r_capacity
        self.a1 = a1
        self.a2 = a2
        self.start_stop_price = start_stop_price
        self.fuel_price = fuel_price
        # Состояние массива генераторов
        # Status of the generator array
        self.power_outputs = np.ones(num_DGs)
        self.n = self.power_outputs.size
        # self.fuel_consumption = 0.0  # Общий расход топлива
        # self.fuel_cost = 0.0  # Общая стоимость
        # self.start_up_count = 0  # Количество запусков


    def get_DGs(self) -> np.ndarray:
        """
        Получить массив дизель-генераторов
        Get an array of diesel generators

        Возвращает (Returns)
        ----------
        np.ndarray
        """
        return self.power_outputs * self.p_min

    def calculate_fuel_consumption(self, generate_array: np.ndarray, p: float = 860, k: float = 1.45) -> Tuple[np.ndarray,np.ndarray]:
        """
        Зависимость расхода топлива от номинальной мощности и текущей нагрузки ДГУ
        The fuel consumption of the diesel generator (DG)
        Параметры (Parameters)
        ----------
        generate_array: np.ndarray
            Массив мощностей генераторов
            Array of diesel generator power outputs
        p : float, optional
            Плотность топлива, по умолчанию 860
            Fuel density, default 860
        k : float, optional
            Коэффициент теплотворной способности, по умолчанию 1.45
            Calorific value coefficient, default 1.45

        Возвращает (Returns)
        specific_cons: np.ndarray
            Удельный расход условного топлива
        total_cons: np.ndarray
            Абсолютный расход топлива
        ----------

        """
        specific_cons = np.zeros_like(generate_array, dtype=np.float64)
        mask = generate_array > 0
        specific_cons[mask] = self.a1 * generate_array[mask] + self.a2 * self.r_capacity
        total_cons = np.zeros_like(generate_array, dtype=np.float64)
        total_cons[mask] = specific_cons[mask] * generate_array[mask] / (p * k)

        return specific_cons, total_cons

    def _allocate_equal_with_bounds(self,n: int, total_power: float) -> np.ndarray:
        """
        Water-filling алгоритм.

        Равномерно распределяет суммарную мощность total_power
        между number_of_units генераторами так, чтобы:
        - сумма равнялась total_power
        - каждая мощность лежала в [p_min, p_max]
        """
        if n == 0:
            return np.array([])
        # Нижняя и верхняя границы мощности одного генератора
        min_power = self.p_min
        max_power = self.p_max
        # Проверка достижимости задачи
        min_total = n * min_power
        max_total = n * max_power

        if total_power < min_total - 1e-9 or total_power > max_total + 1e-9:
            raise ValueError("S out of feasible range for given n and bounds")
        # Начальное предположение, равномерное распределение
        allocated_power  = np.full(n, total_power / n, dtype=np.float64)
        # Маска генераторов, которые ещё МОЖНО догружать
        free_units_mask = np.ones(n, dtype=bool)
        # Сколько мощности осталось распределить
        remaining_power = total_power
        # Сколько генераторов ещё свободны
        remaining_units = n
        # Итеративный water-filling
        for _ in range(n):
            if remaining_units == 0:
                break
        # Попытка равномерного распределения
            equal_share = remaining_power / remaining_units
        # Генераторы, которые при равномерной доле
        # выходят за пределы
            below_min = free_units_mask & (equal_share <= min_power + 1e-12)
            above_max = free_units_mask & (equal_share >= max_power - 1e-12)
        # Если все свободные генераторы укладываются в диапазон
            if not below_min.any() and not above_max.any():
                allocated_power[free_units_mask] = equal_share
                break
            if below_min.any():
                allocated_power[below_min] = min_power
                remaining_power -= min_power * below_min.sum()
                free_units_mask[below_min] = False
                remaining_units = free_units_mask.sum()
                continue
        # Если равномерная доля выше максимума
            if above_max.any():
                allocated_power[above_max] = max_power
                remaining_power -= max_power * above_max.sum()
                free_units_mask[above_max] = False
                remaining_units = free_units_mask.sum()
                continue
        # Защита от численных ошибок
        allocated_power = np.clip(allocated_power, min_power, max_power)
        # Коррекция суммы (из-за float)
        difference = total_power - allocated_power.sum()

        if abs(difference) > 1e-6:
        # Пытаемся распределить разницу по "свободным" генераторам
        adjustable_indices = np.where(
            (allocated_power > min_power + 1e-12) &
            (allocated_power < max_power - 1e-12)
        )[0]

        if adjustable_indices.size == 0:
            adjustable_indices = np.where(
                (allocated_power >= min_power - 1e-12) &
                (allocated_power <= max_power + 1e-12)
            )[0]

            for idx in adjustable_indices:
                allocated_power[idx] += difference / adjustable_indices.size

            allocated_power = np.clip(allocated_power, min_power, max_power)
        return allocated_power

    def distribute_load_among_generators(self, DGs_running: np.ndarray,
                                         load: float, r_electricity: float) -> np.ndarray:
        """
        Распределение нагрузки между работающими генераторами

        Параметры (Parameters)
        ----------
        DGs_running: np.ndarray
            Количество работающих генераторов
            Number of generators running
        load: float
            Требуемая мощность нагрузки
            Electrical load
        r_electricity: float
            Тариф на электроэнергию
            Electricity tariff

        Возвращает (Returns)
        -----------
        np.ndarray: Распределение мощности между генераторами
        """
        # 1. Подготовка входных данных
        n = self.n
        if n == 0:
            raise ValueError("Generator list is empty")
        # Текущее состояние генераторов
        is_running_now  = DGs_running > 1e-9 #BOOL
        running_generators_count = int(is_running_now.sum())
        # 2. Переменные для лучшего решения
        best_total_cost = np.inf
        best_power_distribution = np.zeros(n, dtype=np.float64)
        best_info = {}
        # 3. Перебор количества включенных ДГ
        for online_generators_count in range(1, n + 1):
        # 3.1 Проверка физической возможности
            min_total = online_generators_count * self.p_min
            max_total = online_generators_count * self.p_max
        # Даже при максимальной загрузке не покрываем нагрузку
            if max_total + 1e-9 < load:
                continue
            total_generation_required = max(load, min_total)
            if total_generation_required > max_total + 1e-9:
                continue
        # 3.2 Выбор, какие ДГ будут включены
        # Сколько текущих ДГ можно оставить включенными
            keep_from_running = min(online_generators_count, running_generators_count)
        # Индексы работающих ДГ
            running_is_on = np.where(is_running_now)[0]
        # Сортируем работающие ДГ по убыванию текущей мощности
        # (сильно нагруженные выгоднее сохранить)
            if running_is_on.size > 0:
                order = running_is_on[np.argsort(-DGs_running[running_is_on])]
            else:
                order = np.array([], dtype=int)
        # Оставляем нужное количество работающих ДГ
            selected_generators = order[:keep_from_running].tolist()
        # Если нужно включить дополнительные ДГ
            if len(selected_generators) < online_generators_count:
                stopped_indices = np.where(~is_running_now)[0]
                additional_needed = list(stopped_indices[:(online_generators_count - len(selected_generators))])
                selected_generators += additional_needed
        # Итоговый набор включенных ДГ
            selected_generators = np.array(sorted(selected_generators), dtype=int)
            try:
        # 3.3 Распределение мощности
        # Равномерное распределение с учетом [min_power, max_power]
                allocation = DieselGenerator._allocate_equal_with_bounds(
                    online_generators_count,
                    total_generation_required)
            except ValueError:
                continue
        # Формируем полный вектор мощностей
            power_distribution = np.zeros(n, dtype=np.float64)
            power_distribution[selected_generators] = allocation # присваиваем мощность включенным ДГ
        # 3.4 Расчёт топлива
            _, fuel_consumption = DieselGenerator.calculate_fuel_consumption(
                power_distribution)
            total_fuel = float(fuel_consumption.sum())
            fuel_cost = total_fuel * r_electricity
        # 3.5 Стоимость переключений
            is_running_after = power_distribution  > 1e-9
            switching_events = int(np.sum(is_running_now  != is_running_after))
            switching_cost = switching_events * self.start_stop_price
        # 3.6 Итоговая стоимость
            total_cost = fuel_cost + switching_cost
        # 3.7 Проверка на лучшее решение
            if (total_cost < best_total_cost - 1e-9) or (
                    abs(total_cost - best_total_cost) < 1e-9 and switching_events < best_info.get("switching_count", 1e9)):
                best_total_cost = total_cost
                best_power_distribution = power_distribution.copy()
                best_info = {
                    "online_generators": online_generators_count,
                    "generator_indices": selected_generators,
                    "fuel_consumption": total_fuel,
                    "fuel_cost": fuel_cost,
                    "switching_events": switching_events,
                    "switching_cost": switching_cost,
                    "total_cost": total_cost,
                    "assigned": power_distribution
                }
        # 4. Финальная проверка
            if best_total_cost  == np.inf:
                raise RuntimeError("No feasible assignment found to serve the load with given generator limits.")
            return best_power_distribution, best_info




