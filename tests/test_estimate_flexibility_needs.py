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
    HOURLY_FLEX_OPTIONS,
    _split_ev_dumb,
    build_category_table,
    build_country_table,
    build_flex_option_category_table,
    build_flex_option_country_table,
    build_flex_option_system_table,
    build_system_table,
    country_hourly_demand,
    country_hourly_supply,
    country_residual_load,
    flex_option_hourly_net,
    flex_sign,
    flexibility_needs,
    flexibility_provision,
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


def test_flexibility_provision_matches_geis_et_al_worked_example():
    # Geis et al. (2026) Appendix A.2's worked example: RL=[2,4],
    # P1=[2,8], P2=[0,-4] -> FlexNeed=1, FlexProv1=3, FlexProv2=-2, and the
    # two provisions sum exactly to the need (their proof of additivity,
    # Appendix A.1 - see docs/adr/0017). Both time steps land in the same
    # Day (T001/T002), so the daily mean equals the two-point average, the
    # same "ℓ-mean" their toy example uses.
    base = pd.DataFrame({"Season": ["S01", "S01"], "Time": ["T001", "T002"]})
    rl = base.assign(Value=[2.0, 4.0])
    p1 = base.assign(Value=[2.0, 8.0])
    p2 = base.assign(Value=[0.0, -4.0])

    need = flexibility_needs(rl)
    sign = flex_sign(rl)
    prov1 = flexibility_provision(p1, sign)
    prov2 = flexibility_provision(p2, sign)

    assert need["Daily"] == pytest.approx(1e-6)
    assert prov1["Daily"] == pytest.approx(3e-6)
    assert prov2["Daily"] == pytest.approx(-2e-6)
    assert prov1["Daily"] + prov2["Daily"] == pytest.approx(need["Daily"])


def test_flexibility_provision_sign_is_the_groups_own_not_the_options_own():
    # A technology whose own deviation runs *opposite* the system's need
    # gets a negative provision even though its own series alone is
    # "positive-leaning" - the point of the correlation-based method over a
    # fixed per-kind sign (see docs/adr/0011, superseded by 0017).
    base = pd.DataFrame({"Season": ["S01", "S01"], "Time": ["T001", "T002"]})
    rl = base.assign(Value=[10.0, 0.0])  # deviates high then low -> FlexSign [+1, -1]
    opposing = base.assign(Value=[0.0, 10.0])  # deviates low then high -> opposite phase

    sign = flex_sign(rl)
    provision = flexibility_provision(opposing, sign)

    assert provision["Daily"] < 0


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

    exogenous_and_losses = country_hourly_demand(el, ("EXOGENOUS", "DIST_LOSSES"), "TST_R2050", "2050")
    assert exogenous_and_losses["Value"].sum() == 11


def test_split_ev_dumb_removes_only_the_dumb_share_from_net_charging_hours():
    el = pd.DataFrame(
        {
            "Scenario": ["TST_R2050"] * 2,
            "Year": ["2050"] * 2,
            "Country": ["A", "A"],
            "Region": ["R1", "R1"],
            "Season": ["S01", "S01"],
            "Time": ["T001", "T002"],
            "Category": ["ENDO_EV", "ENDO_EV"],
            # T001: net charging (positive, demand-table convention) ->
            # dumb fraction applies. T002: net discharging (negative, V2G)
            # -> no "dumb charging" to lock in, left untouched.
            "Value": [100.0, -40.0],
        }
    )
    dumb_fraction = pd.DataFrame({"Year": ["2050"], "Region": ["R1"], "dumb_fraction": [0.1]})

    dumb, smart = _split_ev_dumb(el, dumb_fraction, "TST_R2050", "2050")

    assert dumb["Value"].tolist() == pytest.approx([10.0, 0.0])
    assert smart["Value"].tolist() == pytest.approx([90.0, -40.0])
    # Conserved: dumb + smart always reconstructs the raw series exactly.
    assert (dumb["Value"] + smart["Value"]).tolist() == pytest.approx([100.0, -40.0])


def test_split_ev_dumb_defaults_missing_region_fraction_to_zero():
    el = pd.DataFrame(
        {
            "Scenario": ["TST_R2050"],
            "Year": ["2050"],
            "Country": ["A"],
            "Region": ["UNKNOWN"],
            "Season": ["S01"],
            "Time": ["T001"],
            "Category": ["ENDO_EV"],
            "Value": [100.0],
        }
    )
    dumb_fraction = pd.DataFrame({"Year": ["2050"], "Region": ["R1"], "dumb_fraction": [0.5]})

    dumb, smart = _split_ev_dumb(el, dumb_fraction, "TST_R2050", "2050")

    assert dumb["Value"].iloc[0] == 0.0
    assert smart["Value"].iloc[0] == 100.0


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

    result = build_system_table(rl, "ELECTRICITY", "TST_R2050", "2050")

    assert set(result["group_type"]) == {"system_aggregate"}
    assert set(result["group"]) == {"All"}
    assert set(result["Commodity"]) == {"ELECTRICITY"}
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

    result = build_category_table(rl, category_map, "ELECTRICITY", "TST_R2050", "2050")

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
    category_map = {"A": "High Demand / High Wind"}

    result = build_country_table(rl, category_map, "ELECTRICITY", "TST_R2050", "2050")

    assert set(result["group"]) == {"A", "B"}
    assert set(result["group_type"]) == {"country"}


