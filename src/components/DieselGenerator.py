class DieselGenerator:
    def __init__(self, num_DGs: int, r_capacity: float, a1: float, a2: float):
        """
        num_DGs: int
            Number of generators, pcs
            Количество генераторов, шт
        a1: float
            The fuel curve intercept coefficient, l/kWh
            Эмпирический коэффициент, л/кВт·ч.
        a2: float
            The fuel curve slope, l/kWh
            Эмпирический коэффициент, л/кВт·ч.
        """

        self.num_DGs = num_DGs
        self.r_capacity = r_capacity
        self.p_min = 0.35 * self.r_capacity
        self.p_max = 0.95 * self.r_capacity
        self.a1 = a1
        self.a2 = a2

    def generate(self, generatorLoad: float):
        pass

    def calculate_fuel_cost(self, generate: float):
        """

        """
        return self.a1 * self.r_capacity + self.a2 * generate

