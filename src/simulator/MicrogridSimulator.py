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

        self.capacity = self.bess.get_passport_parameters()[
            'Номинальная энергоемкость, кВт·ч'
        ]

    def simulator_1(self,
            initial_soc: float,
            val_dgs: np.ndarray
            ) -> Dict[str, np.ndarray]:
        """
        Приоритетное использование СНЭЭ
        Priority use of BESS
        """
        if not 0 <= initial_soc <= 1:
            raise ValueError("Начальное состояние заряда должно быть в диапазоне [0, 1]")

        # Инициализация массивов
        new_gen = self.gen.copy()
        net_gen = np.zeros(self.n, dtype=np.float64)
        shunt_gen = np.zeros(self.n, dtype=np.float64)

        capacity_history = np.zeros(self.n + 1, dtype=np.float64)
        soc_history = np.zeros(self.n + 1, dtype=np.float64)
        p_bess_history = np.zeros(self.n, dtype=np.float64)

        p_dgs_history = np.zeros(self.n, dtype=np.float64)
        net_dgs = np.zeros(self.n, dtype=np.float64)
        shunt_dgs = np.zeros(self.n, dtype=np.float64)
        cost_dgs_history = np.zeros(self.n, dtype=np.float64)
        is_on_dgs_history = np.zeros(self.n, dtype=np.int8)
        p_dgs_unit_history = np.zeros((self.n, self.dgs.n), dtype=np.float64)

        new_net_power = np.zeros(self.n, dtype=np.float64)

        # Начальные условия
        soc_history[0] = initial_soc
        capacity_history[0] = initial_soc * self.capacity

        for t in range(self.n):
            status = self.bess.soc_status(soc_history[t])

            net_power = self.gen[t] - self.load[t]

            if net_power >= 0:  # Энергия ФЭС больше или равна нагрузке
                if status in ['Заряд и Разряд возможен', 'Возможен только заряд']:
                    p_bess, capacity_next, soc_next = self.bess.charge(net_power, soc_history[t])  # СНЭЭ заряжается от ФЭС
                    # Отключение работающего генератора
                    p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs._shutdown_dgs(val_dgs)
                else: # Балласт от ФЭС
                    p_bess, capacity_next, soc_next = 0.0, capacity_history[t], \
                    soc_history[t]  # СНЭЭ НЕ заряжается от ФЭС
                    p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(
                        val_dgs, load=0.0)

            else: # Энергия ФЭС меньше нагрузки
                if status in ['Заряд и Разряд возможен', 'Возможен только разряд']:
                    p_bess, capacity_next, soc_next = self.bess.discharge(-net_power, soc_history[t])
                    if net_power + p_bess == 0:  # Энергоемкости СНЭЭ достаточно для покрытия остаточной нагрузки
                        p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs._shutdown_dgs(val_dgs)
                    else:
                        p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(
                            val_dgs, -net_power - p_bess)  # Оптимальная загрузка генератора

                else: # Разряд невозможен
                    p_bess = 0.0
                    capacity_next, soc_next = capacity_history[t], soc_history[t]
                    p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(
                        val_dgs, -net_power)



            diff = self.load[t] - total_p - p_bess
            if diff < 0:
                net_gen[t] = 0
                shunt_gen[t] = 0
                shunt_dgs[t] = -diff
            else:
                shunt_gen[t] = new_gen[t] - diff
                net_gen[t] = diff
                shunt_dgs[t] = 0

            # History BESS
            p_bess_history[t] = p_bess
            capacity_history[t + 1] = capacity_next
            soc_history[t + 1] = soc_next
            # History DGS
            p_dgs_history[t] = total_p
            net_dgs[t] = total_p - shunt_dgs[t]
            cost_dgs_history[t] = cost_dgs
            is_on_dgs_history[t] = is_on
            p_dgs_unit_history[t] = p_dgs

            new_net_power[t] = net_gen[t] + net_dgs[t] + p_bess - \
                               self.load[t]

        return {
            'new_gen': new_gen,
            'net_gen': net_gen,
            'shunt_gen': shunt_gen,
            'capacity_history': capacity_history[1:],
            'soc_history': soc_history[1:],
            'p_bess_history': p_bess_history,
            'is_on_dgs_history': is_on_dgs_history,
            'p_dgs_history': p_dgs_history,
            'p_dgs_unit_history': p_dgs_unit_history,
            'net_dgs': net_dgs,
            'shunt_dgs': shunt_dgs,
            'cost_dgs_history': cost_dgs_history,
            'new_net_power': new_net_power,
        }

    def simulator_2(self,
            initial_soc: float,
            val_dgs: np.ndarray
            ) -> Dict[str, np.ndarray]:
        """
        Экономически оптимальное управление
        Economically optimal management
        """
        if not 0 <= initial_soc <= 1:
            raise ValueError("Начальное состояние заряда должно быть в диапазоне [0, 1]")

        # Инициализация массивов
        new_gen = self.gen.copy()
        net_gen = np.zeros(self.n, dtype=np.float64)
        shunt_gen = np.zeros(self.n, dtype=np.float64)

        capacity_history = np.zeros(self.n + 1, dtype=np.float64)
        soc_history = np.zeros(self.n + 1, dtype=np.float64)
        p_bess_history = np.zeros(self.n, dtype=np.float64)

        p_dgs_history = np.zeros(self.n, dtype=np.float64)
        net_dgs = np.zeros(self.n, dtype=np.float64)
        shunt_dgs = np.zeros(self.n, dtype=np.float64)
        cost_dgs_history = np.zeros(self.n, dtype=np.float64)
        is_on_dgs_history = np.zeros(self.n, dtype=np.int8)
        p_dgs_unit_history = np.zeros((self.n, self.dgs.n), dtype=np.float64)

        new_net_power = np.zeros(self.n, dtype=np.float64)

        # Начальные условия
        soc_history[0] = initial_soc
        capacity_history[0] = initial_soc * self.capacity

        for t in range(self.n):
            status = self.bess.soc_status(soc_history[t])

            net_power = self.gen[t] - self.load[t]

            if net_power >= 0:  # Энергия ФЭС больше или равна нагрузке
                if status in ['Заряд и Разряд возможен', 'Возможен только заряд']:
                    p_bess, capacity_next, soc_next = self.bess.charge(net_power, soc_history[t])  # СНЭЭ заряжается от ФЭС
                    # Отключение работающего генератора
                    p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs._shutdown_dgs(val_dgs)
                else: # Балласт от ФЭС
                    p_bess, capacity_next, soc_next = 0.0, capacity_history[t], soc_history[t] # СНЭЭ НЕ заряжается от ФЭС
                    p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(val_dgs, load=0.0)


            else: # Энергия ФЭС меньше нагрузки
                if status in ['Заряд и Разряд возможен', 'Возможен только разряд']:
                    p_candidate, c_candidate, s_candidate = self.bess.discharge(-net_power, soc_history[t])
                    if net_power + p_candidate == 0:  # Энергоемкости СНЭЭ достаточно для покрытия остаточной нагрузки
                        p_bess, capacity_next, soc_next = p_candidate, c_candidate, s_candidate
                        p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs._shutdown_dgs(val_dgs)
                    else:
                        p_dgs_wb, val_dgs_wb, cost_dgs_wb, total_p_wb, is_on_wb = self.dgs.optimize_DGs(
                            val_dgs, -net_power - p_candidate)  # Оптимальная загрузка генератора
                        p_dgs_nb, val_dgs_nb, cost_dgs_nb, total_p_nb, is_on_nb = self.dgs.optimize_DGs(
                            val_dgs, -net_power)  # Оптимальная загрузка генератора
                        if cost_dgs_wb < cost_dgs_nb:
                            p_dgs, val_dgs, cost_dgs, total_p, is_on = p_dgs_wb, val_dgs_wb, cost_dgs_wb, total_p_wb, is_on_wb
                            p_bess, capacity_next, soc_next = p_candidate, c_candidate, s_candidate
                        else:
                            p_dgs, val_dgs, cost_dgs, total_p, is_on = p_dgs_nb, val_dgs_nb, cost_dgs_nb, total_p_nb, is_on_nb
                            excess = total_p + net_power

                            if excess > 0:
                                p_bess, capacity_next, soc_next = self.bess.charge(
                                    excess, soc_history[t])
                            else:
                                p_bess, capacity_next, soc_next = 0.0, \
                                capacity_history[t], soc_history[t]


                else: # Разряд невозможен
                    p_bess = 0.0
                    capacity_next, soc_next = capacity_history[t], soc_history[t]
                    p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(
                        val_dgs, -net_power)

            diff = self.load[t] - total_p - p_bess
            if diff < 0:
                net_gen[t] = 0
                shunt_gen[t] = 0
                shunt_dgs[t] = -diff
            else:
                shunt_gen[t] = new_gen[t] - diff
                net_gen[t] = diff
                shunt_dgs[t] = 0



            # History BESS
            p_bess_history[t] = p_bess
            capacity_history[t + 1] = capacity_next
            soc_history[t + 1] = soc_next
            # History DGS
            p_dgs_history[t] = total_p
            net_dgs[t] = total_p - shunt_dgs[t]
            cost_dgs_history[t] = cost_dgs
            is_on_dgs_history[t] = is_on
            p_dgs_unit_history[t] = p_dgs

            new_net_power[t] = net_gen[t] + net_dgs[t] + p_bess - self.load[t]

        return {
            'new_gen': new_gen,
            'net_gen': net_gen,
            'shunt_gen': shunt_gen,
            'capacity_history': capacity_history[1:],
            'soc_history': soc_history[1:],
            'p_bess_history': p_bess_history,
            'is_on_dgs_history': is_on_dgs_history,
            'p_dgs_history': p_dgs_history,
            'p_dgs_unit_history': p_dgs_unit_history,
            'net_dgs': net_dgs,
            'shunt_dgs': shunt_dgs,
            'cost_dgs_history': cost_dgs_history,
            'new_net_power': new_net_power,
        }

    def simulator_3(self,
                    val_dgs: np.ndarray
                    ) -> Dict[str, np.ndarray]:
        """
        Без СНЭЭ
        NO BESS
        """
        # Инициализация массивов
        new_gen = self.gen.copy()
        net_gen = np.zeros(self.n, dtype=np.float64)
        shunt_gen = np.zeros(self.n, dtype=np.float64)

        p_dgs_history = np.zeros(self.n, dtype=np.float64)
        net_dgs = np.zeros(self.n, dtype=np.float64)
        shunt_dgs = np.zeros(self.n, dtype=np.float64)
        cost_dgs_history = np.zeros(self.n, dtype=np.float64)
        is_on_dgs_history = np.zeros(self.n, dtype=np.int8)
        p_dgs_unit_history = np.zeros((self.n, self.dgs.n), dtype=np.float64)

        new_net_power = np.zeros(self.n, dtype=np.float64)

        for t in range(self.n):

            net_power = self.gen[t] - self.load[t]

            if net_power >= 0:  # Энергия ФЭС больше или равна нагрузке
                p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(val_dgs, load=0.0)
                diff = total_p - self.load[t]
                if diff >= 0:
                    shunt_gen[t] = new_gen[t]
                    net_gen[t] = 0
                    shunt_dgs[t] = diff
                else:
                    shunt_gen[t] = new_gen[t] + diff
                    net_gen[t] = -diff
                    shunt_dgs[t] = 0


            else: # Энергия ФЭС меньше нагрузки
                p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(
                        val_dgs, -net_power)
                diff = self.load[t] - total_p
                if diff < 0:
                    net_gen[t] = 0
                    shunt_gen[t] = 0
                    shunt_dgs[t] = -diff
                else:
                    shunt_gen[t] = new_gen[t] - diff
                    net_gen[t] = diff
                    shunt_dgs[t] = 0

            new_gen[t] = net_gen[t] + shunt_gen[t]
            # History DGS
            p_dgs_history[t] = total_p
            cost_dgs_history[t] = cost_dgs
            is_on_dgs_history[t] = is_on
            p_dgs_unit_history[t] = p_dgs
            net_dgs[t] = total_p - shunt_dgs[t]

            new_net_power[t] = net_gen[t] + net_dgs[t] - self.load[t]
        return {
            'new_gen': new_gen,
            'net_gen': net_gen,
            'shunt_gen': shunt_gen,
            'is_on_dgs_history': is_on_dgs_history,
            'p_dgs_history': p_dgs_history,
            'p_dgs_unit_history': p_dgs_unit_history,
            'net_dgs': net_dgs,
            'shunt_dgs': shunt_dgs,
            'cost_dgs_history': cost_dgs_history,
            'new_net_power': new_net_power,
        }

    def _can_shutdown(self, t: int) -> bool:
        """
        Проверяет, можно ли отключить генератор в момент t.
        Отключение разрешено только если во все следующие 24 часа
        (или до конца моделирования) net_power >= 0.
        """
        horizon = min(t + 24, self.n)
        return all(self.gen[i] >= self.load[i] for i in range(t + 1, horizon))

    def simulator_4(self,
                    initial_soc: float,
                    val_dgs: np.ndarray
                    ) -> Dict[str, np.ndarray]:
        """
        Экономически оптимальное управление с прогнозом на 24 часа.
        Генератор отключается только если в следующие 24 часа net_power >= 0.
        Иначе - холостой ход (load=0.0).
        """
        if not 0 <= initial_soc <= 1:
            raise ValueError(
                "Начальное состояние заряда должно быть в диапазоне [0, 1]")

        new_gen = self.gen.copy()
        net_gen = np.zeros(self.n, dtype=np.float64)
        shunt_gen = np.zeros(self.n, dtype=np.float64)

        capacity_history = np.zeros(self.n + 1, dtype=np.float64)
        soc_history = np.zeros(self.n + 1, dtype=np.float64)
        p_bess_history = np.zeros(self.n, dtype=np.float64)

        p_dgs_history = np.zeros(self.n, dtype=np.float64)
        net_dgs = np.zeros(self.n, dtype=np.float64)
        shunt_dgs = np.zeros(self.n, dtype=np.float64)
        cost_dgs_history = np.zeros(self.n, dtype=np.float64)
        is_on_dgs_history = np.zeros(self.n, dtype=np.int8)
        p_dgs_unit_history = np.zeros((self.n, self.dgs.n), dtype=np.float64)

        new_net_power = np.zeros(self.n, dtype=np.float64)

        soc_history[0] = initial_soc
        capacity_history[0] = initial_soc * self.capacity

        for t in range(self.n):
            status = self.bess.soc_status(soc_history[t])
            net_power = self.gen[t] - self.load[t]
            can_shutdown = self._can_shutdown(t)

            if net_power >= 0:
                if status in ['Заряд и Разряд возможен',
                              'Возможен только заряд']:
                    p_bess, capacity_next, soc_next = self.bess.charge(
                        net_power, soc_history[t])
                    if can_shutdown:
                        # Полное отключение генератора
                        p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs._shutdown_dgs(
                            val_dgs)
                    else:
                        # Холостой ход — генератор остаётся в работе
                        p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(
                            val_dgs, load=0.0)
                else:  # Балласт
                    p_bess, capacity_next, soc_next = 0.0, capacity_history[t], \
                    soc_history[t]
                    p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(
                        val_dgs, load=0.0)

            else:  # net_power < 0
                if status in ['Заряд и Разряд возможен',
                              'Возможен только разряд']:
                    p_candidate, c_candidate, s_candidate = self.bess.discharge(
                        -net_power, soc_history[t])
                    if net_power + p_candidate == 0:
                        p_bess, capacity_next, soc_next = p_candidate, c_candidate, s_candidate
                        if can_shutdown:
                            p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs._shutdown_dgs(
                                val_dgs)
                        else:
                            p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(
                                val_dgs, load=0.0)
                    else:
                        p_dgs_wb, val_dgs_wb, cost_dgs_wb, total_p_wb, is_on_wb = self.dgs.optimize_DGs(
                            val_dgs, -net_power - p_candidate)
                        p_dgs_nb, val_dgs_nb, cost_dgs_nb, total_p_nb, is_on_nb = self.dgs.optimize_DGs(
                            val_dgs, -net_power)
                        if cost_dgs_wb < cost_dgs_nb:
                            p_dgs, val_dgs, cost_dgs, total_p, is_on = p_dgs_wb, val_dgs_wb, cost_dgs_wb, total_p_wb, is_on_wb
                            p_bess, capacity_next, soc_next = p_candidate, c_candidate, s_candidate
                        else:
                            p_dgs, val_dgs, cost_dgs, total_p, is_on = p_dgs_nb, val_dgs_nb, cost_dgs_nb, total_p_nb, is_on_nb
                            excess = total_p + net_power
                            if excess > 0:
                                p_bess, capacity_next, soc_next = self.bess.charge(
                                    excess, soc_history[t])
                            else:
                                p_bess, capacity_next, soc_next = 0.0, \
                                capacity_history[t], soc_history[t]
                else:  # Разряд невозможен
                    p_bess = 0.0
                    capacity_next, soc_next = capacity_history[t], soc_history[
                        t]
                    p_dgs, val_dgs, cost_dgs, total_p, is_on = self.dgs.optimize_DGs(
                        val_dgs, -net_power)

            diff = self.load[t] - total_p - p_bess
            if diff < 0:
                net_gen[t] = 0
                shunt_gen[t] = 0
                shunt_dgs[t] = -diff
            else:
                shunt_gen[t] = new_gen[t] - diff
                net_gen[t] = diff
                shunt_dgs[t] = 0

            p_bess_history[t] = p_bess
            capacity_history[t + 1] = capacity_next
            soc_history[t + 1] = soc_next
            p_dgs_history[t] = total_p
            net_dgs[t] = total_p - shunt_dgs[t]
            cost_dgs_history[t] = cost_dgs
            is_on_dgs_history[t] = is_on
            p_dgs_unit_history[t] = p_dgs
            new_net_power[t] = net_gen[t] + net_dgs[t] + p_bess - self.load[t]

        return {
            'new_gen': new_gen,
            'net_gen': net_gen,
            'shunt_gen': shunt_gen,
            'capacity_history': capacity_history[1:],
            'soc_history': soc_history[1:],
            'p_bess_history': p_bess_history,
            'is_on_dgs_history': is_on_dgs_history,
            'p_dgs_history': p_dgs_history,
            'p_dgs_unit_history': p_dgs_unit_history,
            'net_dgs': net_dgs,
            'shunt_dgs': shunt_dgs,
            'cost_dgs_history': cost_dgs_history,
            'new_net_power': new_net_power,
        }