def test_build_country_table_tags_category_and_defaults_missing_to_empty():
    rl = pd.DataFrame(
        {
            "Country": ["A", "B"],
            "Season": ["S01", "S01"],
            "Time": ["T001", "T001"],
            "Value": [3.0, 4.0],
        }
    )
    category_map = {"A": "High Demand / High Wind"}

    result = build_country_table(rl, category_map, "ELECTRICITY", "TST_R2050", "2050").set_index("group")

    assert (result.loc["A", "category"] == "High Demand / High Wind").all()
    assert (result.loc["B", "category"] == "").all()


def test_hourly_flex_options_excludes_only_demand_response():
    # DR_FLEX_Y has no "ST" (hourly) counterpart (see docs/adr/0007), so
    # Demand response passively falls into the "Other" catch-all instead of
    # ever appearing as a named row. V2G (unlike before docs/adr/0016) does
    # have an hourly form - EL_DEMAND_YCRST's ENDO_EV category - so it's
    # included here.
    flex_option_names = {flex_option for flex_option, _, _ in HOURLY_FLEX_OPTIONS}
    assert "Demand response" not in flex_option_names
    assert "V2G" in flex_option_names
    assert "District PtH" in flex_option_names
    assert "Fuel cells" in flex_option_names
    assert "Electricity transmission" in flex_option_names
    assert "Peaker" in flex_option_names


def test_flex_option_hourly_net_production_filters_scenario_year_and_technology():
    pro = pd.DataFrame(
        {
            "Scenario": ["TST_R2050"] * 3 + ["OTHER_R2050"],
            "Year": ["2050"] * 3 + ["2050"],
            "Country": ["A", "A", "A", "A"],
            "Area": ["A1", "A1", "A1", "A1"],
            "Commodity": ["HEAT"] * 4,
            "Season": ["S01"] * 4,
            "Time": ["T001"] * 4,
            "Technology": ["ELECT-TO-HEAT", "ELECT-TO-HEAT", "CONDENSING", "ELECT-TO-HEAT"],
            "Value": [10, 5, 100, 99],
        }
    )
    spec = {"kind": "production", "technologies": ["ELECT-TO-HEAT"]}
    empty = pd.DataFrame()

    result = flex_option_hourly_net(
        spec, "HEAT", pro, empty, {}, empty, empty, {}, "TST_R2050", "2050"
    )

    assert result["Value"].sum() == 15


def test_flex_option_hourly_net_production_applies_area_filter():
    pro = pd.DataFrame(
        {
            "Scenario": ["TST_R2050"] * 2,
            "Year": ["2050"] * 2,
            "Country": ["A", "A"],
            "Area": ["A1_IND", "A1_IDVU"],
            "Commodity": ["HEAT", "HEAT"],
            "Season": ["S01", "S01"],
            "Time": ["T001", "T001"],
            "Technology": ["ELECT-TO-HEAT", "ELECT-TO-HEAT"],
            "Value": [10, 20],
        }
    )
    spec = {"kind": "production", "technologies": ["ELECT-TO-HEAT"], "area_contains": "IND"}
    empty = pd.DataFrame()

    result = flex_option_hourly_net(
        spec, "HEAT", pro, empty, {}, empty, empty, {}, "TST_R2050", "2050"
    )

    assert result["Value"].sum() == 10


def test_flex_option_hourly_net_consumption_uses_configured_fuel():
    f_cons = pd.DataFrame(
        {
            "Scenario": ["TST_R2050"] * 2,
            "Year": ["2050"] * 2,
            "Country": ["A", "A"],
            "Area": ["A1", "A1"],
            "Season": ["S01", "S01"],
            "Time": ["T001", "T001"],
            "Technology": ["FUELCELL", "FUELCELL"],
            "Fuel": ["HYDROGEN", "ELECTRIC"],
            "Value": [7.0, 100.0],
        }
    )
    spec = {"kind": "consumption", "technologies": ["FUELCELL"], "fuel": "HYDROGEN"}
    empty = pd.DataFrame()

    result = flex_option_hourly_net(
        spec, "HYDROGEN", empty, f_cons, {}, empty, empty, {}, "TST_R2050", "2050"
    )

    # Consumption is reported as negative net dispatch (withdraws from the
    # commodity balance) - only the HYDROGEN=Fuel row should count.
    assert result["Value"].sum() == -7.0


