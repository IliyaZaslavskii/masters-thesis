"""Discounted cash-flow metrics used by the optimization layer."""

from __future__ import annotations

from typing import Sequence, Tuple

import numpy as np
import numpy_financial as npf


class Economy:
    """Calculate NPV, IRR, LCOS and LCOE for a fixed project lifetime."""

    def __init__(self, life_span: int, discount_rate: float | None = None, **legacy: float) -> None:
        """Create a model and validate the horizon and discount rate.
            Параметры (Parameters)
            ----------
            life_span : int
                Жизненный цикл проекта (лет).
            discountRate : float
                ставка дисконтирования (о.е.).
        """
        if discount_rate is None:
            discount_rate = legacy.pop("discountRate", None)
        if legacy or discount_rate is None:
            raise TypeError("Economy requires life_span and discount_rate")
        if life_span < 1:
            raise ValueError("life_span must be positive")
        if discount_rate <= -1:
            raise ValueError("discount_rate must be greater than -1")
        self.life_span = int(life_span)
        self.discount_rate = float(discount_rate)
        self.discountRate = self.discount_rate  # legacy attribute

    def _validate_series(self, values: Sequence[float], name: str) -> np.ndarray:
        """Convert a series to a finite vector of the configured length."""
        array = np.asarray(values, dtype=float)
        if array.size != self.life_span:
            raise ValueError(f"{name} must contain {self.life_span} values")
        if not np.all(np.isfinite(array)):
            raise ValueError(f"{name} contains non-finite values")
        return array

    def npv_calc(self, capex: float, opex: Sequence[float], cash_inflow: float,
                 inflation: float | None = None, escalation: float | None = None,
                 **legacy: float) -> Tuple[np.ndarray, np.ndarray, float]:
        """Return cumulative NPV, cumulative cost and project IRR.
           Параметры (Parameters)
           ----------
           capex : float
               Капитальные затраты, тыс. руб.
               Total capital costs, thousand rubles.
           opex: float
               Затраты на эксплуатацию и техническое обслуживание за время t,
               тыс. руб.
               Operating and maintenance costs over time t, thousand rubles.
           cash_inflow: float
               Сокращение затрат на топливо, тыс. руб
           inflation: float
               Темп инфляции, отн. ед.
               Inflation, p.u.
           escalation: float
               Темп ежегодного изменения стоимости топлива, отн. ед.
               The annual coefficient of correction of the cost of fuel, p.u."""
        inflation = inflation if inflation is not None else legacy.pop("i", None)
        escalation = escalation if escalation is not None else legacy.pop("e", None)
        if legacy or inflation is None or escalation is None:
            raise TypeError("npv_calc requires inflation and escalation")
        if capex < 0:
            raise ValueError("capex must be non-negative")
        operating_cost = self._validate_series(opex, "opex")
        years = np.arange(self.life_span)
        operating_cost = operating_cost * (1 + inflation) ** years
        revenues = cash_inflow * (1 + escalation) ** years
        cash_flow = np.concatenate(([-capex], revenues - operating_cost))
        costs = np.concatenate(([capex], operating_cost))
        npv = np.array([npf.npv(self.discount_rate, cash_flow[:index + 1])
                        for index in range(self.life_span + 1)])
        npc = np.array([npf.npv(self.discount_rate, costs[:index + 1])
                        for index in range(self.life_span + 1)])
        irr = float(npf.irr(cash_flow)) if np.any(cash_flow > 0) else float("nan")
        return npv, npc, irr

    def _levelized_cost(self, capex: float, yearly_costs: np.ndarray,
                        yearly_energy: float) -> float:
        """Discount costs and energy using the same project horizon."""
        if capex < 0 or yearly_energy <= 0:
            raise ValueError("capex must be non-negative and energy must be positive")
        discount = (1 + self.discount_rate) ** np.arange(1, self.life_span + 1)
        return float((capex + np.sum(yearly_costs / discount)) /
                     np.sum(yearly_energy / discount))

    def LCOS_canon(self, capex: float, opex: Sequence[float], kWh: float,
                   i: float) -> float:
        """ Нормированная стоимость накопления энергии
            Levelized cost of storage

            Параметры (Parameters)
            ----------
            capex: float
                Капитальные затраты, тыс. руб.
                Total capital costs, thousand rubles.
            opex: float
                Затраты на эксплуатацию и техническое обслуживание за время t,
                тыс. руб.
                Operating and maintenance costs over time t, thousand rubles.
            kWh: float
                Количество энергии, произведенной СНЭЭ для выравнивания графика
                нагрузки, кВт·ч
                The amount of electricity delivered by the ESS over time t, kWh.
            s: float
                Сокращение затрат на топливо, тыс. руб
            i: float
                Темп инфляции, отн. ед.
                Inflation, p.u.
            e: float
                Темп ежегодного изменения стоимости топлива, отн. ед.
                The annual coefficient of correction of the cost of fuel, p.u."""
        costs = self._validate_series(opex, "opex") * (1 + i) ** np.arange(self.life_span)
        return self._levelized_cost(capex, costs, kWh)

    def LCOS_calc(self, capex: float, opex: Sequence[float], kWh: float,
                  s: float, i: float, e: float) -> float:
        """Calculate LCOS after discounting escalating fuel savings."""
        costs = self._validate_series(opex, "opex") * (1 + i) ** np.arange(self.life_span)
        savings = s * (1 + e) ** np.arange(self.life_span)
        return self._levelized_cost(capex, costs - savings, kWh)

    def LCOE_calc(self, capex: float, opex: Sequence[float], fuel_cost: Sequence[float],
                  energy: Sequence[float]) -> float:
        """Нормированная стоимость электроэнергии
           Levelized Cost of energy.

           Параметры (Parameters)
           ----------
           capex: float
                Капитальные затраты, тыс. руб.
                Total capital costs, thousand rubles.
           opex: float
                Затраты на эксплуатацию и техническое обслуживание за время t,
                тыс. руб.
                Operating and maintenance costs over time t, thousand rubles.
           Ft: float
                Cтоимость дизельного топлива в год за время t, тыс. руб.
                The cost of diesel fuel per year for time t, thousand rubles.
           Et: float
                Полезная отпущенная электроэнергия, кВт
                Net electricity generation, kW"""
        costs = self._validate_series(opex, "opex") + self._validate_series(fuel_cost, "fuel_cost")
        generated = self._validate_series(energy, "energy")
        if np.any(generated <= 0):
            raise ValueError("energy values must be positive")
        discount = (1 + self.discount_rate) ** np.arange(self.life_span)
        return float((capex + np.sum(costs / discount)) / np.sum(generated / discount))
