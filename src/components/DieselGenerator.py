import numpy as np

class DieselGenerator:
    def __init__(self, num_DGs: int, r_capacity: float, a1: float, a2: float, start_up_price: float, fuel_price: float):
        """
        num_DGs: int
            Number of generators, pcs
            Количество генераторов, шт
        r_capacity: float
            The nominal power of each diesel generator (kW)
            Номинальная мощность каждого генератора (кВт)
        a1: float
            The fuel curve intercept coefficient, l/kWh
            Эмпирический коэффициент, л/кВт·ч.
        a2: float
            The fuel curve slope, l/kWh
            Эмпирический коэффициент, л/кВт·ч.
        start_up_price: float
            Стоимость запуска одного двигателя
        fuel_price: float
            Стоимость литра топлива
        """

        self.num_DGs = num_DGs
        self.r_capacity = r_capacity
        self.p_min = 0.35 * self.r_capacity
        self.p_max = 0.95 * self.r_capacity
        self.a1 = a1
        self.a2 = a2
        self.start_up_price = start_up_price
        self.fuel_price = fuel_price
        # Состояние массива генераторов
        # Status of the generator array
        self.power_outputs = np.zeros(num_DGs)
        self.total_fuel_consumption = 0.0  # Общий расход топлива
        self.total_cost = 0.0  # Общая стоимость
        self.start_up_count = 0  # Количество запусков


    def calculate_fuel_consumption(self, generate: float):
        """
        The fuel consumption of the diesel generator (DG)
        Зависимость расхода топлива от номинальной мощности и текущей нагрузки ДГУ
        """
        if generate <= 0:
            return 0.0
        return self.a1 * generate + self.a2 * self.r_capacity

    def calculate_operating_cost(self, power_kw: float, is_starting: bool = False) -> float:
        """
        Расчет стоимости эксплуатации одного генератора
        """
        pass

    def distribute_load_among_generators(self, target_num_running: int,
                                         load: float) -> np.ndarray:
        """
        Распределение нагрузки между работающими генераторами

        Параметры (Parameters)
        ----------
        target_num_running: int
            Количество работающих генераторов
        load: float
            Требуемая мощность нагрузки

        Возвращает (Returns)
        -----------
        np.ndarray: Распределение мощности между генераторами
        """
        pass



