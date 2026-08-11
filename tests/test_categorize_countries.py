"""Unit tests for scripts/categorize_countries.py's pure logic.

Not wired into the main Snakefile's `rule test` / test_runner.py fixtures:
postprocessing is a deliberately separate flow (see docs/adr/0003) that
needs no GDX/HPC results, so these run standalone via
`pixi run pytest tests/test_categorize_countries.py`.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.postprocessing.categorize_countries import (  # noqa: E402
    categorize_scenario,
    select_scenario_names,
)


def test_select_scenario_names_skips_investment_only():
    assert select_scenario_names(["EVN_INV"]) == []


def test_select_scenario_names_prefers_rolling_over_fullyear():
    assert select_scenario_names(["EVN_F2050", "EVN_R2050"]) == ["EVN_R2050"]


def test_select_scenario_names_keeps_fullyear_when_no_rolling_exists():
    assert select_scenario_names(["EVN_F2050"]) == ["EVN_F2050"]


def test_select_scenario_names_handles_weather_year_variant():
    # A future dimension (weather year) shouldn't need any code change -
    # the run-type/year suffix is still the last two underscore-parts.
    names = ["EVN_WY2001_R2050", "EVN_WY2001_F2050"]
    assert select_scenario_names(names) == ["EVN_WY2001_R2050"]


def _demand_frame(scenario: str, year: str, values: dict) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Scenario": scenario,
            "Year": year,
            "Country": list(values.keys()),
            "Value": list(values.values()),
        }
    )


def _production_frame(scenario: str, year: str, rows: list) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Scenario": scenario, "Year": year, "Country": country, "Technology": technology, "Value": value}
            for country, technology, value in rows
        ]
    )


def test_categorize_scenario_thresholds_are_mean_based():
    scenario, year = "TST_R2050", "2050"
    # A: high demand (20 > mean 15), B: low demand (10 < mean 15)
    el = _demand_frame(scenario, year, {"A": 15, "B": 5})
    h = _demand_frame(scenario, year, {"A": 5, "B": 5})
    h2 = pd.DataFrame(columns=["Scenario", "Year", "Country", "Value"])

    # A: wind_ratio = 10/20 = 0.5, solar_ratio = 0 -> mean wind = 0.3, mean solar = 0.1
    # B: wind_ratio = 1/10 = 0.1, solar_ratio = 2/10 = 0.2
    pro = _production_frame(
        scenario, year,
        [("A", "WIND-ON", 10), ("B", "WIND-ON", 1), ("B", "SOLAR-PV", 2)],
    )

    result = categorize_scenario(el, h, h2, pro, scenario).set_index("Country")

    assert result.loc["A", "demand_category"] == "High"
    assert result.loc["B", "demand_category"] == "Low"
    assert result.loc["A", "vre_category"] == "High Wind"
    assert result.loc["B", "vre_category"] == "High Solar"


def test_categorize_scenario_skips_zero_demand_countries():
    scenario, year = "TST_R2050", "2050"
    el = _demand_frame(scenario, year, {"A": 10, "B": 0})
    h = pd.DataFrame(columns=["Scenario", "Year", "Country", "Value"])
    h2 = pd.DataFrame(columns=["Scenario", "Year", "Country", "Value"])
    pro = _production_frame(scenario, year, [("A", "WIND-ON", 5)])

    result = categorize_scenario(el, h, h2, pro, scenario)

    assert list(result["Country"]) == ["A"]
