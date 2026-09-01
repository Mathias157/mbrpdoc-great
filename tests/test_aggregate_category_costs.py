"""Unit tests for scripts/postprocessing/aggregate_category_costs.py's pure
logic.

Not wired into the main Snakefile's `rule test` / test_runner.py fixtures:
postprocessing is a deliberately separate flow (see docs/adr/0003) that
needs no GDX/HPC results, so these run standalone via
`pixi run pytest tests/test_aggregate_category_costs.py`.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.postprocessing.aggregate_category_costs import (  # noqa: E402
    aggregate_category_costs,
    build_reference_category_map,
)


def test_build_reference_category_map_uses_only_the_reference_scenario():
    categorization = pd.DataFrame(
        {
            "Scenario": ["base_R2050", "base_R2050", "HPN_R2050"],
            "Country": ["GERMANY", "DENMARK", "GERMANY"],
            "combined_category": [
                "High Demand / High Wind",
                "Low Demand / High Wind+Solar",
                "Low Demand / Low VRE",  # HPN relabels GERMANY - should be ignored
            ],
        }
    )
    category_map = build_reference_category_map(categorization, "base_R2050")
    assert category_map == {
        "GERMANY": "High Demand / High Wind",
        "DENMARK": "Low Demand / High Wind+Solar",
    }


def test_build_reference_category_map_missing_reference_scenario_is_empty():
    categorization = pd.DataFrame({"Scenario": ["base_R2050"], "Country": ["GERMANY"], "combined_category": ["High Demand / High Wind"]})
    assert build_reference_category_map(categorization, "HPN_R2050") == {}


def test_aggregate_category_costs_sums_and_converts_to_beur():
    combined = pd.DataFrame(
        {
            "Scenario": ["base_R2050", "base_R2050"],
            "Country": ["GERMANY", "DENMARK"],
            "Category": ["GENERATION_CAPITAL_COSTS", "GENERATION_CAPITAL_COSTS"],
            "Value": [1000.0, 500.0],  # M€
        }
    )
    category_map = {"GERMANY": "High Demand / High Wind", "DENMARK": "High Demand / High Wind"}

    result = aggregate_category_costs(combined, category_map, aggfunc="sum")

    assert result.to_dict("records") == [
        {"Scenario": "base_R2050", "combined_category": "High Demand / High Wind", "cost_beur": 1.5}
    ]


def test_aggregate_category_costs_applies_fixed_category_across_scenarios():
    combined = pd.DataFrame(
        {
            "Scenario": ["base_R2050", "HPN_R2050"],
            "Country": ["GERMANY", "GERMANY"],
            "Category": ["GENERATION_CAPITAL_COSTS", "GENERATION_CAPITAL_COSTS"],
            "Value": [1000.0, 1200.0],
        }
    )
    # Fixed from base_R2050 - HPN_R2050's own (unmapped) label for GERMANY is irrelevant here.
    category_map = {"GERMANY": "High Demand / High Wind"}

    result = aggregate_category_costs(combined, category_map, aggfunc="sum")

    assert set(result["combined_category"]) == {"High Demand / High Wind"}
    assert result.set_index("Scenario")["cost_beur"].to_dict() == {"base_R2050": 1.0, "HPN_R2050": 1.2}


def test_aggregate_category_costs_drops_countries_missing_from_category_map():
    combined = pd.DataFrame(
        {
            "Scenario": ["base_R2050", "base_R2050"],
            "Country": ["GERMANY", "MALTA"],  # MALTA has no modelled demand - excluded by categorize_countries.py
            "Category": ["GENERATION_CAPITAL_COSTS", "GENERATION_CAPITAL_COSTS"],
            "Value": [1000.0, 50.0],
        }
    )
    category_map = {"GERMANY": "High Demand / High Wind"}

    result = aggregate_category_costs(combined, category_map, aggfunc="sum")

    assert result.to_dict("records") == [
        {"Scenario": "base_R2050", "combined_category": "High Demand / High Wind", "cost_beur": 1.0}
    ]


def test_aggregate_category_costs_supports_mean_aggfunc():
    combined = pd.DataFrame(
        {
            "Scenario": ["base_R2050", "base_R2050"],
            "Country": ["GERMANY", "DENMARK"],
            "Category": ["GENERATION_CAPITAL_COSTS", "GENERATION_CAPITAL_COSTS"],
            "Value": [1000.0, 500.0],
        }
    )
    category_map = {"GERMANY": "High Demand / High Wind", "DENMARK": "High Demand / High Wind"}

    result = aggregate_category_costs(combined, category_map, aggfunc="mean")

    assert result.to_dict("records") == [
        {"Scenario": "base_R2050", "combined_category": "High Demand / High Wind", "cost_beur": 0.75}
    ]
