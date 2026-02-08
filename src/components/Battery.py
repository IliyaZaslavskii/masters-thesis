class Battery:
    """
    Класс моделирования системы накопления электрической энергии (СНЭЭ)
    A class that models a battery energy storage system (BESS).
    """

    def __init__(self,
            capacity: float,
            soc_max: float,
            soc_min: float,
            r_power_ch: float,
            r_power_ds: float,
            eff_ch: float,
            eff_ds: float,
            cp: float
            ):
        """
        Инициализация объекта батареи
        Initializing the battery object

        Параметры (Parameters)
        ----------
        capacity: float
            Номинальная энергоемкость, кВт·ч
            Nominal energy capacity, kWh
        soc_max: float
            Максимально допустимый СЗ, %.
            The maximum allowable SOC, %.
        soc_min: float
            Минимально допустимый СЗ, %.
            The minimum allowable SOC, %.
        r_power_ch: float
            Номинальная предельная мощность заряда, кВт
        r_power_ds: float
            Номинальная предельная мощность разряда, кВт
        eff_ch: float
            Эффективность заряда, %
            roundtrip efficiency charging, %.
        eff_ds: float
            Эффективность разряда, %
            roundtrip efficiency discharging, %.
        aux_p_ch: float
            Мощность потребления вспомогательной подсистемы при заряде, кВт
            auxiliary power consumption, kW
        aux_p_ds: float
            Мощность потребления вспомогательной подсистемы при разряде, кВт
            auxiliary power consumption, kW
        cp: float
            Саморазряд СНЭЭ, %
            self-discharge of BESS, %
        """
        # Основные параметры
        # Basic parameters
        self.capacity = capacity  # кВт·ч
        self.soc_max = soc_max / 100  # от 0 до 1
        self.soc_min = soc_min / 100  # от 0 до 1
        self.r_power_ch = r_power_ch  # кВт
        self.r_power_ds = r_power_ds  # кВт
        self.eff_ch = eff_ch / 100  # от 0 до 1
        self.eff_ds = eff_ds / 100  # от 0 до 1
        self.cp = cp / 100  # от 0 до 1
        # Расчетные параметры
        # Calculated parameters
        self.aux_p_ch = self.cp * capacity + r_power_ch * (1 - self.eff_ch)
        self.aux_p_ds = self.cp * capacity + (r_power_ds - r_power_ds * self.eff_ds) / self.eff_ds

    def get_passport_parameters(self) -> dict:
        """
        Возвращает паспортные параметры СНЭЭ

        Возвращает (Returns)
        ----------
        dict
        """
        return {
            "Номинальная энергоемкость (кВт·ч)": self.capacity,
            "Максимальная степень заряда (СЗ_макс), %": self.soc_max * 100,
            "Минимальная степень заряда (СЗ_мин), %": self.soc_min * 100,
            "Номинальная мощность заряда, кВт": self.r_power_ch,
            "Номинальная мощность разряда, кВт": self.r_power_ds,
            "Эффективность заряда, %": self.eff_ch * 100,
            "Эффективность разряда, %": self.eff_ds * 100,
            "Коэффициент саморазряда, %": self.cp * 100,
            "Потери мощности при заряде, кВт": self.aux_p_ch,
            "Потери мощности при разряде, кВт": self.aux_p_ds
        }


    def charge(self, net_power: float, soc: float) -> tuple[float, float, float]:
        """
        Функция заряда батареи
        Battery charge function.

        Параметры (Parameters)
        ----------
        net_power: float
            Мощность  из сети, кВт.
            Network Power, kW.
        soc: float
            Доcтупный СЗ.
            Accessible SOC.
        Возвращает (Returns)
        ----------
        tuple[float, float, float]:
            p_ch: float
                Мощность зарядки, кВт.
                Charging power, kW.
            e_new: float
                Доступная энергия после заряда.
                Available energy after charging.
            soc_new: float
                Доступный уровень СЗ после заряда..
        """

        if net_power <= self.aux_p_ch:
            p_ch = 0.0
            e_new = self.capacity * soc
            soc_new = soc
        else:
            ava_e = min(net_power, self.r_power_ch) # New available energy capacity
            p_ch = - min(self.capacity * (self.soc_max - soc) / self.eff_ch + self.cp * self.capacity, ava_e)
            e_new = self.capacity * soc - p_ch * self.eff_ch - self.cp * self.capacity # New available energy capacity
            soc_new = e_new / self.capacity
        return p_ch, e_new, soc_new

    def discharge(self, net_power: float, soc: float) -> tuple[float, float, float]:
        """
        Функция разряда батареи
        Battery discharge function.

        Параметры (Parameters)
        ----------
        net_power: float
            Мощность  из сети, кВт.
            Network Power, kW.
        soc: float
            Доcтупный СЗ.
            Accessible SOC.
        Возвращает (Returns)
        ----------
        tuple[float, float, float]:
            p_ds: float
                Мощность разряда, кВт.
                Discharge power, kW.
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
            p_ds =min(self.capacity * (soc - self.soc_min) * self.eff_ds - self.cp * self.capacity, ava_e)
            e_new = self.capacity * soc - p_ds / self.eff_ds - self.cp * self.capacity  # New available energy capacity
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
