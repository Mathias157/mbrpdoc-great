"""Unit tests for scripts/postprocessing/estimate_flexibility_needs.py's
pure logic. See tests/test_categorize_countries.py's module docstring for
why this runs standalone via
`pixi run pytest tests/test_estimate_flexibility_needs.py`.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.postprocessing.estimate_flexibility_needs import (  # noqa: E402
    build_category_table,
    build_country_table,
    build_system_table,
    country_hourly_demand,
    country_hourly_supply,
    country_residual_load,
    flexibility_needs,
)


def _hourly_frame(week_values: dict) -> pd.DataFrame:
    """week_values: {season: [168 hourly values, T001..T168]}."""
    rows = [
        {"Season": season, "Time": f"T{i + 1:03d}", "Value": value}
        for season, values in week_values.items()
        for i, value in enumerate(values)
    ]
    return pd.DataFrame(rows)


def test_flexibility_needs_hierarchical_decomposition():
    # Week 1: day 1 flat at 0, day 2 flat at 10, days 3-7 flat at 5 (= the
    # week's own mean) -> no intra-day variation (Daily = 0), but day 1/2
    # deviate from the week mean (Weekly > 0).
    week1 = [0.0] * 24 + [10.0] * 24 + [5.0] * 120
    # Week 2: flat at 15 throughout -> no Daily or Weekly contribution, but
    # its week-mean (15) deviates from week 1's (5), so Annual > 0.
    week2 = [15.0] * 168
    rl = _hourly_frame({"S01": week1, "S02": week2})

    result = flexibility_needs(rl)

    assert result["Daily"] == pytest.approx(0.0)
    assert result["Weekly"] == pytest.approx(120 / 1e6)
    assert result["Annual"] == pytest.approx(840 / 1e6)


def test_country_hourly_demand_filters_scenario_year_and_category():
    el = pd.DataFrame(
        {
            "Scenario": ["TST_R2050"] * 3 + ["OTHER_R2050"],
            "Year": ["2050"] * 3 + ["2050"],
            "Country": ["A", "A", "A", "A"],
            "Season": ["S01"] * 4,
            "Time": ["T001"] * 4,
            "Category": ["EXOGENOUS", "ENDO_EV", "DIST_LOSSES", "EXOGENOUS"],
            "Value": [10, 5, 1, 99],
        }
    )

    exogenous_only = country_hourly_demand(el, ("EXOGENOUS",), "TST_R2050", "2050")
    assert exogenous_only["Value"].sum() == 10

    exogenous_and_ev = country_hourly_demand(el, ("EXOGENOUS", "ENDO_EV"), "TST_R2050", "2050")
    assert exogenous_and_ev["Value"].sum() == 15


def test_country_hourly_supply_filters_non_dispatchable_technologies():
    pro = pd.DataFrame(
        {
            "Scenario": ["TST_R2050"] * 3,
            "Year": ["2050"] * 3,
            "Country": ["A", "A", "A"],
            "Season": ["S01"] * 3,
            "Time": ["T001"] * 3,
            "Technology": ["WIND-ON", "HYDRO-RUN-OF-RIVER", "CONDENSING"],
            "Value": [10, 5, 100],
        }
    )

    supply = country_hourly_supply(pro, "TST_R2050", "2050")

    assert supply["Value"].sum() == 15


def test_country_residual_load_treats_missing_side_as_zero():
    demand = pd.DataFrame(
        {"Country": ["A", "B"], "Season": ["S01", "S01"], "Time": ["T001", "T001"], "Value": [10, 20]}
    )
    supply = pd.DataFrame({"Country": ["A"], "Season": ["S01"], "Time": ["T001"], "Value": [4]})

    rl = country_residual_load(demand, supply).set_index("Country")

    assert rl.loc["A", "Value"] == 6
    assert rl.loc["B", "Value"] == 20


def test_build_system_table_sums_across_countries():
    rl = pd.DataFrame(
        {
            "Country": ["A", "B"],
            "Season": ["S01", "S01"],
            "Time": ["T001", "T001"],
            "Value": [3.0, 4.0],
        }
    )

    result = build_system_table(rl, "TST_R2050", "2050")

    assert set(result["group_type"]) == {"system"}
    assert set(result["group"]) == {"All"}
    assert set(result["timescale"]) == {"Daily", "Weekly", "Annual"}


def test_build_category_table_drops_countries_missing_from_category_map():
    rl = pd.DataFrame(
        {
            "Country": ["A", "B"],
            "Season": ["S01", "S01"],
            "Time": ["T001", "T001"],
            "Value": [3.0, 4.0],
        }
    )
    category_map = {"A": "High Demand / High Wind"}

    result = build_category_table(rl, category_map, "TST_R2050", "2050")

    assert set(result["group"]) == {"High Demand / High Wind"}


def test_build_country_table_keeps_countries_separate():
    rl = pd.DataFrame(
        {
            "Country": ["A", "B"],
            "Season": ["S01", "S01"],
            "Time": ["T001", "T001"],
            "Value": [3.0, 4.0],
        }
    )

    result = build_country_table(rl, "TST_R2050", "2050")

    assert set(result["group"]) == {"A", "B"}
    assert set(result["group_type"]) == {"country"}
