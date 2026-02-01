from typing import Tuple
from itertools import product
import numpy as np

class DieselGenerator:
    def __init__(self, num_DGs: int, r_capacity: float, a1: float, a2: float, start_stop_price: float, fuel_price: float):
        """
        Класс моделирования работы дизель-генератора
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
            Стоимость пуска-останова одного двигателя, руб.
            The cost of starting and stopping one diesel generator, RUB
        fuel_price: float
            Стоимость кз топлива, руб./кг
            The cost of a kg of fuel, RUB/kg.
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
            Плотность топлива, по умолчанию 860 кг/м3
            Fuel density, default 860 kg/m3
        k : float, optional
            Коэффициент теплотворной способности, по умолчанию 1.45
            Calorific value coefficient, default 1.45

        Возвращает (Returns)
        specific_cons: np.ndarray
            Удельный расход условного топлива, л/кВт·ч
            Specific fuel consumption, l/kWh
        total_cons: np.ndarray
            Абсолютный расход топлива, кг
            Absolute fuel consumption, kg
        ----------

        """
        specific_cons = np.zeros_like(generate_array, dtype=np.float64)
        mask = generate_array > 0
        specific_cons[mask] = self.a1 * generate_array[mask] + self.a2 * self.r_capacity
        total_cons = np.zeros_like(generate_array, dtype=np.float64)
        total_cons[mask] = specific_cons[mask] * generate_array[mask] / (p * k)
        return specific_cons, total_cons

    def total_cost(self, power: np.ndarray, u: np.ndarray, u_prev: np.ndarray, r_electricity: float) -> float:
        """
        Полная стоимость: топливо + старт/стоп
        Параметры (Parameters)
        ----------
        power: float
            Мощность генератора.
            Generator power.
        """
        # Топливо
        _, fuel_cons = self.calculate_fuel_consumption(power)
        fuel_cost = np.sum(fuel_cons) * r_electricity

        # Старт/стоп
        start_penalty = np.sum(self.start_stop_price * np.maximum(0, u - u_prev))

        return fuel_cost + start_penalty

    def _allocate_equal_with_bounds(self, n: int, load: float) -> np.ndarray:
        """
        Water-filling алгоритм.
        Распределяем S между n генераторами в пределах [p_min, p_max]
        """
        if n == 0:
            return np.array([])
        low, high = self.p_min, self.p_max
        x = np.full(n, load / n, dtype=np.float64)
        mask_free = np.ones(n, dtype=bool)
        remaining_load = load
        remaining_n = n

        for _ in range(n):
            if remaining_n == 0:
                break
            share = remaining_load / remaining_n
            below = mask_free & (share <= low)
            above = mask_free & (share >= high)
            if not below.any() and not above.any():
                x[mask_free] = share
                break
            if below.any():
                x[below] = low
                remaining_load -= low * below.sum()
                mask_free[below] = False
                remaining_n = mask_free.sum()
                continue
            if above.any():
                x[above] = high
                remaining_load -= high * above.sum()
                mask_free[above] = False
                remaining_n = mask_free.sum()
                continue
        allocated_power = np.clip(x, low, high)
        return allocated_power

    def optimize_DGs(self, u_prev: np.ndarray,
                                         load: float, r_electricity: float):
        """
        Распределение нагрузки между работающими генераторами

        Параметры (Parameters)
        ----------
        u_prev: np.ndarray
            Количество работающих генераторов, шт
            Number of generators running, pcs
        load: float
            Требуемая мощность нагрузки, кВт
            Electrical load, kW
        r_electricity: float
            Тариф на электроэнергию, руб./кВт·ч
            Electricity tariff, RUB/kWh

        Возвращает (Returns)
        -----------
        Распределение мощности между генераторами
        best_p: np.ndarray
            Оптимальные мощности
        best_u: np.ndarray
            Статус генераторов (1=вкл,0=выкл)
        best_cost: np.ndarray
            Минимальная стоимость
        """
        n = self.n
        best_cost = np.inf
        best_p = None
        best_u = None

        # Перебор всех комбинаций включённых генераторов (0/1)
        for u_candidate in product([0, 1], repeat=n):
            u_candidate = np.array(u_candidate, dtype=int)
            running_count = u_candidate.sum()

            # Проверяем, возможно ли распределить нагрузку
            if running_count == 0 or load < running_count * self.p_min or load > running_count * self.p_max:
                continue  # невозможно

            # Равномерно распределяем нагрузку среди включённых ДГУ
            p_candidate = self._allocate_equal_with_bounds(
                n=running_count,
                load=load
            )
            # Формируем полный массив мощностей с нулями для выключенных
            p_full = np.zeros(n)
            p_full[u_candidate == 1] = p_candidate

            # Считаем полную стоимость
            cost = self.total_cost(p_full, u_candidate, u_prev, r_electricity)

            # Сохраняем лучший вариант
            if cost < best_cost:
                best_cost = cost
                best_p = p_full
                best_u = u_candidate

        return best_p, best_u, best_cost




