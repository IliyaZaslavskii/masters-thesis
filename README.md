# Оптимизация СНЭЭ в автономном гибридном энергокомплексе

Исследовательская модель для выбора мощности и энергоемкости системы накопления электрической энергии (СНЭЭ) в автономном комплексе «фотоэлектростанция - СНЭЭ - дизельные генераторы».

Репозиторий содержит:

- почасовую имитационную модель диспетчеризации;
- модели аккумулятора, солнечной генерации и группы ДГУ;
- экономический расчет NPV, IRR и LCOS;
- оптимизацию параметров СНЭЭ генетическим алгоритмом;
- анализ чувствительности и построение графиков.


## Содержание

- [Быстрый старт](#быстрый-старт)
- [Подготовка данных](#подготовка-данных)
- [Запуск моделирования](#запуск-моделирования)
- [Запуск оптимизации](#запуск-оптимизации)
- [Структура проекта](#структура-проекта)

## Быстрый старт

### 1. Клонирование

```bash
git clone https://github.com/IliyaZaslavskii/masters-thesis.git
cd masters-thesis
```

### 2. Виртуальное окружение и зависимости

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Для работы с ноутбуками установите Jupyter, если он отсутствует в окружении:

```bash
pip install jupyterlab
```

### 3. Запуск Jupyter

Ноутбуки вычисляют корень проекта относительно текущей директории, поэтому запускайте Jupyter из `src/tests`. Одновременно добавьте корень репозитория в `PYTHONPATH`, чтобы импорты вида `from src...` работали и вне IDE.

Windows PowerShell:

```powershell
cd src/tests
$env:PYTHONPATH = (Resolve-Path ../..).Path
jupyter lab
```

Linux/macOS:

```bash
cd src/tests
PYTHONPATH=../.. jupyter lab
```

Рекомендуемый порядок:

1. [`SolarGeneration.ipynb`](src/tests/SolarGeneration.ipynb) — подготовить погодные данные и `dataset.xlsx`; .

## Подготовка данных

### Входной ряд нагрузки

Перед выполнением `SolarGeneration.ipynb` поместите файл нагрузки по пути:

```text
src/data/data.xlsx
```

Ноутбук ожидает почасовой временной индекс и столбец `Нагрузка, kW`.

### Погодные данные и солнечная генерация

[`SolarGeneration.ipynb`](src/tests/SolarGeneration.ipynb):

1. определяет координаты населенного пункта;
2. загружает почасовую погоду NASA POWER;
3. рассчитывает генерацию ФЭС через `pvlib`;
4. совмещает генерацию с нагрузкой;
5. сохраняет итоговый набор данных.

Параметры эксперимента задаются в первой кодовой ячейке:

```python
START_DATE = 20181231
END_DATE = 20200101
LOCATION_NAME = "СВОЕНАЗВАНИЕЛОКАЦИИ"
```

Итоговый `dataset.xlsx` должен содержать как минимум:

| Столбец | Единица | Назначение |
|---|---:|---|
| `Load, kW` | кВт | электрическая нагрузка |
| `Solar, kW` | кВт | мощность солнечной генерации |
| `datetime` или индекс | час | временная метка, если доступна |

Значения нагрузки и генерации должны быть конечными и неотрицательными.

> Для получения погоды необходим доступ к NASA POWER и сервису геокодирования Nominatim. Исходный файл нагрузки `data.xlsx` и сформированный `dataset.xlsx` не входят в репозиторий.

## Запуск моделирования

Для интерактивного анализа откройте [`src/tests/test.ipynb`](src/tests/test.ipynb) и последовательно выполните ячейки.

Доступные стратегии:

| Метод | Режим                                                                    |
|---|--------------------------------------------------------------------------|
| `simulator_1(initial_soc, dg_status)` | приоритетное использование СНЭЭ                                          |
| `simulator_2(initial_soc, dg_status)` | экономическая диспетчеризация СНЭЭ с учетом стоимости топлива            |
| `simulator_3(dg_status)` | базовый сценарий без СНЭЭ                                                |
| `simulator_4(initial_soc, dg_status)` | экономическая стратегия с 24-часовой проверкой возможности остановки ДГУ |

Минимальный пример Python:

```python
import numpy as np
import pandas as pd

from src.components.Battery import Battery
from src.components.DieselGenerator import DieselGenerator
from src.simulator.MicrogridSimulator import MicrogridSimulator

data = pd.read_excel("src/data/dataset.xlsx")

battery = Battery(
    capacity=151,
    soc_max_percent=100,
    soc_min_percent=20,
    charge_power_limit=75.5,
    discharge_power_limit=75.5,
    charge_efficiency_percent=98,
    discharge_efficiency_percent=98,
    self_discharge_percent=2,
)

generators = DieselGenerator(
    num_dgs=4,
    gen_capacity=110,
    a1=0.0101,
    a2=0.2654,
    fuel_price=54.6,
)

simulator = MicrogridSimulator(
    data=data,
    load_column="Load, kW",
    gen_column="Solar, kW",
    bess=battery,
    dgs=generators,
)

result = simulator.simulator_2(
    initial_soc=0.5,
    val_dgs=np.array([1, 1, 0, 0]),
)

print(result["p_bess_history"])
print(result["soc_history"])
```

Соглашение для `p_bess_history`:

- положительное значение — разряд СНЭЭ;
- отрицательное значение — заряд СНЭЭ;
- ноль — СНЭЭ не участвует в балансе на этом шаге.

## Запуск оптимизации

Оптимизация и графики находятся в [`src/tests/optim.ipynb`](src/tests/optim.ipynb). Ноутбук включает отдельные блоки для:

- оценки заданной пары `capacity`/`power`;
- смешанного генетического алгоритма `pymoo`;
- графика сходимости `lcos_convergence.png`;
- поверхности `lcos_surface.png`;
- чувствительности оптимальной емкости `lcos_optimal_sensitivity.png`;
- tornado-диаграммы `tornado_LCOS.png`.

Основные экономические и технические параметры находятся в словаре `BASE_PARAMETERS` первой кодовой ячейки.

Длительные расчеты защищены флагами:

```python
RUN_GA = False
RUN_SURFACE = False
RUN_TORNADO = False
```

Установите в `True` только нужный режим и выполните соответствующие ячейки. Поверхность LCOS запускает отдельную оптимизацию для каждой пары CAPEX и может выполняться значительно дольше одного GA-запуска.

В задаче оптимизации используются:

- `x0` — энергоемкость СНЭЭ, кВт·ч;
- `C1` — отношение мощности к энергоемкости: `0.5` или `1.0`;
- мощность СНЭЭ: `power = x0 * C1`, кВт;
- целевая функция — минимальный LCOS.

## Структура проекта

```text
masters-thesis/
├── README.md
├── LICENSE
├── requirements.txt
└── src/
    ├── components/
    │   ├── Battery.py             # модель СНЭЭ
    │   ├── DieselGenerator.py     # модель группы ДГУ
    │   └── Solar.py               # загрузка погоды и параметры площадки
    ├── financial/
    │   └── Economy.py             # NPV, IRR, LCOS и LCOE
    ├── simulator/
    │   ├── MicrogridSimulator.py  # стратегии диспетчеризации
    │   └── Optimization/
    │       ├── Fitness.py         # оценка проекта и целевая функция
    │       └── Optimization.py    # задача оптимизации pymoo
    ├── data/                      # входные и расчетные таблицы
    ├── plots/                     # создаваемые графики
    └── tests/
        ├── SolarGeneration.ipynb  # подготовка солнечной генерации
        ├── test.ipynb             # моделирование стратегий
        └── optim.ipynb            # оптимизация и чувствительность
```

## Лицензия

Проект распространяется по лицензии [MIT](LICENSE).

