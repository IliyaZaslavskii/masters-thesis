"""Time-series dispatch strategies for a solar-battery-diesel microgrid."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd


class MicrogridSimulator:
    """ Класс моделирования алгоритма управления гибридным комплексом
        A class for modeling a hybrid complex control algorithm."""

    def __init__(self, data: pd.DataFrame, load_column: str, gen_column: str,
                 bess: Any, dgs: Any) -> None:
        """
        Параметры (Parameters)
        ----------
        df : pd.DataFrame
            Временной ряд нагрузки и генерации.
        load_column : str
            Название столбца нагрузки (кВт).
        gen_column : str
            Название столбца генерации (кВт).
        bess : object
            Класс моделирования системы накопления электрической энергии (СНЭЭ).
        dgs : object
            Класс моделирования работы дизель-генератора.
        """
        missing = {load_column, gen_column} - set(data.columns)
        if missing:
            raise ValueError(f"Missing columns: {sorted(missing)}")
        if data.empty:
            raise ValueError("data must contain at least one row")
        self.load = data[load_column].to_numpy(dtype=float)
        self.gen = data[gen_column].to_numpy(dtype=float)
        if np.any(~np.isfinite(self.load)) or np.any(~np.isfinite(self.gen)):
            raise ValueError("load and generation must contain finite values")
        if np.any(self.load < 0) or np.any(self.gen < 0):
            raise ValueError("load and generation cannot be negative")
        self.n, self.bess, self.dgs = len(self.load), bess, dgs
        self.capacity = float(bess.capacity)

    def _empty_history(self, with_battery: bool) -> Dict[str, np.ndarray]:
        """Allocate all result arrays once to avoid duplicated strategy setup."""
        history = {"new_gen": self.gen.copy(), "net_gen": np.zeros(self.n),
                   "shunt_gen": np.zeros(self.n), "p_dgs_history": np.zeros(self.n),
                   "net_dgs": np.zeros(self.n), "shunt_dgs": np.zeros(self.n),
                   "cost_dgs_history": np.zeros(self.n), "is_on_dgs_history": np.zeros(self.n, dtype=np.int8),
                   "p_dgs_unit_history": np.zeros((self.n, self.dgs.n)), "new_net_power": np.zeros(self.n)}
        if with_battery:
            history.update({"capacity_history": np.zeros(self.n + 1), "soc_history": np.zeros(self.n + 1),
                            "p_bess_history": np.zeros(self.n)})
        return history

    def _record(self, history: Dict[str, np.ndarray], index: int, total_power: float,
                generator_power: np.ndarray, generator_status: np.ndarray,
                cost: float, battery_power: float = 0.0,
                soc: float | None = None, energy: float | None = None) -> None:
        """Record one dispatch step and compute unmet/excess power consistently."""
        difference = self.load[index] - total_power - battery_power
        if difference < 0:
            history["shunt_dgs"][index] = -difference
            history["net_gen"][index] = history["shunt_gen"][index] = 0
        else:
            history["net_gen"][index] = difference
            history["shunt_gen"][index] = self.gen[index] - difference
        history["p_dgs_history"][index] = total_power
        history["net_dgs"][index] = total_power - history["shunt_dgs"][index]
        history["cost_dgs_history"][index] = cost
        history["is_on_dgs_history"][index] = int(np.sum(generator_status > 0))
        history["p_dgs_unit_history"][index] = generator_power
        history["new_net_power"][index] = history["net_gen"][index] + history["net_dgs"][index] + battery_power - self.load[index]
        if "p_bess_history" in history:
            history["p_bess_history"][index] = battery_power
        if soc is not None:
            history["soc_history"][index + 1] = soc
        if energy is not None:
            history["capacity_history"][index + 1] = energy

    def _run(self, initial_soc: float, generator_status: np.ndarray,
             economic: bool = False, forecast: bool = False) -> Dict[str, np.ndarray]:
        """Execute a battery strategy; ``economic`` compares battery and fuel costs."""
        if not 0 <= initial_soc <= 1:
            raise ValueError("initial_soc must be in [0, 1]")
        status = np.asarray(generator_status, dtype=float)
        if status.shape != (self.dgs.n,):
            raise ValueError(f"generator_status must contain {self.dgs.n} values")
        history = self._empty_history(True)
        history["soc_history"][0], history["capacity_history"][0] = initial_soc, initial_soc * self.capacity
        current_status = status.copy()
        for index in range(self.n):
            soc = history["soc_history"][index]
            net_power = self.gen[index] - self.load[index]
            can_shutdown = not forecast or self._can_shutdown(index)
            battery_power, next_energy, next_soc = 0.0, history["capacity_history"][index], soc
            can_charge = self.bess.soc_status(soc) != "Возможен только разряд"
            can_discharge = self.bess.soc_status(soc) != "Возможен только заряд"
            if net_power >= 0: # Энергия ФЭС больше или равна нагрузке
                if can_charge: # СНЭЭ заряжается от ФЭС
                    battery_power, next_energy, next_soc = self.bess.charge(net_power, soc)
                if can_charge and (not forecast or can_shutdown):
                    dispatch = self.dgs.shutdown(current_status)
                else: # Балласт от ФЭС
                    dispatch = self.dgs.optimize_dgs(current_status, 0.0)
            else: # Энергия ФЭС меньше нагрузки
                if can_discharge:
                    candidate = self.bess.discharge(-net_power, soc)
                else:
                    candidate = (0.0, next_energy, next_soc)
                if can_discharge and economic:
                    if net_power + candidate[0] == 0: # Энергоемкости СНЭЭ достаточно для покрытия остаточной нагрузки
                        battery_power, next_energy, next_soc = candidate
                        dispatch = (self.dgs.shutdown(current_status) if can_shutdown
                                    else self.dgs.optimize_dgs(current_status, 0.0))
                    else: # Оптимальная загрузка генератора
                        with_battery = self.dgs.optimize_dgs(current_status, -net_power - candidate[0])
                        without_battery = self.dgs.optimize_dgs(current_status, -net_power)
                        if with_battery[2] < without_battery[2]:
                            battery_power, next_energy, next_soc, dispatch = candidate[0], candidate[1], candidate[2], with_battery
                        else:
                            dispatch = without_battery
                            excess = dispatch[3] + net_power
                            if excess > 0:
                                battery_power, next_energy, next_soc = self.bess.charge(excess, soc)
                else: # Разряд невозможен
                    battery_power, next_energy, next_soc = candidate
                    if net_power + battery_power == 0:
                        dispatch = (self.dgs.shutdown(current_status) if can_shutdown
                                    else self.dgs.optimize_dgs(current_status, 0.0))
                    else:
                        dispatch = self.dgs.optimize_dgs(
                            current_status, -net_power - battery_power
                        )
            power, current_status, cost, total_power, _ = dispatch
            self._record(history, index, total_power, power, current_status, cost, battery_power, next_soc, next_energy)
        for key in ("capacity_history", "soc_history"):
            history[key] = history[key][1:]
        return history

    def simulator_1(self, initial_soc: float, val_dgs: np.ndarray) -> Dict[str, np.ndarray]:
        """ Приоритетное использование СНЭЭ
            Run priority BESS dispatch."""
        return self._run(initial_soc, val_dgs)

    def simulator_2(self, initial_soc: float, val_dgs: np.ndarray) -> Dict[str, np.ndarray]:
        """Run fuel-cost-aware battery dispatch."""
        return self._run(initial_soc, val_dgs, economic=True)

    def _can_shutdown(self, index: int) -> bool:
        """Allow shutdown only when the next 24 hours remain renewable-surplus."""
        return bool(np.all(self.gen[index + 1:min(index + 24, self.n)] >= self.load[index + 1:min(index + 24, self.n)]))

    def simulator_4(self, initial_soc: float, val_dgs: np.ndarray) -> Dict[str, np.ndarray]:
        """Run cost-aware dispatch with a 24-hour shutdown forecast."""
        return self._run(initial_soc, val_dgs, economic=True, forecast=True)

    def simulator_3(self, val_dgs: np.ndarray) -> Dict[str, np.ndarray]:
        """Без СНЭЭ
           Run the baseline dispatch without a battery."""
        history = self._empty_history(False)
        current_status = np.asarray(val_dgs, dtype=float)
        if current_status.shape != (self.dgs.n,):
            raise ValueError(f"val_dgs must contain {self.dgs.n} values")
        for index, (solar, load) in enumerate(zip(self.gen, self.load)):
            net_power = solar - load
            dispatch = self.dgs.optimize_dgs(
                current_status, 0.0 if net_power >= 0 else -net_power
            )
            power, current_status, cost, total_power, _ = dispatch
            if net_power >= 0:
                difference = total_power - load
                if difference >= 0:
                    history["shunt_gen"][index] = solar
                    history["net_gen"][index] = 0.0
                    history["shunt_dgs"][index] = difference
                else:
                    history["shunt_gen"][index] = solar + difference
                    history["net_gen"][index] = -difference
            else:
                difference = load - total_power
                if difference < 0:
                    history["shunt_dgs"][index] = -difference
                else:
                    history["shunt_gen"][index] = solar - difference
                    history["net_gen"][index] = difference
            history["new_gen"][index] = history["net_gen"][index] + history["shunt_gen"][index]
            history["p_dgs_history"][index] = total_power
            history["cost_dgs_history"][index] = cost
            history["is_on_dgs_history"][index] = int(np.sum(current_status > 0))
            history["p_dgs_unit_history"][index] = power
            history["net_dgs"][index] = total_power - history["shunt_dgs"][index]
            history["new_net_power"][index] = history["net_gen"][index] + history["net_dgs"][index] - load
        return history
