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
    FLEX_OPTIONS,
    _filter_area,
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
        extract_flex_option_values(None, {}, "V2G", "ELECTRICITY", "capacity")
    with pytest.raises(ValueError):
        extract_flex_option_values(None, {}, "Demand response", "ELECTRICITY", "capacity")


def test_extract_flex_option_values_allows_valid_metric_type_for_use_only_options():
    # "use" is valid for V2G, so the guard should pass through and fail only
    # once it tries to touch `model.results` on the None stand-in - proving
    # the ValueError guard itself didn't false-positive.
    with pytest.raises(Exception) as exc_info:
        extract_flex_option_values(None, {}, "V2G", "ELECTRICITY", "use")
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

    result = build_category_table(
        flex_values, scenario_metrics, category_map, "Individual PtH", "ELECTRICITY", "capacity", "demand"
    )

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
            "flex_option": "Individual PtH",
            "Commodity": "ELECTRICITY",
            "metric_type": "capacity",
            "direction": "demand",
            "group_type": "category",
        }
    ]


def test_build_category_table_drops_countries_missing_from_category_map():
    flex_values = _flex_values([("base_R2050", "2050", "MALTA", 1.0)])
    scenario_metrics = _scenario_metrics([("base_R2050", "2050", "MALTA", 1.0, 1.0, 1.0, 1.0)])

    result = build_category_table(
        flex_values, scenario_metrics, {}, "Individual PtH", "ELECTRICITY", "capacity", "demand"
    )

    assert result.empty


def test_build_category_table_returns_empty_for_country_less_flex_values():
    # Demand response's own shape: no Country column at all, so it can
    # never be assigned a category - build_category_table must recognise
    # this rather than crash on a missing "Country" column.
    flex_values = pd.DataFrame({"Scenario": ["base_R2050"], "Year": ["2050"], "Value": [1.0]})
    scenario_metrics = _scenario_metrics([("base_R2050", "2050", "GERMANY", 1.0, 1.0, 1.0, 1.0)])

    result = build_category_table(
        flex_values, scenario_metrics, {"GERMANY": "X"}, "Demand response", "ELECTRICITY", "use", "unsigned"
    )

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

    result = build_system_table(flex_values, sys_metrics, "Individual PtH", "ELECTRICITY", "capacity", "demand")

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
            "flex_option": "Individual PtH",
            "Commodity": "ELECTRICITY",
            "metric_type": "capacity",
            "direction": "demand",
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

    result = build_system_table(flex_values, sys_metrics, "Demand response", "ELECTRICITY", "use", "unsigned")

    assert result.loc[0, "flex_value"] == 42.0


def test_filter_area_contains_keeps_only_matching_rows():
    df = pd.DataFrame({"Area": ["A1_IND", "A1_IDVU", "A1"], "Value": [1, 2, 3]})

    result = _filter_area(df, {"area_contains": "IND"})

    assert result["Value"].tolist() == [1]


def test_filter_area_excludes_drops_any_matching_substring():
    df = pd.DataFrame({"Area": ["A1_IND", "A1_IDVU", "A1"], "Value": [1, 2, 3]})

    result = _filter_area(df, {"area_excludes": ["IND", "IDVU"]})

    assert result["Value"].tolist() == [3]


def test_filter_area_is_a_no_op_without_area_keys():
    df = pd.DataFrame({"Area": ["A1_IND"], "Value": [1]})

    assert _filter_area(df, {}) is df


def test_pth_split_by_area_covers_industrial_individual_and_district():
    # Every "PtH" variant reads the same technology and
    # only differs by Area filter (see docs/adr/0017) - regression-guard
    # against accidentally reintroducing a hardware-based split.
    for name in (
        "Industrial PtH",
        "Individual PtH",
        "District PtH",
    ):
        spec = FLEX_OPTIONS[name]["ELECTRICITY"]
        assert spec["technologies"] == ["ELECT-TO-HEAT"]
        assert "area_contains" in spec or "area_excludes" in spec


def test_fuel_cells_hydrogen_view_consumes_hydrogen_not_electricity():
    spec = FLEX_OPTIONS["Fuel cells"]["HYDROGEN"]
    assert spec["kind"] == "consumption"
    assert spec["fuel"] == "HYDROGEN"


def test_extract_flex_option_values_consumption_uses_configured_fuel_and_area():
    f_cons = pd.DataFrame(
        {
            "Scenario": ["TST_R2050"] * 2,
            "Year": ["2050"] * 2,
            "Country": ["A", "A"],
            "Area": ["A1_IND", "A1_IDVU"],
            "Technology": ["ELECT-TO-HEAT", "ELECT-TO-HEAT"],
            "Fuel": ["ELECTRIC", "ELECTRIC"],
            "Value": [10.0, 20.0],
        }
    )

    def get_symbol(symbol):
        assert symbol == "F_CONS_YCRA"
        return f_cons

    direction, rows = extract_flex_option_values(
        get_symbol, {}, "Industrial PtH", "ELECTRICITY", "use"
    )[0]

    assert direction == "demand"
    assert rows["Value"].sum() == -10.0


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
