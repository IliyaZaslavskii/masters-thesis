"""Battery energy-storage model used by the microgrid simulator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

BatteryStep = Tuple[float, float, float]


@dataclass(init=False)
class Battery:
    """Класс моделирования системы накопления электрической энергии (СНЭЭ)
       A class that models a battery energy storage system (BESS).

       Параметры (Parameters)
        ----------
        capacity: float
            Номинальная энергоемкость, кВт·ч
            Nominal energy capacity, kWh
        soc_max_percent/soc_max: float
            Максимально допустимый СЗ, %.
            The maximum allowable SOC, %.
        soc_min_percent/soc_min: float
            Минимально допустимый СЗ, %.
            The minimum allowable SOC, %.
        charge_power_limit/r_power_ch: float
            Номинальная предельная мощность заряда, кВт
        discharge_power_limit/r_power_ds: float
            Номинальная предельная мощность разряда, кВт
        charge_efficiency_percent/eff_ch: float
            Эффективность заряда, %
            roundtrip efficiency charging, %.
        discharge_efficiency_percent/eff_ds: float
            Эффективность разряда, %
            roundtrip efficiency discharging, %.
        self_discharge_percent/cp: float
            Саморазряд СНЭЭ, %
            self-discharge of BESS, %
       """

    capacity: float
    soc_max_percent: float
    soc_min_percent: float
    charge_power_limit: float
    discharge_power_limit: float
    charge_efficiency_percent: float
    discharge_efficiency_percent: float
    self_discharge_percent: float

    def __init__(
        self,
        capacity: float,
        soc_max_percent: float | None = None,
        soc_min_percent: float | None = None,
        charge_power_limit: float | None = None,
        discharge_power_limit: float | None = None,
        charge_efficiency_percent: float | None = None,
        discharge_efficiency_percent: float | None = None,
        self_discharge_percent: float | None = None,
        **legacy: float,
    ) -> None:
        """Initialize the battery using descriptive or legacy argument names."""
        values = {
            "soc_max_percent": soc_max_percent,
            "soc_min_percent": soc_min_percent,
            "charge_power_limit": charge_power_limit,
            "discharge_power_limit": discharge_power_limit,
            "charge_efficiency_percent": charge_efficiency_percent,
            "discharge_efficiency_percent": discharge_efficiency_percent,
            "self_discharge_percent": self_discharge_percent,
        }
        aliases = {
            "soc_max": "soc_max_percent",
            "soc_min": "soc_min_percent",
            "r_power_ch": "charge_power_limit",
            "r_power_ds": "discharge_power_limit",
            "eff_ch": "charge_efficiency_percent",
            "eff_ds": "discharge_efficiency_percent",
            "cp": "self_discharge_percent",
        }
        for old_name, new_name in aliases.items():
            if values[new_name] is None and old_name in legacy:
                values[new_name] = legacy.pop(old_name)
        if legacy or any(value is None for value in values.values()):
            raise TypeError("Battery requires SOC, power and efficiency parameters")
        self.capacity = float(capacity)
        for name, value in values.items():
            setattr(self, name, float(value))
        self.__post_init__()

    def __post_init__(self) -> None:
        """Validate inputs and expose legacy derived attributes."""
        for name, value in {"capacity": self.capacity, "charge_power_limit": self.charge_power_limit,
                            "discharge_power_limit": self.discharge_power_limit}.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if not 0 <= self.soc_min_percent <= self.soc_max_percent <= 100:
            raise ValueError("SOC limits must satisfy 0 <= min <= max <= 100")
        for name, value in {"charge_efficiency_percent": self.charge_efficiency_percent,
                            "discharge_efficiency_percent": self.discharge_efficiency_percent,
                            "self_discharge_percent": self.self_discharge_percent}.items():
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be in the range [0, 100]")
        if self.charge_efficiency_percent == 0 or self.discharge_efficiency_percent == 0:
            raise ValueError("Charge and discharge efficiencies must be non-zero")
        self.soc_max = self.soc_max_percent / 100
        self.soc_min = self.soc_min_percent / 100
        self.r_power_ch = self.charge_power_limit
        self.r_power_ds = self.discharge_power_limit
        self.eff_ch = self.charge_efficiency_percent / 100
        self.eff_ds = self.discharge_efficiency_percent / 100
        self.cp = self.self_discharge_percent / 100
        self.aux_p_ch = self.cp * self.capacity + self.r_power_ch * (1 - self.eff_ch)
        self.aux_p_ds = self.cp * self.capacity + self.r_power_ds * (1 - self.eff_ds) / self.eff_ds

    def get_passport_parameters(self) -> Dict[str, float]:
        """Вернуть паспортные параметры СНЭЭ
           Return passport and derived battery parameters."""
        return {"Номинальная энергоемкость, кВт·ч": round(self.capacity, 2),
                "Максимальная степень заряда (СЗ_макс), %": round(self.soc_max * 100, 2),
                "Минимальная степень заряда (СЗ_мин), %": round(self.soc_min * 100, 2),
                "Номинальная мощность заряда, кВт": round(self.r_power_ch, 2),
                "Номинальная мощность разряда, кВт": round(self.r_power_ds, 2),
                "Эффективность заряда, %": round(self.eff_ch * 100, 2),
                "Эффективность разряда, %": round(self.eff_ds * 100, 2),
                "Коэффициент саморазряда, %": round(self.cp * 100, 2),
                "Потери мощности при заряде, кВт": round(self.aux_p_ch, 2),
                "Потери мощности при разряде, кВт": round(self.aux_p_ds, 2)}

    def _validate_soc(self, soc: float) -> None:
        """Validate a normalized state-of-charge value."""
        if not 0 <= soc <= 1:
            raise ValueError("SOC must be in the range [0, 1]")

    def charge(self, net_power: float, soc: float) -> BatteryStep:
        """Функция заряда батареи
           Battery charge function.

           Параметры (Parameters)
            ----------
            net_power: float
                Мощность  из сети, кВт.
                Network Power, kW.
            soc: float
                Доcтупный СЗ.
                Accessible SOC.
            Возвращает (Returns)
            ----------
            p_ch: float
                Мощность зарядки, кВт.
                Charging power, kW.
            e_new: float
                Доступная энергия после заряда.
                Available energy after charging.
            soc_new: float
                Доступный уровень СЗ после заряда.
                    """
        self._validate_soc(soc)
        if net_power <= self.aux_p_ch or soc >= self.soc_max:
            return 0.0, self.capacity * soc, soc
        available_power = min(float(net_power), self.r_power_ch)
        required_power = self.capacity * (self.soc_max - soc) / self.eff_ch + self.cp * self.capacity
        charge_power = -min(required_power, available_power)
        new_energy = self.capacity * soc - charge_power * self.eff_ch - self.cp * self.capacity
        return charge_power, new_energy, new_energy / self.capacity

    def discharge(self, net_power: float, soc: float) -> BatteryStep:
        """Функция разряда батареи
           Battery discharge function.

           Параметры (Parameters)
            ----------
            net_power: float
                Мощность  из сети, кВт.
                Network Power, kW.
            soc: float
                Доcтупный СЗ.
                Accessible SOC.
            Возвращает (Returns)
            ----------
            p_ds: float
                Мощность разряда, кВт.
                Discharge power, kW.
            e_new: float
                Доступная энергия после разряда.
                Available energy after discharge.
            soc_new: float
                Доступный уровень СЗ после разряда.
                SOC after discharge."""
        self._validate_soc(soc)
        if net_power <= 0 or self.capacity * (soc - self.soc_min) <= self.aux_p_ds:
            return 0.0, self.capacity * soc, soc
        available_power = min(float(net_power), self.r_power_ds)
        deliverable_power = self.capacity * (soc - self.soc_min) * self.eff_ds - self.cp * self.capacity
        discharge_power = min(deliverable_power, available_power)
        new_energy = self.capacity * soc - discharge_power / self.eff_ds - self.cp * self.capacity
        return discharge_power, new_energy, new_energy / self.capacity

    def soc_status(self, soc: float) -> str:
        """Функция состояния батареи
           Battery status function."""
        self._validate_soc(soc)
        if soc >= self.soc_max:
            return "Возможен только разряд"
        if soc <= self.soc_min:
            return "Возможен только заряд"
        return "Заряд и Разряд возможен"
