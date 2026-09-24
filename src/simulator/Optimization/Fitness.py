"""Objective-function evaluation for battery sizing experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from src.components.Battery import Battery
from src.components.DieselGenerator import DieselGenerator
from src.financial.Economy import Economy
from src.simulator.MicrogridSimulator import MicrogridSimulator


@dataclass(frozen=True)
class FitnessResult:
    """Metrics returned for one candidate battery design."""

    lcos: float
    npv: float
    irr: float
    hours: int


class FitnessEvaluator:
    """Build a simulation and financial score for each capacity/power pair."""

    def __init__(self, wacc: float = 0.145, c_capex: float = 360.0,
                 p_capex: float = 1400.0, fuel_price: float = 54.6,
                 lifespan: int = 20, penalty: float = 1e9, value: float = 85.0,
                 inflation: float = 0.0602, escalation: float = 0.082,
                 opex_share: float = 0.02, initial_soc: float = 0.5,
                 num_dgs: int = 4, gen_capacity: float = 110.0,
                 a1: float = 0.0101, a2: float = 0.2654,
                 soc_max: float = 100.0, soc_min: float = 20.0,
                 eff_ch: float = 98.0, eff_ds: float = 98.0, cp: float = 2.0,
                 dg_status: Optional[Sequence[float]] = None) -> None:
        """Store economic and equipment parameters with safe defaults."""
        if not 0 <= initial_soc <= 1:
            raise ValueError("initial_soc must be in [0, 1]")
        self.wacc, self.c_capex, self.p_capex = wacc, c_capex, p_capex
        self.fuel_price, self.lifespan, self.penalty = fuel_price, lifespan, penalty
        self.value, self.inflation, self.escalation, self.opex_share = value, inflation, escalation, opex_share
        self.initial_soc = initial_soc
        self.num_dgs, self.gen_capacity, self.a1, self.a2 = num_dgs, gen_capacity, a1, a2
        self.soc_max, self.soc_min, self.eff_ch, self.eff_ds, self.cp = soc_max, soc_min, eff_ch, eff_ds, cp
        self.dg_status = np.asarray(dg_status if dg_status is not None else [1, 1, 0, 0], dtype=float)
        if self.dg_status.size != num_dgs:
            raise ValueError("dg_status length must equal num_dgs")
        self.economy = Economy(lifespan, wacc)

    def evaluate(self, design: Sequence[float], data: pd.DataFrame) -> FitnessResult:
        """Evaluate one ``(capacity, power)`` design against load and solar data."""
        candidate = np.asarray(design, dtype=float)
        if candidate.shape != (2,) or np.any(candidate <= 0):
            raise ValueError("design must contain positive capacity and power")
        capacity, power = map(float, candidate)
        battery = Battery(capacity, self.soc_max, self.soc_min, power, power,
                          self.eff_ch, self.eff_ds, self.cp)
        generators = DieselGenerator(self.num_dgs, self.gen_capacity, self.a1, self.a2, self.fuel_price)
        simulation = MicrogridSimulator(data, "Load, kW", "Solar, kW", battery, generators)
        baseline = simulation.simulator_3(self.dg_status)
        with_battery = simulation.simulator_2(self.initial_soc, self.dg_status)
        delivered_energy = float(np.sum(with_battery["p_bess_history"][with_battery["p_bess_history"] > 0]))
        if delivered_energy <= 0:
            return FitnessResult(self.penalty, 0.0, 0.0, 0)
        savings = (baseline["cost_dgs_history"].sum() - with_battery["cost_dgs_history"].sum()) * -1e-3
        capex = (self.c_capex * self.value * capacity + self.p_capex * self.value * power) * 1e-3
        opex = np.full(self.lifespan, capex * self.opex_share)
        lcos = self.economy.LCOS_calc(capex, opex, delivered_energy, savings, self.inflation, self.escalation)
        if not np.isfinite(lcos) or lcos <= 0:
            return FitnessResult(self.penalty, 0.0, 0.0, 0)
        npv, _, irr = self.economy.npv_calc(capex, opex, savings, self.inflation, self.escalation)
        hours = int(baseline["is_on_dgs_history"].sum() - with_battery["is_on_dgs_history"].sum())
        return FitnessResult(float(lcos), float(npv[-1]), float(irr), hours)