def test_flex_option_hourly_net_consumption_hourly_category_reads_demand_symbol():
    el = pd.DataFrame(
        {
            "Scenario": ["TST_R2050"] * 2,
            "Year": ["2050"] * 2,
            "Country": ["A", "A"],
            "Season": ["S01", "S01"],
            "Time": ["T001", "T001"],
            "Category": ["ENDO_H2", "EXOGENOUS"],
            "Value": [12.0, 999.0],
        }
    )
    spec = {"kind": "consumption", "technologies": ["ELECTROLYZER"], "hourly_category": "ENDO_H2"}
    empty = pd.DataFrame()

    result = flex_option_hourly_net(
        spec, "ELECTRICITY", empty, empty, {"ELECTRICITY": el}, empty, empty, {}, "TST_R2050", "2050"
    )

    assert result["Value"].sum() == -12.0


def test_flex_option_hourly_net_net_category_signed_uses_ev_smart_hourly_override():
    el = pd.DataFrame(
        {
            "Scenario": ["TST_R2050"],
            "Year": ["2050"],
            "Country": ["A"],
            "Season": ["S01"],
            "Time": ["T001"],
            "Category": ["ENDO_EV"],
            "Value": [1000.0],  # would dominate the result if not overridden
        }
    )
    ev_smart_hourly = pd.DataFrame(
        {"Country": ["A"], "Season": ["S01"], "Time": ["T001"], "Value": [40.0]}
    )
    spec = {"kind": "net_category_signed", "category": "ENDO_EV", "direction": "demand"}
    empty = pd.DataFrame()

    result = flex_option_hourly_net(
        spec, "ELECTRICITY", empty, empty, {"ELECTRICITY": el}, empty, empty, {}, "TST_R2050", "2050",
        ev_smart_hourly=ev_smart_hourly,
    )

    # 40 (demand-table convention) -> -40 (positive=supply convention) ->
    # clipped to <=0 for "demand" direction -> -40, not derived from the
    # raw (overridden) 1000 value.
    assert result["Value"].sum() == -40.0


def test_flex_option_hourly_net_transmission_nets_import_minus_export_and_filters_symbol():
    # A exports 10 to B, and separately imports 4 from B, both at T001 -
    # X_FLOW_YCR's "Country" column is always the *exporting* region's
    # country (see docs/adr/0019), so A's own net position is import(4) -
    # export(10) = -6, and B's is import(10) - export(4) = 6. Intra-country
    # flow (C1 -> C2, both mapped to "C") at T002 must cancel to 0.
    x_flow = pd.DataFrame(
        {
            "Scenario": ["TST_R2050", "TST_R2050", "TST_R2050"],
            "Year": ["2050", "2050", "2050"],
            "Country": ["A", "B", "C"],
            "From": ["A1", "B1", "C1"],
            "To": ["B1", "A1", "C2"],
            "Season": ["S01", "S01", "S01"],
            "Time": ["T001", "T001", "T002"],
            "Value": [10, 4, 7],
        }
    )
    xh2_flow = pd.DataFrame(columns=x_flow.columns)
    spec = {"kind": "transmission", "capacity_symbol": "X_CAP_YCR", "use_symbol": "X_FLOW_YCR"}
    region_to_country = {"A1": "A", "B1": "B", "C1": "C", "C2": "C"}
    empty = pd.DataFrame()

    result = flex_option_hourly_net(
        spec, "ELECTRICITY", empty, empty, {}, x_flow, xh2_flow, region_to_country, "TST_R2050", "2050"
    )

    by_country = result.set_index("Country")["Value"]
    assert by_country["A"] == -6
    assert by_country["B"] == 6
    assert by_country["C"] == 0


def test_flex_option_hourly_net_peaker_maps_region_to_country_and_filters_backup():
    pro = pd.DataFrame(
        {
            "Scenario": ["TST_R2050"] * 2,
            "Year": ["2050"] * 2,
            "Region": ["R1", "R1"],
            "Season": ["S01"] * 2,
            "Time": ["T001"] * 2,
            "Commodity": ["ELECTRICITY", "ELECTRICITY"],
            "Generation": ["GNR_BACKUP_CONDENSING", "GNR_NORMAL_CONDENSING"],
            "Value": [7, 100],
        }
    )
    spec = {"kind": "peaker"}
    empty = pd.DataFrame()

    result = flex_option_hourly_net(
        spec, "ELECTRICITY", pro, empty, {}, empty, empty, {"R1": "A"}, "TST_R2050", "2050"
    )

    assert result["Value"].sum() == 7
    assert set(result["Country"]) == {"A"}


