from typing import Tuple
import numpy as np
import math as m

class DieselGenerator:
    """
    Класс моделирования работы дизель-генератора
    A class that models a diesel generator (DG).
    """

    def __init__(self,
            num_DGs: int,
            gen_capacity: float,
            a1: float,
            a2: float,
            fuel_price: float
            ):
        """
        Инициализация объекта дизель-генераторной системы
        Initialization of the diesel generator system object.

        Параметры (Parameters)
        ----------
        num_DGs: int
            Количество генераторов, шт
            Number of diesel generators, pcs
        gen_capacity: float
            Установленная мощность каждого генератора (кВт)
            The nominal power of each diesel generator (kW)
        a1: float
            Эмпирический коэффициент, л/кВт·ч.
            The fuel curve intercept coefficient, l/kWh
        a2: float
            Эмпирический коэффициент, л/кВт·ч.
            The fuel curve slope, l/kWh
        fuel_price: float
            Стоимость ДТ, руб./кг
            The cost of a kg of fuel, RUB/kg.
        """
        # Основные параметры
        # Basic parameters
        self.n = num_DGs
        self.gen_capacity = gen_capacity # Установленная мощность, кВт
        self.a1 = a1
        self.a2 = a2
        # self.start_stop_price = start_stop_price
        self.fuel_price = fuel_price
        # Расчетные параметры
        # Calculated parameters
        self.p_min = 0.35 * self.gen_capacity
        self.p_max = 0.95 * self.gen_capacity
        # Состояние массива генераторов
        # Status of the generator array
        self.power_outputs = np.ones(self.n)



    def get_parameters(self) -> np.ndarray:
        """
        Получить массив дизель-генераторов
        Get an array of diesel generators

        Возвращает (Returns)
        ----------
        np.ndarray:
            Массив генераторов в кВт.
        num_DGs: int
            Количество генераторов, шт.
            Number of diesel generators, pcs.
        """
        gen_set = self.power_outputs * self.gen_capacity

        return gen_set, self.n

    def calculate_fuel_consumption(self, generate_array: np.ndarray,p: float
    = 860.0, LHV: float = 43.2) -> Tuple[np.ndarray,np.ndarray]:
        """
        Зависимость расхода топлива от номинальной мощности и текущей нагрузки ДГУ
        The fuel consumption of the diesel generator (DG)
        Параметры (Parameters)
        ----------
        generate_array: np.ndarray
            Массив мощностей генераторов, кВт
            Array of diesel generator power outputs, kW
        p : float, optional
            Плотность топлива, по умолчанию 860 кг/м3
            Fuel density, default 860 kg/m3
        LHV : float, optional
            Низшая теплота сгорания, по умолчанию 43.2 МДж/кг
            Lower Heating Value, default 43.2 MJ/kg

        Возвращает (Returns)
        ----------
        Tuple[np.ndarray, np.ndarray, np.ndarray]:
            SFC: np.ndarray
                Удельный расход условного топлива, о.е.
                Specific fuel consumption, l/kWh
            AFC: np.ndarray
                Абсолютный расход топлива, кг
                Absolute fuel consumption, kg
            EFF: np.ndarray
                Электрический КПД ДГУ, о.е. (0..1). Для генераторов,
                не несущих нагрузку (generate_array <= 0), КПД равен 0.
                Electrical efficiency of the DG, p.u. (0..1). For idle
                generators (generate_array <= 0), efficiency is 0.
        """
        # Инициализация массивов
        SFC = np.zeros_like(generate_array, dtype=np.float64)
        AFC = np.zeros_like(generate_array, dtype=np.float64)
        EFF = np.zeros_like(generate_array, dtype=np.float64)
        # Маска для работающих генераторов
        mask = generate_array > 0
        L = generate_array[mask] / self.gen_capacity # текущая загрузка ДГУ относительно номинальной мощности от 0 до 1
        SFC[mask] = self.a1 * 1 / L + self.a2
        AFC[mask] = p * SFC[mask] * generate_array[mask] * 1e-3
        EFF[mask] = (3.6 * generate_array[mask]) / (AFC[mask] * LHV)
        return SFC, AFC, EFF

    def total_cost(self, power: np.ndarray, u: np.ndarray, u_prev: np.ndarray) -> float:
        """
        Полная стоимость: топливо + старт/стоп
        Параметры (Parameters)
        ----------
        power: np.ndarray
            Мощность генераторов, кВт.
            Power of generators, kW.
        u: np.ndarray
            Текущее состояние генераторов (1 - вкл, 0 - выкл).
            The current status of the generators (1 - on, 0 - off).
        u_prev: np.ndarray
            Предыдущее состояние генераторов (1 - вкл, 0 - выкл).
            Previous status of generators (1 - on, 0 - off).
        """
        # Расчет стоимости топлива
        _, fuel_cons, _ = self.calculate_fuel_consumption(power)
        fuel_cost = np.sum(fuel_cons) * self.fuel_price
        # Расчет штрафа за старт/стоп
        # start_penalty = np.sum(self.start_stop_price * np.maximum(0, u - u_prev))
        # Общая стоимость
        return fuel_cost

    def optimize_DGs(self, u_prev: np.ndarray,
                                         load: float) -> Tuple[np.ndarray, np.ndarray, float, float, int]:
        """
        Оптимизация распределения нагрузки между генераторами.
        Optimization of generator load distribution.

        Параметры (Parameters)
        ----------
        u_prev: np.ndarray
            Предыдущее состояние генераторов (1 - вкл, 0 - выкл).
            Previous status of generators (1 - on, 0 - off).
        load: float
            Требуемая мощность нагрузки, кВт
            Electrical load, kW

        Возвращает (Returns)
        -----------
        Tuple[np.ndarray, np.ndarray, float, float, int]:
            best_p: np.ndarray
                Оптимальное распределение мощностей, кВт
            best_u: np.ndarray
                Оптимальное состояние генераторов
            best_cost: np.ndarray
                Минимальная стоимость работы, руб
            total_p: float
                Суммарная выдаваемая мощность, кВт
            is_on: int
                Количество работающих генераторов.
        """
        n = self.n

        if load > n * self.p_max:
            raise ValueError(
                f"Требуемая нагрузка {load} кВт превышает максимальную "
                f"мощность системы {n * self.p_max} кВт"
            )
        best_p = np.zeros(n, dtype=np.float64)
        best_u = np.zeros(n, dtype=np.int64)
        best_cost = np.inf

        k_min = max(1, m.ceil(load / self.p_max))
        # if k < 1:
        #     k = 1
        #     load = self.p_min

        for k in range(k_min, n + 1):
            p = load / k
            p_per_gen = max(self.p_min, min(self.p_max, p))
            p_load = np.zeros(n, dtype=np.float64)
            p_load[:k] = p_per_gen

            u_candidate = np.zeros(n, dtype=np.int64)
            u_candidate[:k] = 1

            total_p = p_load.sum()

            if total_p < load:
                continue

            cost = self.total_cost(p_load, u_candidate, u_prev)
            if cost < best_cost:
                best_p = p_load.copy()
                best_u = u_candidate.copy()
                best_cost = cost


        total_p = best_p.sum()
        is_on = (best_u > 0).sum()

        return best_p, best_u, best_cost, total_p, is_on

    def _restriction_dgs(self, val_dgs: np.ndarray, net_power: float):
        """Ограничение ДГУ и расчет стоимости этого действия
           Restricting the DSU and calculating the cost of this action
        """
        best_p, best_u, best_cost, total_p, is_on = self.optimize_DGs(
            val_dgs, load= 0.0)
        shunt_gen = np.maximum(0, net_power - total_p)
        new_gen = net_power - shunt_gen
        return best_p, best_u, best_cost, total_p, is_on, new_gen, shunt_gen

    def _shutdown_dgs(self, val_dgs: np.ndarray) -> Tuple[np.ndarray, float]:
        """Остановка ДГУ и расчет стоимости этого действия
           Stopping diesel generators and calculating the cost of this action
        """
        best_u = np.zeros_like(val_dgs)
        best_cost = self.total_cost(best_u, val_dgs, best_u)
        best_p, total_p, is_on = 0, 0, 0
        return best_p, best_u, best_cost, total_p, is_on




