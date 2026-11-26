"""Objective-function evaluation for battery sizing experiments."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
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
    afc: float
    lcos_canon: float
    baseline_CF: float
    with_battery_CF: float


@dataclass
class FitnessParameters:
    """Общие параметры оборудования и экономики.
        wacc, о.е.
        c_capex, $/кВт·ч
        p_capex, $/кВт
        fuel_price, руб./кг
        lifespan, лет
        inflation, о.е.
        escalation, о.е.
        opex_share, о.е.
        initial_soc, о.е.
        num_dgs, шт
        gen_capacity, кВт
        soc_max, %
        soc_min, %
        eff_ch, %
        eff_ds, %
        cp, %"""

    wacc: float = 0.145
    c_capex: float = 360.0
    p_capex: float = 1400.0
    fuel_price: float = 54.6
    lifespan: int = 20
    penalty: float = 1e9
    value: float = 85.0
    inflation: float = 0.0602
    escalation: float = 0.082
    opex_share: float = 0.02
    initial_soc: float = 0.5
    num_dgs: int = 2
    gen_capacity: float = 110.0
    a1: float = 0.0101
    a2: float = 0.2654
    soc_max: float = 100.0
    soc_min: float = 20.0
    eff_ch: float = 98.0
    eff_ds: float = 98.0
    cp: float = 2.0
    dg_status: Optional[Sequence[float]] = None

@dataclass
class FitnessEvaluator(FitnessParameters):
    """Build a simulation and financial score for each capacity/power pair."""
    economy: Economy = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not 0 <= self.initial_soc <= 1:
            raise ValueError("initial_soc must be in [0, 1]")

        self.dg_status = (
            np.ones(self.num_dgs, dtype=float)
            if self.dg_status is None
            else np.array(self.dg_status, dtype=float, copy=True)
        )

        if self.dg_status.shape != (self.num_dgs,):
            raise ValueError("dg_status must contain one value per generator")

        self.economy = Economy(self.lifespan, self.wacc)

    def evaluate(self, design: Sequence[float], data: pd.DataFrame,
                 baseline_cache: dict | None = None) -> FitnessResult:
        """Evaluate one design; optionally reuse an identical no-BESS dispatch.

        The bounded external cache is keyed by complete load/solar data and all
        DG inputs. It cannot reuse a baseline after changing these inputs. The
        default path remains uncached for existing callers.
        """
        candidate = np.asarray(design, dtype=float)
        if candidate.shape != (2,) or np.any(candidate <= 0):
            raise ValueError("design must contain positive capacity and power")
        size = data.shape[0]
        capacity, power = map(float, candidate)
        battery = Battery(capacity, self.soc_max, self.soc_min, power, power,
                          self.eff_ch, self.eff_ds, self.cp)
        generators = DieselGenerator(self.num_dgs, self.gen_capacity, self.a1, self.a2, self.fuel_price)
        simulation = MicrogridSimulator(data, "Load, kW", "Solar, kW", battery, generators)
        full_solar_power = size * data['Solar, kW'].max()
        if baseline_cache is None:
            baseline = simulation.simulator_3(self.dg_status)
        else:
            digest = hashlib.blake2b(
                data[['Load, kW', 'Solar, kW']].to_numpy(dtype=float).tobytes(),
                digest_size=32,
            ).digest()
            key = (size, digest, self.num_dgs, self.gen_capacity, self.a1,
                   self.a2, self.fuel_price, tuple(self.dg_status))
            baseline = baseline_cache.get(key)
            if baseline is None:
                baseline = simulation.simulator_3(self.dg_status)
                baseline_cache.clear()
                baseline_cache[key] = baseline
        baseline_CF = baseline['net_gen'].sum() / full_solar_power * 100
        with_battery = simulation.simulator_2(self.initial_soc, self.dg_status)
        afc = int(baseline["afc"].sum() - with_battery["afc"].sum())
        with_battery_CF = with_battery['net_gen'].sum() / full_solar_power * 100
        delivered_energy = float(np.sum(with_battery["p_bess_history"][with_battery["p_bess_history"] > 0])) # кВт·ч
        if delivered_energy <= 0:
            return FitnessResult(
                self.penalty, 0.0, 0.0, 0, afc, 0.0,
                float(baseline_CF), float(with_battery_CF)
            )
        savings = (baseline["cost_dgs_history"].sum() - with_battery["cost_dgs_history"].sum()) * 1e-3 # тыс.руб.
        capex = (self.c_capex * self.value * capacity + self.p_capex * self.value * power) * 1e-3 # тыс.руб
        opex = np.full(self.lifespan, capex * self.opex_share) # тыс.руб
        lcos = self.economy.LCOS_calc(capex, opex, delivered_energy, savings, self.inflation, self.escalation) # тыс.руб./кВт·ч
        lcos_canon = self.economy.LCOS_canon(capex, opex, delivered_energy, self.inflation) # тыс.руб./кВт·ч
        if not np.isfinite(lcos) or lcos <= 0:
            return FitnessResult(
                self.penalty, 0.0, 0.0, 0, afc, 0.0,
                float(baseline_CF), float(with_battery_CF)
            )
        npv, _, irr = self.economy.npv_calc(capex, opex, savings, self.inflation, self.escalation)
        hours = int(baseline["is_on_dgs_history"].sum() - with_battery["is_on_dgs_history"].sum())
        return FitnessResult(float(lcos), float(npv[-1]), float(irr), hours, afc, float(lcos_canon), float(baseline_CF), float(with_battery_CF))
