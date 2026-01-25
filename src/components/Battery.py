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
        # self.aux_p_ds

    def charge(self, net_power: float, soc: float) -> tuple:
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
        tuple:
            p_ch: float
                Мощность зарядки.
            e_new: float
                Доступная энергия после зарядки.
            soc_new: float
                Доступный уровень заряда (SOC) после зарядки.
        """

        if self.aux_p_ch >= net_power:
            return 0, self.capacity * soc, soc
        else:
            ava_e = min(net_power, self.r_power_ch) # Available energy capacity
            p_ch = - min(self.capacity * (self.soc_max - soc), ava_e)
            e_new = self.capacity * soc - p_ch * self.eff - self.cp * self.capacity # New available energy capacity
            soc_new = e_new / self.capacity
            return p_ch, e_new, soc_new

    def discharge(self, net_power: float, soc: float) -> tuple:
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
        tuple:
            p_ds: float
                Мощность разряда.
            e_cap: float
                Доступная энергия после разряда.
            soc_new: float
                Доступный уровень заряда (SOC) после разряда.
        """
        if self.capacity * (soc - self.soc_min) * self.eff <= self.cp * self.capacity:
            return 0, self.capacity * soc, soc
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