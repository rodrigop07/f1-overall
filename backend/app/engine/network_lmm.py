"""Network LMM / Ridge IRLS solver for isolating Driver Skill vs Car-Season Performance & Age Curve."""

from __future__ import annotations

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import lsqr

from app.engine.hygiene import robust_mad


def solve_network_lmm(
    session_obs: list[dict],
    pair_obs: list[dict],
    lambda_driver: float = 6.0,
    lambda_car: float = 1.5,
    lambda_age_lin: float = 120.0,
    lambda_age_quad: float = 4000.0,
    irls_iters: int = 3,
) -> dict:
    """Solve y ~ alpha_driver + gamma_car_season + beta1*(age-27) + beta2*(age-27)^2
    jointly with same-session teammate pair differences via sparse Ridge IRLS.

    Args:
        session_obs: list of dicts with keys:
            'driver_id', 'car_key' (team_id, year), 'age', 'y', 'weight'
        pair_obs: list of dicts with keys:
            'driver_i', 'driver_j', 'age_i', 'age_j', 'delta_y', 'weight'

    Returns:
        dict containing:
            'driver_alpha': {driver_id: float}
            'car_gamma': {(team_id, year): float}
            'age_beta': (beta1, beta2)
            'variance_decomposition': dict
    """
    driver_ids = sorted(
        {o["driver_id"] for o in session_obs}
        | {p["driver_i"] for p in pair_obs}
        | {p["driver_j"] for p in pair_obs}
    )
    car_keys = sorted({o["car_key"] for o in session_obs})

    if not driver_ids or (not session_obs and not pair_obs):
        return {
            "driver_alpha": {},
            "car_gamma": {},
            "age_beta": (0.0, 0.0),
            "variance_decomposition": {
                "car_share_pct": 80.0,
                "driver_share_pct": 20.0,
                "total_explained_r2": 0.0,
            },
        }

    d_idx = {d: i for i, d in enumerate(driver_ids)}
    c_idx = {c: i for i, c in enumerate(car_keys)}
    n_d = len(driver_ids)
    n_c = len(car_keys)
    n_cols = n_d + n_c + 2  # alphas, gammas, beta1, beta2
    b1_col = n_d + n_c
    b2_col = n_d + n_c + 1

    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    rhs: list[float] = []
    base_weights: list[float] = []
    is_data_row: list[bool] = []

    r_ptr = 0
    # 1. Session observations: alpha_d + gamma_c + b1*a + b2*a^2 = y
    for o in session_obs:
        di = d_idx[o["driver_id"]]
        ci = n_d + c_idx[o["car_key"]]
        age_c = float(o.get("age") if o.get("age") is not None else 29.0) - 27.0
        age_c = float(np.clip(age_c, -10.0, 20.0))

        rows.extend([r_ptr, r_ptr, r_ptr, r_ptr])
        cols.extend([di, ci, b1_col, b2_col])
        vals.extend([1.0, 1.0, age_c, age_c * age_c])
        rhs.append(float(o["y"]))
        base_weights.append(float(o.get("weight", 1.0)))
        is_data_row.append(True)
        r_ptr += 1

    n_sess = r_ptr

    # 2. Direct same-session teammate pair differences: (alpha_i - alpha_j) + age diff = delta
    for p in pair_obs:
        di = d_idx[p["driver_i"]]
        dj = d_idx[p["driver_j"]]
        if di == dj:
            continue
        ai = float(np.clip((p.get("age_i") if p.get("age_i") is not None else 29.0) - 27.0, -10.0, 20.0))
        aj = float(np.clip((p.get("age_j") if p.get("age_j") is not None else 29.0) - 27.0, -10.0, 20.0))

        rows.extend([r_ptr, r_ptr, r_ptr, r_ptr])
        cols.extend([di, dj, b1_col, b2_col])
        vals.extend([1.0, -1.0, ai - aj, ai * ai - aj * aj])
        rhs.append(float(p["delta_y"]))
        base_weights.append(float(p.get("weight", 1.0)) * 2.5)
        is_data_row.append(True)
        r_ptr += 1

    n_data = r_ptr

    # 3. Ridge regularization rows
    sq_ld = np.sqrt(lambda_driver)
    for i in range(n_d):
        rows.append(r_ptr)
        cols.append(i)
        vals.append(sq_ld)
        rhs.append(0.0)
        base_weights.append(1.0)
        is_data_row.append(False)
        r_ptr += 1

    sq_lc = np.sqrt(lambda_car)
    for j in range(n_c):
        rows.append(r_ptr)
        cols.append(n_d + j)
        vals.append(sq_lc)
        rhs.append(0.0)
        base_weights.append(1.0)
        is_data_row.append(False)
        r_ptr += 1

    # Age curve regularization
    rows.extend([r_ptr, r_ptr + 1])
    cols.extend([b1_col, b2_col])
    vals.extend([np.sqrt(lambda_age_lin), np.sqrt(lambda_age_quad)])
    rhs.extend([0.0, 0.0])
    base_weights.extend([1.0, 1.0])
    is_data_row.extend([False, False])
    r_ptr += 2

    X = sparse.csr_matrix((vals, (rows, cols)), shape=(r_ptr, n_cols), dtype=float)
    y_vec = np.asarray(rhs, dtype=float)
    w_base = np.asarray(base_weights, dtype=float)
    data_mask = np.asarray(is_data_row, dtype=bool)

    irls_w = w_base.copy()
    x_hat = np.zeros(n_cols, dtype=float)

    for _ in range(max(1, irls_iters)):
        sqrt_w = np.sqrt(irls_w)
        X_w = X.multiply(sqrt_w[:, None])
        y_w = y_vec * sqrt_w
        sol = lsqr(X_w, y_w, atol=1e-8, btol=1e-8, iter_lim=5000)
        x_hat = sol[0]

        resid = y_vec[data_mask] - X[data_mask].dot(x_hat)
        scale = robust_mad(resid) or 0.5
        scale = max(scale, 0.15)
        k_huber = 2.0 * scale
        abs_r = np.abs(resid)
        huber_factor = np.where(abs_r <= k_huber, 1.0, k_huber / np.maximum(abs_r, 1e-9))
        irls_w = w_base.copy()
        irls_w[data_mask] = w_base[data_mask] * huber_factor

    alphas_raw = x_hat[:n_d]
    gammas_raw = x_hat[n_d : n_d + n_c]
    beta1 = float(x_hat[b1_col])
    beta2 = float(x_hat[b2_col])

    # Center alphas & gammas around zero across observed session entries for clean interpretation
    alpha_center = float(np.mean(alphas_raw)) if alphas_raw.size else 0.0
    alphas_raw = alphas_raw - alpha_center
    gammas_raw = gammas_raw + alpha_center

    driver_alpha = {d: float(alphas_raw[i]) for i, d in enumerate(driver_ids)}
    car_gamma = {c: float(gammas_raw[j]) for j, c in enumerate(car_keys)}

    # Variance decomposition on session observations
    var_decomp = {
        "car_share_pct": 80.0,
        "driver_share_pct": 20.0,
        "total_explained_r2": 0.0,
        "n_session_obs": n_sess,
        "n_pair_obs": n_data - n_sess,
    }
    if n_sess >= 30:
        y_sess = y_vec[:n_sess]
        car_pred = np.array([car_gamma[o["car_key"]] for o in session_obs], dtype=float)
        drv_pred = np.array(
            [
                driver_alpha[o["driver_id"]]
                + beta1 * float(np.clip((o.get("age") or 29.0) - 27.0, -10.0, 20.0))
                + beta2 * (float(np.clip((o.get("age") or 29.0) - 27.0, -10.0, 20.0)) ** 2)
                for o in session_obs
            ],
            dtype=float,
        )
        v_car = float(np.var(car_pred))
        v_drv = float(np.var(drv_pred))
        v_tot = float(np.var(y_sess))
        v_res = float(np.var(y_sess - car_pred - drv_pred))
        denom = max(v_car + v_drv, 1e-9)
        var_decomp = {
            "car_share_pct": round(100.0 * v_car / denom, 2),
            "driver_share_pct": round(100.0 * v_drv / denom, 2),
            "total_explained_r2": round(max(0.0, 1.0 - v_res / max(v_tot, 1e-9)), 4),
            "car_std_pct": round(float(np.sqrt(v_car)), 4),
            "driver_std_pct": round(float(np.sqrt(v_drv)), 4),
            "n_session_obs": n_sess,
            "n_pair_obs": n_data - n_sess,
        }

    return {
        "driver_alpha": driver_alpha,
        "car_gamma": car_gamma,
        "age_beta": (beta1, beta2),
        "variance_decomposition": var_decomp,
    }


def age_effect(age_years: float | None, beta: tuple[float, float]) -> float:
    """Evaluate quadratic age effect centered at age 27."""
    if age_years is None:
        a = 2.0
    else:
        a = float(np.clip(age_years - 27.0, -10.0, 20.0))
    return beta[0] * a + beta[1] * (a * a)
