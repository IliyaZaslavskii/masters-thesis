"""pymoo problem definition for battery capacity/power search."""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from pymoo.core.problem import ElementwiseProblem
from pymoo.core.variable import Choice, Integer


class OptProblem(ElementwiseProblem):
    """Optimize integer battery capacity and a discrete power ratio."""

    def __init__(self, objective: Callable[[Sequence[float]], object], lower_bound: int,
                 upper_bound: int, iteration_log_interval: Optional[int] = None) -> None:
        """Configure search variables and objective-history storage."""
        if lower_bound <= 0 or upper_bound < lower_bound:
            raise ValueError("Bounds must satisfy 0 < lower_bound <= upper_bound")
        if iteration_log_interval is not None and iteration_log_interval <= 0:
            raise ValueError("iteration_log_interval must be positive")
        self.objective = objective
        self.iteration_log_interval = iteration_log_interval
        self.iteration = 0
        self.best_value = float("inf")
        self.best_parameters = None
        self.history_best_value = []
        self.history_best_metrics = []
        super().__init__(vars={"x0": Integer(bounds=(lower_bound, upper_bound)),
                               "C1": Choice(options=[0.5, 1.0])}, n_obj=1,
                         n_ieq_constr=0, n_eq_constr=0)

    def _evaluate(self, variables: dict, output: dict, *args, **kwargs) -> None:
        """Evaluate one candidate and update monotonic best-so-far history."""
        capacity, ratio = float(variables["x0"]), float(variables["C1"])
        power = capacity * ratio
        result = self.objective([capacity, power])
        if hasattr(result, "lcos"):
            metrics = {"lcos": result.lcos, "npv_last": result.npv, "irr": result.irr, "h": result.hours}
        elif isinstance(result, tuple):
            metrics = dict(zip(("lcos", "npv_last", "irr", "h"), result))
        else:
            metrics = {"lcos": float(result), "npv_last": None, "irr": None, "h": None}
        lcos = float(metrics["lcos"])
        output["F"] = lcos
        if lcos <= self.best_value:
            self.best_value = lcos
            self.best_parameters = [capacity, power]
            metrics.update({"iter": self.iteration, "x0": capacity, "x1": power})
        self.history_best_value.append(self.best_value)
        self.history_best_metrics.append(dict(metrics))
        if self.iteration_log_interval and self.iteration % self.iteration_log_interval == 0:
            print(f"[{self.iteration:>4}] LCOS={lcos * 1e3:.3f} руб/кВт·ч; best={self.best_value * 1e3:.3f}")
        self.iteration += 1
