"""Unit tests for scripts/postprocessing/flex_option_metrics.py's pure logic.

Not wired into the main Snakefile's `rule test` / test_runner.py fixtures:
postprocessing is a deliberately separate flow (see docs/adr/0003) that
needs no GDX/HPC results, so these run standalone via
`pixi run pytest tests/test_flex_option_metrics.py`.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.postprocessing.flex_option_metrics import (  # noqa: E402
    build_category_table,
    build_system_table,
    extract_flex_option_values,
    system_totals,
)


def test_extract_flex_option_values_rejects_invalid_metric_type():
    # V2G and Demand response are use-only (exogenous capacity assumption,
    # not an optimised decision) - requesting "capacity" must fail before
    # ever touching `model` (passed as None here).
    with pytest.raises(ValueError):
        extract_flex_option_values(None, {}, "V2G", "capacity")
    with pytest.raises(ValueError):
        extract_flex_option_values(None, {}, "Demand response", "capacity")


def test_extract_flex_option_values_allows_valid_metric_type_for_use_only_options():
    # "use" is valid for V2G, so the guard should pass through and fail only
    # once it tries to touch `model.results` on the None stand-in - proving
    # the ValueError guard itself didn't false-positive.
    with pytest.raises(Exception) as exc_info:
        extract_flex_option_values(None, {}, "V2G", "use")
    assert not isinstance(exc_info.value, ValueError)


def _flex_values(rows):
    return pd.DataFrame(rows, columns=["Scenario", "Year", "Country", "Value"])


def _scenario_metrics(rows):
    return pd.DataFrame(rows, columns=["Scenario", "Year", "Country", "cost_beur", "emissions_kton", "lole_h", "ens_twh"])


def test_build_category_table_sums_within_category():
    flex_values = _flex_values(
        [
            ("base_R2050", "2050", "GERMANY", 10.0),
            ("base_R2050", "2050", "DENMARK", 5.0),
        ]
    )
    scenario_metrics = _scenario_metrics(
        [
            ("base_R2050", "2050", "GERMANY", 100.0, 50.0, 2.0, 1.0),
            ("base_R2050", "2050", "DENMARK", 20.0, 10.0, 1.0, 2.0),
        ]
    )
    category_map = {"GERMANY": "High Demand / High Wind", "DENMARK": "High Demand / High Wind"}

    result = build_category_table(flex_values, scenario_metrics, category_map, "Heat pumps", "capacity")

    assert result.to_dict("records") == [
        {
            "Scenario": "base_R2050",
            "Year": "2050",
            "group": "High Demand / High Wind",
            "flex_value": 15.0,
            "cost_beur": 120.0,
            "emissions_kton": 60.0,
            "lole_h": 3.0,
            "ens_twh": 3.0,
            "flex_option": "Heat pumps",
            "metric_type": "capacity",
            "group_type": "category",
        }
    ]


def test_build_category_table_drops_countries_missing_from_category_map():
    flex_values = _flex_values([("base_R2050", "2050", "MALTA", 1.0)])
    scenario_metrics = _scenario_metrics([("base_R2050", "2050", "MALTA", 1.0, 1.0, 1.0, 1.0)])

    result = build_category_table(flex_values, scenario_metrics, {}, "Heat pumps", "capacity")

    assert result.empty


def test_build_category_table_returns_empty_for_country_less_flex_values():
    # Demand response's own shape: no Country column at all, so it can
    # never be assigned a category - build_category_table must recognise
    # this rather than crash on a missing "Country" column.
    flex_values = pd.DataFrame({"Scenario": ["base_R2050"], "Year": ["2050"], "Value": [1.0]})
    scenario_metrics = _scenario_metrics([("base_R2050", "2050", "GERMANY", 1.0, 1.0, 1.0, 1.0)])

    result = build_category_table(flex_values, scenario_metrics, {"GERMANY": "X"}, "Demand response", "use")

    assert result.empty


def test_build_system_table_sums_flex_value_across_countries():
    flex_values = _flex_values(
        [
            ("base_R2050", "2050", "GERMANY", 10.0),
            ("base_R2050", "2050", "DENMARK", 5.0),
        ]
    )
    sys_metrics = pd.DataFrame(
        {
            "Scenario": ["base_R2050"],
            "Year": ["2050"],
            "cost_beur": [120.0],
            "emissions_kton": [60.0],
            "lole_h": [3.0],
            "ens_twh": [3.0],
        }
    )

    result = build_system_table(flex_values, sys_metrics, "Heat pumps", "capacity")

    assert result.to_dict("records") == [
        {
            "Scenario": "base_R2050",
            "Year": "2050",
            "flex_value": 15.0,
            "cost_beur": 120.0,
            "emissions_kton": 60.0,
            "lole_h": 3.0,
            "ens_twh": 3.0,
            "group": "All",
            "flex_option": "Heat pumps",
            "metric_type": "capacity",
            "group_type": "system",
        }
    ]


def test_build_system_table_handles_country_less_flex_values_directly():
    # Demand response's own shape: no Country column, already a system
    # total - build_system_table shouldn't try (and fail) to sum it again.
    flex_values = pd.DataFrame({"Scenario": ["base_R2050"], "Year": ["2050"], "Value": [42.0]})
    sys_metrics = pd.DataFrame(
        {
            "Scenario": ["base_R2050"],
            "Year": ["2050"],
            "cost_beur": [120.0],
            "emissions_kton": [60.0],
            "lole_h": [3.0],
            "ens_twh": [3.0],
        }
    )

    result = build_system_table(flex_values, sys_metrics, "Demand response", "use")

    assert result.loc[0, "flex_value"] == 42.0


def test_system_totals_sums_across_countries():
    scenario_metrics = _scenario_metrics(
        [
            ("base_R2050", "2050", "GERMANY", 100.0, 50.0, 2.0, 1.0),
            ("base_R2050", "2050", "DENMARK", 20.0, 10.0, 1.0, 2.0),
        ]
    )

    result = system_totals(scenario_metrics)

    assert result.to_dict("records") == [
        {"Scenario": "base_R2050", "Year": "2050", "cost_beur": 120.0, "emissions_kton": 60.0, "lole_h": 3.0, "ens_twh": 3.0}
    ]
