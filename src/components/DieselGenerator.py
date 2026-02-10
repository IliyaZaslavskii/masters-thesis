from typing import Tuple
import numpy as np

class DieselGenerator:
    """
    Класс моделирования работы дизель-генератора
    A class that models a diesel generator (DG).
    """

    def __init__(self,
            num_DGs: int,
            r_capacity: float,
            a1: float,
            a2: float,
            start_stop_price: float,
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
        # Основные параметры
        # Basic parameters
        self.num_DGs = num_DGs
        self.r_capacity = r_capacity # Номинальная мощность, кВт
        self.a1 = a1
        self.a2 = a2
        self.start_stop_price = start_stop_price
        self.fuel_price = fuel_price
        # Расчетные параметры
        # Calculated parameters
        self.p_min = 0.35 * self.r_capacity
        self.p_max = 0.95 * self.r_capacity
        # Состояние массива генераторов
        # Status of the generator array
        self.power_outputs = np.ones(num_DGs)
        self.n = self.power_outputs.size# Количество генераторо


    def get_DGs(self) -> np.ndarray:
        """
        Получить массив дизель-генераторов
        Get an array of diesel generators

        Возвращает (Returns)
        ----------
        np.ndarray:
            Массив мощностей генераторов в кВт.
            Для генераторов возвращается номинальная мощность.
        """
        return self.power_outputs * self.r_capacity

    def calculate_fuel_consumption(self, generate_array: np.ndarray, p: float = 860.0, k: float = 1.45) -> Tuple[np.ndarray,np.ndarray]:
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
        ----------
        Tuple[np.ndarray, np.ndarray]:
            specific_cons: np.ndarray
                Удельный расход условного топлива, л/кВт·ч
                Specific fuel consumption, l/kWh
            total_cons: np.ndarray
                Абсолютный расход топлива, кг
                Absolute fuel consumption, kg
        """
        # Инициализация массивов
        specific_cons = np.zeros_like(generate_array, dtype=np.float64)
        total_cons = np.zeros_like(generate_array, dtype=np.float64)
        # Маска для работающих генераторов
        mask = generate_array > 0
        L = generate_array[mask] / self.r_capacity # текущая загрузка ДГУ относительно номинальной мощности от 0 до 1
        specific_cons[mask] = self.a1 * 1 / L + self.a2
        total_cons[mask] = specific_cons[mask] * generate_array[mask] / (p * k)
        return specific_cons, total_cons

    def total_cost(self, power: np.ndarray, u: np.ndarray, u_prev: np.ndarray, r_electricity: float) -> float:
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
        r_electricity: float
            Тариф на электроэнергию, руб./кВт·ч.
            Electricity tariff, RUB/kWh.
        """
        # Расчет стоимости топлива
        _, fuel_cons = self.calculate_fuel_consumption(power)
        fuel_cost = np.sum(fuel_cons) * r_electricity
        # Расчет штрафа за старт/стоп
        start_penalty = np.sum(self.start_stop_price * np.maximum(0, u - u_prev))
        # Общая стоимость
        return fuel_cost + start_penalty

    def optimize_DGs(self, u_prev: np.ndarray,
                                         load: float, r_electricity: float) -> Tuple[np.ndarray, np.ndarray, float, float, int]:
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
        r_electricity: float
            Тариф на электроэнергию, руб./кВт·ч
            Electricity tariff, RUB/kWh

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
        best_p = None
        best_u = None
        best_cost = np.inf

        k = round(load / self.p_max)
        if k > n:
            raise ValueError(
                f"Требуемая нагрузка {load} кВт превышает максимальную\nмощность системы {n * self.p_max} кВт"
            )
        else:
            if k < 1:
                k = 1
                load = self.p_min
            while k <= n:
                p = load / k
                if p < self.p_min:
                    break
                p_load = np.array([p] * k + [0] * (n - k), dtype=np.float64)
                u_candidate = np.array([1] * k + [0] * (n - k), dtype=np.int64)
                k += 1

            # Считаем полную стоимость
            cost = self.total_cost(p_load, u_candidate, u_prev, r_electricity)

            # Сохраняем лучший вариант
            if cost < best_cost:
                best_p = p_load
                best_u = u_candidate
                best_cost = cost
        total_p = best_p.sum()
        is_on = (u_prev > 0).sum()

        return best_p, best_u, best_cost, total_p, is_on




