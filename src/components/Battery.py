class Battery:
    """
    Класс моделирования системы накопления электрической энергии (СНЭЭ)
    A class that models a storage battery energy storage system (BESS).

    Параметры (Parameters)
    ----------
    e_cr: float
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
    aux_power: float
        Мощность потребления вспомогательной подсистемы, Вт
        auxiliary power consumption, Wh
    cp: float
        Саморазряд СНЭЭ, %

    Возвращает (Returns)
    ----------

    """
    def __init__(self, e_cr: float, soc_max: float, soc_min: float, r_power_ch: float, r_power_ds: float, eff: float, aux_power: float, cp: float):
        self.e_cr = e_cr
        self.soc_max = soc_max/100
        self.soc_min = soc_min/100
        self.r_power_ch = r_power_ch
        self.r_power_ds = r_power_ds
        self.eff = eff/100
        self.aux_power = aux_power
        self.cp = cp/100

    def charge(self, soc: float) -> tuple:
        """
        Функция заряда батареи
        Battery charge function.

        Параметры (Parameters)
        ----------
        soc: float
            Допустимый СЗ.
            Available SOC.
        Возвращает (Returns)
        ----------
        tuple:
            p_ch: float
                Мощность зарядки.
            e_cap: float
                Доступная энергия после зарядки.
            soc_new: float
                Доступный уровень заряда (SOC) после зарядки.
        """
        p_ch = - min(self.e_cr * (self.soc_max - soc), self.r_power_ch)
        e_cap = self.e_cr * soc - p_ch * self.eff - self.cp * self.e_cr # Available energy capacity
        soc_new = e_cap / self.e_cr
        return p_ch, e_cap, soc_new

    def discharge(self, soc: float) -> tuple:
        """
        Функция разряда батареи
        Battery discharge function.

        Параметры (Parameters)
        ----------
        soc: float
            Допустимый СЗ.
            Available SOC.
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
        p_ds = min(self.e_cr * (soc - self.soc_min), self.r_power_ds)
        e_cap = self.e_cr * soc - p_ds / self.eff - self.cp * self.e_cr  # Available energy capacity
        soc_new = e_cap / self.e_cr
        return p_ds, e_cap, soc_new

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