"""Unit tests for Network LMM / Ridge IRLS car-vs-driver skill isolation."""

from __future__ import annotations

from app.engine.network_lmm import solve_network_lmm


def test_lmm_isolates_car_performance_from_driver_skill():
    """Two equal-skill drivers in a +1.5% faster car and a baseline car connected across seasons
    should receive nearly identical driver alphas while car_gammas capture the ~1.5% car gap.
    """
    session_obs = []
    pair_obs = []

    # Season 1: Driver 1 & Driver 2 in FastCar (+1.5%), Driver 3 & Driver 4 in SlowCar (0.0%)
    # Season 2: Driver 2 moves to SlowCar and equals Driver 3 (connecting the graph!)
    for _ in range(12):
        # Season 1
        session_obs.extend(
            [
                {"driver_id": 1, "car_key": (1, 2024), "age": 27.0, "y": 1.8, "weight": 1.0},  # +0.3 driver + 1.5 car
                {"driver_id": 2, "car_key": (1, 2024), "age": 27.0, "y": 1.5, "weight": 1.0},  # 0.0 driver + 1.5 car
                {"driver_id": 3, "car_key": (2, 2024), "age": 27.0, "y": 0.0, "weight": 1.0},  # 0.0 driver + 0.0 car
                {"driver_id": 4, "car_key": (2, 2024), "age": 27.0, "y": -0.3, "weight": 1.0},  # -0.3 driver + 0.0 car
            ]
        )
        pair_obs.extend(
            [
                {"driver_i": 1, "driver_j": 2, "age_i": 27.0, "age_j": 27.0, "delta_y": 0.3, "weight": 1.0},
                {"driver_i": 3, "driver_j": 4, "age_i": 27.0, "age_j": 27.0, "delta_y": 0.3, "weight": 1.0},
            ]
        )
        # Season 2: Driver 2 joins SlowCar alongside Driver 3 -> equal pace!
        session_obs.extend(
            [
                {"driver_id": 2, "car_key": (2, 2025), "age": 28.0, "y": 0.0, "weight": 1.0},
                {"driver_id": 3, "car_key": (2, 2025), "age": 28.0, "y": 0.0, "weight": 1.0},
            ]
        )
        pair_obs.append(
            {"driver_i": 2, "driver_j": 3, "age_i": 28.0, "age_j": 28.0, "delta_y": 0.0, "weight": 1.0}
        )

    sol = solve_network_lmm(session_obs, pair_obs)
    alphas = sol["driver_alpha"]
    gammas = sol["car_gamma"]

    # Driver 1 > Driver 2 == Driver 3 > Driver 4
    assert alphas[1] > alphas[2]
    assert abs(alphas[2] - alphas[3]) < 0.08
    assert alphas[3] > alphas[4]
    # FastCar (1, 2024) should be ~1.5% faster than SlowCar (2, 2024)
    car_gap = gammas[(1, 2024)] - gammas[(2, 2024)]
    assert 1.2 < car_gap < 1.7
    # Car explains majority of raw variance
    assert sol["variance_decomposition"]["car_share_pct"] >= 70.0
