"""Diesel-generator dispatch and fuel-consumption model."""

from __future__ import annotations

from itertools import combinations
from typing import Tuple

import numpy as np


class DieselGenerator:
    """Класс моделирования работы дизель-генератора
       A class that models a diesel generator (DG)."""

    def __init__(self, num_dgs: int | None = None, gen_capacity: float | None = None,
                 a1: float | None = None, a2: float | None = None,
                 fuel_price: float | None = None, **legacy: float) -> None:
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
        if num_dgs is None:
            num_dgs = legacy.pop("num_DGs", None)
        if legacy or any(value is None for value in (num_dgs, gen_capacity, a1, a2, fuel_price)):
            raise TypeError("DieselGenerator requires fleet and fuel parameters")
        if num_dgs < 1 or int(num_dgs) != num_dgs:
            raise ValueError("num_dgs must be a positive integer")
        if gen_capacity <= 0 or a1 < 0 or a2 < 0 or fuel_price < 0:
            raise ValueError("Generator capacity and coefficients must be non-negative")
        self.n = int(num_dgs)
        # Расчетные параметры
        # Calculated parameters
        self.gen_capacity, self.a1, self.a2, self.fuel_price = gen_capacity, a1, a2, fuel_price
        self.p_min, self.p_max = 0.35 * gen_capacity, 0.95 * gen_capacity
        self.power_outputs = np.ones(self.n, dtype=float)

    def get_parameters(self) -> Tuple[np.ndarray, int]:
        """Получить массив дизель-генераторов
           Get an array of diesel generators.
           """
        return self.power_outputs * self.gen_capacity, self.n

    def calculate_fuel_consumption(self, generate_array: np.ndarray,
                                   fuel_density: float = 860.0,
                                   lower_heating_value: float = 43.2,
                                   **legacy: float
                                   ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Зависимость расхода топлива от номинальной мощности и текущей нагрузки ДГУ
           The fuel consumption of the diesel generator (DG).

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
                sfc: np.ndarray
                    Удельный расход условного топлива, о.е.
                    Specific fuel consumption, l/kWh
                afc: np.ndarray
                    Абсолютный расход топлива, кг
                    Absolute fuel consumption, kg
                efficiency: np.ndarray
                    Электрический КПД ДГУ, о.е. (0..1). Для генераторов,
                    не несущих нагрузку (generate_array <= 0), КПД равен 0.
                    Electrical efficiency of the DG, p.u. (0..1). For idle
                    generators (generate_array <= 0), efficiency is 0."""
        fuel_density = legacy.pop("p", fuel_density)
        lower_heating_value = legacy.pop("LHV", lower_heating_value)
        if legacy:
            raise TypeError(f"Unexpected arguments: {', '.join(legacy)}")
        power = np.asarray(generate_array, dtype=float)
        if np.any(power < 0) or np.any(power > self.gen_capacity):
            raise ValueError("Generator output must be in [0, gen_capacity]")
        if fuel_density <= 0 or lower_heating_value <= 0:
            raise ValueError("Fuel density and lower heating value must be positive")
        sfc = np.zeros_like(power)
        afc = np.zeros_like(power)
        efficiency = np.zeros_like(power)
        active = power > 0
        load_fraction = power[active] / self.gen_capacity # текущая загрузка ДГУ относительно номинальной мощности от 0 до 1
        sfc[active] = self.a1 / load_fraction + self.a2
        afc[active] = fuel_density * sfc[active] * power[active] * 1e-3
        efficiency[active] = 3.6 * power[active] / (afc[active] * lower_heating_value)
        return sfc, afc, efficiency

    def total_cost(self, power: np.ndarray, u: np.ndarray,
                   u_prev: np.ndarray) -> float:
        """ Возвращает полную стоимость топлива
            Return fuel cost for a dispatch.

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
                Previous status of generators (1 - on, 0 - off)."""
        _, fuel_consumption, _ = self.calculate_fuel_consumption(power)
        return float(np.sum(fuel_consumption) * self.fuel_price)

    def optimize_dgs(self, previous_status: np.ndarray, load: float
                     ) -> Tuple[np.ndarray, np.ndarray, float, float, int]:
        """Оптимизация распределения нагрузки между генераторами.
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
               powers: np.ndarray
                   Оптимальное распределение мощностей, кВт
               statuses: np.ndarray
                   Оптимальное состояние генераторов
               cost: np.ndarray
                   Минимальная стоимость работы, руб
               powers: float
                   Суммарная выдаваемая мощность, кВт
               statuses: int
                   Количество работающих генераторов."""
        previous_status = np.asarray(previous_status)
        if previous_status.shape != (self.n,):
            raise ValueError(f"previous_status must contain {self.n} values")
        if load < 0:
            raise ValueError("load must be non-negative")
        if load > self.n * self.p_max:
            raise ValueError(f"load {load} exceeds fleet capacity {self.n * self.p_max}")
        if load == 0:
            return self._shutdown_dgs(previous_status)
        best = None
        minimum_units = max(1, int(np.ceil(load / self.p_max)))
        for units in range(minimum_units, self.n + 1):
            unit_power = max(self.p_min, min(self.p_max, load / units))
            powers = np.zeros(self.n)
            powers[:units] = unit_power
            if powers.sum() + 1e-9 < load:
                continue
            statuses = np.zeros(self.n, dtype=int)
            statuses[:units] = 1
            candidate = (self.total_cost(powers, statuses, previous_status), powers, statuses)
            if best is None or candidate[0] < best[0]:
                best = candidate
        if best is None:
            raise RuntimeError("No feasible generator dispatch was found")
        cost, powers, statuses = best
        return powers, statuses, float(cost), float(powers.sum()), int(statuses.sum())

    # Legacy method name retained for existing notebooks.
    optimize_DGs = optimize_dgs

    def _shutdown_dgs(self, previous_status: np.ndarray):
        """Остановка ДГУ и расчет стоимости этого действия
           Stopping diesel generators and calculating the cost of this action."""
        previous_status = np.asarray(previous_status)
        statuses = np.zeros(self.n, dtype=int)
        powers = np.zeros(self.n)
        return powers, statuses, self.total_cost(powers, statuses, previous_status), 0.0, 0

    def shutdown(self, previous_status: np.ndarray):
        """Public, descriptive alias for the legacy shutdown helper."""
        return self._shutdown_dgs(previous_status)