def test_flex_option_hourly_net_rejects_non_hourly_kind():
    empty = pd.DataFrame()
    with pytest.raises(ValueError):
        flex_option_hourly_net(
            {"kind": "system_only"}, "ELECTRICITY", empty, empty, {}, empty, empty, {}, "TST_R2050", "2050"
        )


def test_build_flex_option_system_table_uses_the_groups_own_sign():
    hourly_net = pd.DataFrame(
        {
            "Country": ["A", "B"],
            "Season": ["S01", "S01"],
            "Time": ["T001", "T001"],
            "Value": [3.0, 4.0],
        }
    )
    sign = pd.DataFrame({
        "Season": ["S01"], "Time": ["T001"], "Daily": [1.0], "Weekly": [1.0], "Annual": [1.0],
    })

    result = build_flex_option_system_table(hourly_net, sign, "Fuel cells", "ELECTRICITY", "TST_R2050", "2050")

    assert set(result["group_type"]) == {"flex_option_system_aggregate"}
    assert set(result["group"]) == {"All"}
    assert set(result["flex_option"]) == {"Fuel cells"}


def test_build_flex_option_category_table_drops_countries_missing_from_category_map():
    hourly_net = pd.DataFrame(
        {
            "Country": ["A", "B"],
            "Season": ["S01", "S01"],
            "Time": ["T001", "T001"],
            "Value": [3.0, 4.0],
        }
    )
    category_map = {"A": "High Demand / High Wind"}
    signs = {
        "High Demand / High Wind": pd.DataFrame({
            "Season": ["S01"], "Time": ["T001"], "Daily": [1.0], "Weekly": [1.0], "Annual": [1.0],
        })
    }

    result = build_flex_option_category_table(
        hourly_net, category_map, signs, "Fuel cells", "ELECTRICITY", "TST_R2050", "2050"
    )

    assert set(result["group"]) == {"High Demand / High Wind"}
    assert set(result["group_type"]) == {"flex_option_category_aggregate"}
    assert set(result["flex_option"]) == {"Fuel cells"}


def test_build_flex_option_category_table_skips_groups_with_no_sign():
    hourly_net = pd.DataFrame(
        {
            "Country": ["A"],
            "Season": ["S01"],
            "Time": ["T001"],
            "Value": [3.0],
        }
    )
    category_map = {"A": "High Demand / High Wind"}

    result = build_flex_option_category_table(
        hourly_net, category_map, {}, "Fuel cells", "ELECTRICITY", "TST_R2050", "2050"
    )

    assert result.empty


def test_build_flex_option_country_table_uses_each_countrys_own_sign():
    hourly_net = pd.DataFrame(
        {
            "Country": ["A", "A", "B", "B"],
            "Season": ["S01", "S01", "S01", "S01"],
            "Time": ["T001", "T002", "T001", "T002"],
            "Value": [2.0, 8.0, 0.0, -4.0],
        }
    )
    category_map = {"A": "High Demand / High Wind"}
    # Geis et al.'s own worked example (see
    # test_flexibility_provision_matches_geis_et_al_worked_example) reused
    # per country - both hours land in the same Day, so FlexProv should
    # again come out to 3e-6/-2e-6 for A/B respectively.
    sign = pd.DataFrame({
        "Season": ["S01", "S01"], "Time": ["T001", "T002"], "Daily": [-1.0, 1.0],
        "Weekly": [0.0, 0.0], "Annual": [0.0, 0.0],
    })
    signs = {"A": sign, "B": sign}

    result = build_flex_option_country_table(
        hourly_net, category_map, signs, "Fuel cells", "ELECTRICITY", "TST_R2050", "2050"
    ).set_index("group")

    assert set(result.index) == {"A", "B"}
    assert set(result["group_type"]) == {"flex_option_country"}
    assert result.loc["A"].set_index("timescale").loc["Daily", "flex_need_twh"] == pytest.approx(3e-6)
    assert result.loc["B"].set_index("timescale").loc["Daily", "flex_need_twh"] == pytest.approx(-2e-6)
    assert (result.loc["A", "category"] == "High Demand / High Wind").all()
    assert (result.loc["B", "category"] == "").all()


def test_build_flex_option_country_table_skips_countries_with_no_sign():
    hourly_net = pd.DataFrame(
        {"Country": ["A"], "Season": ["S01"], "Time": ["T001"], "Value": [3.0]}
    )

    result = build_flex_option_country_table(
        hourly_net, {}, {}, "Fuel cells", "ELECTRICITY", "TST_R2050", "2050"
    )

    assert result.empty
