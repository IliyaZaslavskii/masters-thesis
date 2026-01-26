class Battery:
    """
    Класс моделирования системы накопления электрической энергии (СНЭЭ)
    A class that models a storage battery energy storage system (BESS).

    Параметры (Parameters)
    ----------
    capacity: float
        Номинальная энергоемкость, Вт·ч
        Nominal energy capacity, Wh
    soc_max: float
        Максимально допустимый СЗ, %.
        The maximum allowable SOC, %.
    soc_min: float
        Минимально допустимый СЗ, %.
        The minimum allowable SOC, %.
    r_power_ch: float
        Номинальная предельная мощность заряда, Вт
    r_power_ds: float
        Номинальная предельная мощность разряда, Вт
    eff: float
        Эффективность заряда-разряда, %
        roundtrip efficiency, %.
    aux_p_ch: float
        Мощность потребления вспомогательной подсистемы при заряде, Вт
        auxiliary power consumption, Wh
    aux_p_ds: float
        Мощность потребления вспомогательной подсистемы при разряде, Вт
        auxiliary power consumption, Wh
    cp: float
        Саморазряд СНЭЭ, %

    Возвращает (Returns)
    ----------

    """
    def __init__(self, capacity: float, soc_max: float, soc_min: float, r_power_ch: float, r_power_ds: float, eff: float, cp: float):
        self.capacity = capacity
        self.soc_max = soc_max/100
        self.soc_min = soc_min/100
        self.r_power_ch = r_power_ch
        self.r_power_ds = r_power_ds
        self.eff = eff/100
        self.cp = cp/100
        self.aux_p_ch = cp/100 * capacity + r_power_ch * (1 - eff)
        self.aux_p_ds = cp/100 * capacity + (r_power_ds - r_power_ds * eff) / eff

    def charge(self, net_power: float, soc: float) -> tuple[float, float, float]:
        """
        Функция заряда батареи
        Battery charge function.

        Параметры (Parameters)
        ----------
        net_power: float
            Мощность  из сети.
            Network Power.
        soc: float
            Доcтупный СЗ.
            Accessible SOC.
        Возвращает (Returns)
        ----------
        tuple[float, float, float]:
            p_ch: float
                Мощность зарядки.
                Charging power.
            e_new: float
                Доступная энергия после заряда.
                Available energy after charging.
            soc_new: float
                Доступный уровень СЗ после заряда..
        """

        if net_power <= self.aux_p_ch or self.capacity * (self.soc_max - soc) <= self.aux_p_ch:
            p_ch = 0.0
            e_new = self.capacity * soc
            soc_new = soc
        else:
            ava_e = min(net_power, self.r_power_ch) # Available energy capacity
            p_ch = - min(self.capacity * (self.soc_max - soc), ava_e)
            e_new = self.capacity * soc - p_ch * self.eff - self.cp * self.capacity # New available energy capacity
            soc_new = e_new / self.capacity
        return p_ch, e_new, soc_new

    def discharge(self, net_power: float, soc: float) -> tuple[float, float, float]:
        """
        Функция разряда батареи
        Battery discharge function.

        Параметры (Parameters)
        ----------
        net_power: float
            Мощность  из сети.
            Network Power.
        soc: float
            Доcтупный СЗ.
            Accessible SOC.
        Возвращает (Returns)
        ----------
        tuple[float, float, float]:
            p_ds: float
                Мощность разряда.
                Discharge power.
            e_new: float
                Доступная энергия после разряда.
                Available energy after discharge.
            soc_new: float
                Доступный уровень СЗ после разряда.
                SOC after discharge.
        """
        if self.capacity * (soc - self.soc_min) <= self.aux_p_ds:
            p_ds = 0.0
            e_new = self.capacity * soc
            soc_new = soc
        else:
            ava_e = min(net_power, self.r_power_ds) # Available energy capacity
            p_ds =min(self.capacity * (soc - self.soc_min) * self.eff - self.cp * self.capacity, ava_e)
            e_new = self.capacity * soc - p_ds / self.eff - self.cp * self.capacity  # New available energy capacity
            soc_new = e_new / self.capacity
        return p_ds, e_new, soc_new


    def soc_status(self, soc: float) -> str:
        """
        Функция состояния батареи
        Battery status function.

        Параметры (Parameters)
        ----------
        soc: float
            Допустимый СЗ.
            Available SOC.
        Возвращает (Returns)
        ----------
        str:
            Состояние батареи
            Battery Status
        """
        match (soc, self.soc_max, self.soc_min):
            case (soc, max_soc, min_soc) if min_soc < soc < max_soc:
                return 'Заряд и Разряд возможен'
            case (soc, max_soc, _) if soc == max_soc:
                return 'Заряд невозможен'
            case (soc, _, min_soc) if soc == min_soc:
                return 'Разряд невозможен'
            case _:
                return 'Выключен'