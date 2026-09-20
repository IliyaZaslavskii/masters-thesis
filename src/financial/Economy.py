import numpy_financial as npf
import numpy as np
class Economy:
    def __init__(self,
                 life_span: int,
                 discountRate: float,
                 ):
        self.life_span = life_span
        self.discountRate = discountRate

    def npv_calc(self,
                 capex,
                 opex,
                 cash_inflow,
                 i,
                 e):
        opex = [opex[t] * ((1 + i) ** t) for t in range(self.life_span)]
        revenues = np.array([
            cash_inflow * (1 + e) ** t
            for t in range(self.life_span)
        ])
        fcf = np.concatenate((
            [-capex],
            revenues - opex
        ))
        costs = np.concatenate((
            [capex],
            opex
        ))

        npv = np.array([
            npf.npv(self.discountRate, fcf[:i + 1])
            for i in range(self.life_span + 1)
        ])
        npc = np.array([
            npf.npv(self.discountRate, costs[:i + 1])
            for i in range(self.life_span + 1)
        ])
        irr = npf.irr(fcf)

        return npv, npc, irr

    def LCOS_canon(self,
                 capex,
                 opex,
                  kWh,
                  i
                   ):
        """
        Нормированная стоимость накопления энергии
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
            The annual coefficient of correction of the cost of fuel, p.u.

        """

        numerator = capex + sum(
            (opex[t] * (1 + i) ** t)
            / (1 + self.discountRate) ** (t + 1)
            for t in range(self.life_span)
        )

        denominator = sum(
            kWh / (1 + self.discountRate) ** (t + 1)
            for t in range(self.life_span)
        )

        LCOS = numerator / denominator

        return LCOS

    def LCOS_calc(self,
                 capex,
                 opex,
                  kWh,
                  s,
                  i,
                  e):
        """
        Нормированная стоимость накопления энергии
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
            The annual coefficient of correction of the cost of fuel, p.u.
        """

        numerator = capex + sum(
            (opex[t] * (1 + i) ** t - s * (1 + e) ** t)
            / (1 + self.discountRate) ** (t + 1)
            for t in range(self.life_span)
        )

        denominator = sum(
            kWh / (1 + self.discountRate) ** (t + 1)
            for t in range(self.life_span)
        )

        LCOS = numerator / denominator

        return LCOS

    def LCOE_calc(self,
                  capex,
                  opex,
                  Ft,
                  Et):
        """
        Нормированная стоимость электроэнергии
        Levelized Cost of energy

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
            Net electricity generation, kW

        """
        numerator = capex + sum(
            (opex[t] + Ft[t]) / (1 + self.discountRate) ** t for t in
             range(self.life_span)
        )

        # Знаменатель формулы LCOE (сумма дисконтированной электроэнергии)
        denominator = sum(
            Et[t] / (1 + self.discountRate) ** t for t in range(self.life_span)
        )

        # Рассчет LCOE
        LCOE = numerator / denominator

        return LCOE
