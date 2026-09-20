import numpy as np
import pandas as pd
from typing import Optional
from dataclasses import dataclass
from src.components.Battery import Battery
from src.components.DieselGenerator import DieselGenerator
from src.simulator.MicrogridSimulator import MicrogridSimulator
from src.financial import Economy

@dataclass(frozen=True)
class FitnessResult:
    lcos: float       # LCOS, руб./кВт·ч
    npv: float        # Чистая дисконтированный доход, тыс. руб.
    irr: float        # Внутренняя норма доходности
    hours: int        # Сэкономленные часы работы ДГ


class FitnessEvaluator:
    """

    """
    def __init__(
        self,
        wacc: float = 0.145,
        c_capex: float = 360.0,
        p_capex: float = 1400.0,
        fuel_price: float = 54.6,
        lifespan: int = 20,
        penalty: float = 1e9,
        value: float = 85.0,
        inflation: float = 0.0602,
        escalation: float = 0.082,
        opex_share: float = 0.02,
        initial_soc: float = 0.5,
        # Параметры ДГ
        num_dgs: int = 4,
        gen_capacity: float = 110.0,
        a1: float = 0.0101,
        a2: float = 0.2654,
        # Параметры СНЭЭ
        soc_max: float = 100.0,
        soc_min: float = 20.0,
        eff_ch: float = 98.0,
        eff_ds: float = 98.0,
        cp: float = 2.0,
        dg_status: Optional[np.ndarray] = np.array([1, 1, 0, 0], dtype=np.float64),
        ) -> None:

        self.wacc = wacc
        self.c_capex = c_capex
        self.p_capex = p_capex
        self.fuel_price = fuel_price
        self.lifespan = lifespan
        self.penalty = penalty
        self.value = value
        self.inflation = inflation
        self.escalation = escalation
        self.opex_share = opex_share
        self.initial_soc = initial_soc
        # Параметры ДГ
        self.num_dgs = num_dgs
        self.gen_capacity = gen_capacity
        self.a1 = a1
        self.a2 = a2
        # Параметры СНЭЭ
        self.soc_max = soc_max
        self.soc_min = soc_min
        self.eff_ch = eff_ch
        self.eff_ds = eff_ds
        self.cp = cp
        self.dg_status = dg_status

        self.economy = Economy.Economy(self.lifespan, self.wacc)

    def evaluate(self, x: np.ndarray, df: pd.DataFrame) -> FitnessResult:
        """
        """
        capacity, power = float(x[0]), float(x[1])

        battery = Battery(
            capacity=capacity,
            soc_max=self.soc_max,
            soc_min=self.soc_min,
            r_power_ch=power,
            r_power_ds=power,
            eff_ch=self.eff_ch,
            eff_ds=self.eff_ds,
            cp=self.cp,

        )
        dg = DieselGenerator(
            num_DGs=self.num_dgs,
            gen_capacity=self.gen_capacity,
            a1=self.a1,
            a2=self.a2,
            fuel_price=self.fuel_price,
        )

        sim = MicrogridSimulator(df, 'Load, kW', 'Solar, kW', battery, dg)

        baseline = sim.simulator_3(self.dg_status)
        with_bess = sim.simulator_2(
            initial_soc=self.initial_soc,
            val_dgs=self.dg_status
        )

        kwh = np.sum(
            with_bess['p_bess_history'][with_bess['p_bess_history'] > 0])
        if kwh == 0:
            return FitnessResult(self.penalty, 0.0, 0.0, 0)

        savings = (
            baseline["cost_dgs_history"].sum()
            - with_bess["cost_dgs_history"].sum()
        ) * -1e-3

        capex = (
            self.c_capex * self.value * capacity
            + self.p_capex * self.value * power
        ) * 1e-3
        opex = np.ones(self.lifespan) * capex *  self.opex_share

        lcos = self.economy.LCOS_calc(
            capex=capex,
            opex=opex,
            kWh=kwh,
            s=savings,
            i=self.inflation,
            e=self.escalation
        )

        if not np.isfinite(lcos) or lcos <= 0:
            return FitnessResult(self.penalty, 0.0, 0.0, 0)

        npv, _, irr = self.economy.npv_calc(
            capex=capex,
            opex=opex,
            cash_inflow=savings,
            i=self.inflation,
            e=self.escalation
        )

        hours = int(baseline['is_on_dgs_history'].sum()
                    - with_bess['is_on_dgs_history'].sum())

        return FitnessResult(
            lcos=lcos,
            npv=npv[-1],
            irr=irr,
            hours=hours
        )