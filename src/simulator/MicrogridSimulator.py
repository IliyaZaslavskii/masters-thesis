import numpy as np
import pandas as pd
from typing import Tuple, Dict, Optional

class MicrogridSimulator:
    """
    Класс моделирования алгоритма управления гибридным комплексом
    """
    def __init__(self,
                 df: pd.DataFrame,
                 load_column: str,
                 gen_column: str,
                 bess: object,
                 dgs: object,
                 r_electricity,
                 ):
        """
        Инициализация объекта АГЭК

        Параметры (Parameters)
        ----------
        df : pd.DataFrame
            Временной ряд нагрузки и генерации.
        load_column : str
            Название столбца нагрузки (кВт).
        gen_column : str
            Название столбца генерации (кВт).
        bess : object
            Класс моделирования системы накопления электрической энергии (СНЭЭ).
        dgs : object
            Класс моделирования работы дизель-генератора.
        r_electricity : float
            Тариф на электроэнергию (руб/кВт·ч).
        """
        if load_column not in df or gen_column not in df:
            raise ValueError("Указанные столбцы отсутствуют в DataFrame")

        self.load = df[load_column].to_numpy(dtype=np.float64)
        self.gen = df[gen_column].to_numpy(dtype=np.float64)
        if len(self.load) != len(self.gen):
            raise ValueError("Длины массивов нагрузки и генерации должны совпадать")

        self.n = len(self.gen)
        self.bess = bess
        self.dgs = dgs
        self.r_electricity = r_electricity

        self.capacity = self.bess.get_passport_parameters()[
            'Номинальная энергоемкость (кВт·ч)'
        ]

    def simulator_1(self,
            initial_soc: float,
            u_dgs: Optional[np.ndarray]
            ) -> Dict[str, np.ndarray]:

        if not 0 <= initial_soc <= 1:
            raise ValueError("Начальное состояние заряда должно быть в диапазоне [0, 1]")

        # Инициализация массивов
        new_gen = self.gen.copy()
        capacity_history = np.zeros(self.n + 1, dtype=np.float64)
        soc_history = np.zeros(self.n + 1, dtype=np.float64)
        new_net_power = np.zeros(self.n, dtype=np.float64)

        p_bess_history = np.zeros(self.n, dtype=np.float64)
        p_dgs_history = np.zeros(self.n, dtype=np.float64)
        cost_dgs_history = np.zeros(self.n, dtype=np.float64)

        # Начальные условия
        soc_history[0] = initial_soc
        capacity_history[0] = initial_soc * self.capacity

        for t in range(self.n):
            current_soc = soc_history[t]
            status = self.bess.soc_status(current_soc)

            net_power = self.gen[t] - self.load[t]

            if net_power >= 0:  # Энергия ФЭС больше или равна нагрузке
                if status in ['Заряд и Разряд возможен', 'Разряд невозможен']:
                    p_bess, capacity_next, soc_next = self.bess.charge(net_power, current_soc)  # СНЭЭ заряжается от ФЭС
                    new_net_power[t] = net_power + p_bess  # Новый баланс мощности
                else: # Балласт от ФЭС
                    p_bess, capacity_next, soc_next = 0.0, capacity_history[t], current_soc # СНЭЭ НЕ заряжается от ФЭС
                    new_gen[t] = self.load[t]  # Ограничиваем генерацию
                    new_net_power[t] = 0.0  # Новый баланс мощности
                #Отключение работающего генератора
                u_prev = np.zeros_like(u_dgs)
                cost_dgs = self.dgs.total_cost(u_prev, u_dgs, u_prev,
                                           self.r_electricity)
                p_dgs, u_dgs, total_p, is_on = 0, np.zero_like(u_dgs), 0, 0

                p_dgs_history[t] = total_p
                cost_dgs_history[t] = cost_dgs

            else: # Энергия ФЭС меньше нагрузки
                if status in ['Заряд и Разряд возможен', 'Заряд невозможен']:
                    p_bess, capacity_next, soc_next = self.bess.discharge(-net_power, current_soc)
                    if net_power + p_bess == 0:  # Энергоемкости СНЭЭ достаточно для покрытия остаточной нагрузки
                        new_net_power[t] = net_power + p_bess
                    else:
                        p_dgs, u_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(
                            u_dgs, -net_power - p_bess, self.r_electricity
                        )  # Оптимальная загрузка генератора
                        p_dgs_history[t] = total_p
                        cost_dgs_history[t] = cost_dgs
                        new_net_power[t] = total_p + p_bess  # Новый баланс мощности

                else: # Разряд невозможен
                    p_bess = 0.0
                    capacity_next, soc_next = capacity_history[t], current_soc
                    p_dgs, u_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(
                        u_dgs, -net_power, self.r_electricity
                    )
                    p_dgs_history[t] = total_p
                    cost_dgs_history[t] = cost_dgs
                    new_net_power[t] = net_power + p_dgs

            # Запись истории BESS
            p_bess_history[t] = p_bess
            capacity_history[t + 1] = capacity_next
            soc_history[t + 1] = soc_next

        return {
            'new_gen': new_gen,
            'capacity_history': capacity_history,
            'soc_history': soc_history,
            'new_net_power': new_net_power,
            'final_u_dgs': u_dgs,
            'p_bess_history': p_bess_history,
            'p_dgs_history': p_dgs_history,
            'cost_dgs_history': cost_dgs_history
        }

    def simulator_2(self,
            initial_soc: float,
            u_dgs: Optional[np.ndarray]
            ) -> Dict[str, np.ndarray]:

        if not 0 <= initial_soc <= 1:
            raise ValueError("Начальное состояние заряда должно быть в диапазоне [0, 1]")

        # Инициализация массивов
        new_gen = self.gen.copy()
        capacity_history = np.zeros(self.n + 1, dtype=np.float64)
        soc_history = np.zeros(self.n + 1, dtype=np.float64)
        new_net_power = np.zeros(self.n, dtype=np.float64)

        p_bess_history = np.zeros(self.n, dtype=np.float64)
        p_dgs_history = np.zeros(self.n, dtype=np.float64)
        cost_dgs_history = np.zeros(self.n, dtype=np.float64)

        # Начальные условия
        soc_history[0] = initial_soc
        capacity_history[0] = initial_soc * self.capacity

        for t in range(self.n):
            current_soc = soc_history[t]
            status = self.bess.soc_status(current_soc)

            net_power = self.gen[t] - self.load[t]

            if net_power >= 0:  # Энергия ФЭС больше или равна нагрузке
                if status in ['Заряд и Разряд возможен', 'Разряд невозможен']:
                    p_bess, capacity_next, soc_next = self.bess.charge(net_power, current_soc)  # СНЭЭ заряжается от ФЭС
                    new_net_power[t] = net_power + p_bess  # Новый баланс мощности
                else: # Балласт от ФЭС
                    p_bess, capacity_next, soc_next = 0.0, capacity_history[t], current_soc # СНЭЭ НЕ заряжается от ФЭС
                    new_gen[t] = self.load[t]  # Ограничиваем генерацию
                    new_net_power[t] = 0.0  # Новый баланс мощности
                # Отключение работающего генератора
                u_prev = np.zeros_like(u_dgs)
                cost_dgs = self.dgs.total_cost(u_prev, u_dgs, u_prev,
                                               self.r_electricity)
                p_dgs, u_dgs, total_p, is_on = 0, np.zero_like(u_dgs), 0, 0
                p_dgs_history[t] = total_p
                cost_dgs_history[t] = cost_dgs

            else: # Энергия ФЭС меньше нагрузки
                if status in ['Заряд и Разряд возможен', 'Заряд невозможен']:
                    p_candidate, c_candidate, s_candidate = self.bess.discharge(-net_power, current_soc)
                    if net_power + p_candidate == 0:  # Энергоемкости СНЭЭ достаточно для покрытия остаточной нагрузки
                        p_bess, capacity_next, soc_next = p_candidate, c_candidate, s_candidate
                        new_net_power[t] = net_power + p_bess
                    else:
                        p_dgs_wb, u_dgs_wb, cost_dgs_wb, total_p_wb, is_on_wb = self.dgs.optimize_DGs(
                            u_dgs, -net_power - p_candidate, self.r_electricity
                        )  # Оптимальная загрузка генератора
                        p_dgs_nb, u_dgs_nb, cost_dgs_nb, total_p_nb, is_on_nb = self.dgs.optimize_DGs(
                            u_dgs, -net_power, self.r_electricity
                        )  # Оптимальная загрузка генератора
                        if cost_dgs_wb >= cost_dgs_nb:
                            p_dgs, u_dgs, cost_dgs, total_p, is_on = p_dgs_nb, u_dgs_nb, cost_dgs_nb, total_p_nb, is_on_nb
                            net = total_p-net_power
                            if net >= 0:
                                if status in ['Заряд и Разряд возможен', 'Разряд невозможен']:
                                    p_bess, capacity_next, soc_next = self.bess.charge(net,current_soc)  # СНЭЭ заряжается от ДГУ
                                    new_net_power[t] = net + p_bess  # Новый баланс мощности
                            else:
                                p_bess, capacity_next, soc_next = 0.0, capacity_history[t], current_soc  # СНЭЭ НЕ заряжается от ДГУ
                                new_net_power[t] = 0.0  # Новый баланс мощности
                        else:
                            p_dgs, u_dgs, cost_dgs, total_p, is_on = p_dgs_wb, u_dgs_wb, cost_dgs_wb, total_p_wb, is_on_wb
                            p_bess, capacity_next, soc_next = p_candidate, c_candidate, s_candidate
                        p_dgs_history[t] = total_p
                        cost_dgs_history[t] = cost_dgs
                        new_net_power[t] = total_p + p_bess  # Новый баланс мощности

                else: # Разряд невозможен
                    p_bess = 0.0
                    capacity_next, soc_next = capacity_history[t], current_soc
                    p_dgs, u_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(
                        u_dgs, -net_power, self.r_electricity
                    )
                    p_dgs_history[t] = total_p
                    cost_dgs_history[t] = cost_dgs
                    new_net_power[t] = net_power + p_dgs

            # Запись истории BESS
            p_bess_history[t] = p_bess
            capacity_history[t + 1] = capacity_next
            soc_history[t + 1] = soc_next

        return {
            'new_gen': new_gen,
            'capacity_history': capacity_history,
            'soc_history': soc_history,
            'new_net_power': new_net_power,
            'final_u_dgs': u_dgs,
            'p_bess_history': p_bess_history,
            'p_dgs_history': p_dgs_history,
            'cost_dgs_history': cost_dgs_history
        }

