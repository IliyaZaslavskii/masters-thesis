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
                 cash_inflow):
        costi = np.hstack([capex, opex])
        P_pv = np.tile((cash_inflow), self.life_span)
        revenues = np.sum(np.reshape(P_pv, (self.life_span, -1)), axis=1)
        fcf = np.hstack([0, revenues]) - costi
        npv = np.array([npf.npv(self.discountRate, fcf[:i]) for i in
                        np.arange(1, self.life_span + 2)])      
        npc = np.array([npf.npv(self.discountRate, costi[:i]) for i in
                        np.arange(1, self.life_span + 2)])
        irr = npf.irr(fcf)
        return npv, npc, irr

    def LCOS_calc(self,
                 capex,
                 opex,
                  aux,
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
        aux: float
            Стоимость электроэнергии на собственные нужды СНЭЭ за время t,
            тыс. руб.
            The cost of electricity stored over time t, thousand rubles.
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
            Темп ежегодного изменения стоимости электроэнергии, отн. ед.
            The annual coefficient of correction of the cost of electricity, p.u.

        """

        numerator = capex + np.sum([
            (opex[t] * (1 + i) ** t + aux[t] * (1 + e) ** t) / (1 +
                                                                self.discountRate) ** t
            for t in range(self.life_span) ]) - s * self.life_span


        denominator = np.sum([
            (kWh[t] * (1 + e) ** t) / (1 + self.discountRate) ** t
            for t in range(self.life_span)
        ])

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
        """
        numerator = np.sum(
            [(capex + opex[t] + Ft[t]) / (1 + self.discountRate) ** t for t in range(self.life_span)])

        # Знаменатель формулы LCOE (сумма дисконтированной электроэнергии)
        denominator = np.sum([Et[t] / (1 + self.discountRate) ** t for t in range(self.life_span)])

        # Рассчет LCOE
        LCOE = numerator / denominator

        return LCOE
