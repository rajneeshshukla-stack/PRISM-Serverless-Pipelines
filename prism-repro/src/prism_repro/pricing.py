"""Cost model (Eqs. (8)-(9), §III-D). All quantities in USD, seconds, GB."""
from __future__ import annotations

import numpy as np

from .config import Prices


def stage_cost(P, n_pc, n_od, n_cold, d, init, g, tau, prices: Prices, bill_init: bool = True):
    """Cost of one stage over an interval of tau seconds (Eq. (9)).

    P: provisioned environments; n_pc/n_od: executions served from provisioned /
    on-demand capacity; n_cold: cold starts (init billed at on-demand rate if
    bill_init); d: mean execution time (s); init: mean init time (s); g: GB.
    Broadcasting is supported.
    """
    c = (np.asarray(P) * g * tau * prices.pc
         + np.asarray(n_pc) * d * g * prices.pcd
         + np.asarray(n_od) * d * g * prices.od)
    if bill_init:
        c = c + np.asarray(n_cold) * init * g * prices.od
    return c


def request_cost(n_exec, n_stages: int, prices: Prices):
    return np.asarray(n_exec) * n_stages * prices.req


def break_even_utilisation(prices: Prices) -> float:
    return prices.pc / (prices.od - prices.pcd)
