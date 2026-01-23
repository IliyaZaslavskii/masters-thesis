class Battery:
    """
    Класс моделирования системы накопления электрической энергии (СНЭЭ)
    A class that models a storage battery energy storage system (BESS).
    Параметры (Parameters)
    ----------
    e_cr: float
        Номинальная энергоемкость, кВт·ч
        Nominal energy capacity, kWh
    soc_max: float
        Максимально допустимый СЗ. По умолчанию 1.0
        The maximum allowable SOC is 1.0 by default.
    soc_min:
        Минимально допустимый СЗ. По умолчанию 0.0
        The minimum allowable SOC is 0.0 by default.
    r_power_ch: float
        Максимальная мощность зарядки, кВт
    r_power_ds: float
        Максимальная мощность разрядки, кВт
    eff: float
        Эффективность заряда-разряда (0 < eff ≤ 1)
        roundtrip efficiency (0 < eff ≤ 1).
    aux_power: float
        Мощность потребления вспомогательной подсистемы, кВт
        auxiliary power consumption, kWh

    Returns

    ----------

    """
    def __init__(self, e_cr, soc_max, soc_min, r_power_ch, r_power_ds, eff, aux_power):
        self.e_cr = e_cr
        self.soc_max = soc_max
        self.soc_min = soc_min
        self.r_power_ch = r_power_ch
        self.r_power_ds = r_power_ds
        self.eff = eff
        self.aux_power = aux_power

    def charge(self, power_kw: float, duration_h:float) -> tuple:
        pass

    def discharge(self, power_kw, duration_h):
        pass

    def soc_status(self,state_of_charge):
        pass