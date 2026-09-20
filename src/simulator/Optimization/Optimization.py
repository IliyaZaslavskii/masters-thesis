import numpy as np
from pymoo.core.problem import ElementwiseProblem
from pymoo.core.variable import Integer, Choice

class OptProblem(ElementwiseProblem):
    def __init__(self, obj, lb, ub, iter_log=False):
        self.obj = obj
        self.iter_log = iter_log
        self.best_val = float('inf')
        self.iter = 0
        self.best_parms = None
        self.history_best_val = []
        self.history_best_metrics = []

        raw_x1 = [0.5, 1]
        vars = {
            "x0": Integer(bounds=(lb, ub)),
            "C1": Choice(options=raw_x1)
        }
        super().__init__(vars=vars, n_obj=1, n_ieq_constr=0, n_eq_constr=0)

    def _evaluate(self, X, out, *args, **kwargs):

        x0 = X["x0"]
        C = X["C1"]
        x1 = x0 * C
        f = self.obj([x0, x1])

        if isinstance(f, tuple):
            lcos, npv_last, irr, h = f
        else:
            lcos, npv_last, irr, h = f, None, None, None

        out["F"] = lcos

        if self.iter == 0:
            self.best_val = lcos
        if lcos <= self.best_val:
            self.best_val = lcos
            self.best_parms = [x0, x1]
            self.best_metrics = {
                'iter': self.iter,
                'lcos': lcos,
                'lcos_usdt_mwh': lcos * 1e6 / 85,
                'npv_last': npv_last,
                'irr': irr,
                'h': h,
                'x0': x0,
                'x1': x1,
            }
        self.history_best_val.append(self.best_val)
        self.history_best_metrics.append(dict(self.best_metrics))
        if self.iter_log and (self.iter % self.iter_log == 0):
            npv_str = f'{npv_last:.1f}' if npv_last is not None else 'N/A'
            irr_str = f'{irr * 100:.2f} %' if irr is not None else 'N/A'
            h_str = str(int(h)) if h is not None else 'N/A'
            print(
                f'[{self.iter:>4}]'
                f'LCOS={lcos * 1e3:.3f} руб/кВт·ч '
                f'({lcos * 1e6 / 85:.2f} $/MWh) | '
                f'NPV={npv_str} тыс.руб | '
                f'IRR={irr_str} | '
                f'Δh={h_str} ч | '
                f'x0={x0} кВт·ч  x1={x1:.1f} кВт | '
                f'best={self.best_val * 1e3:.3f}'
            )

        self.iter += 1