"""
Categorize Balmorel Scenario Results by Demand and VRE Type

For each country in each fullyear/rolling scenario result, labels Demand as
High/Low and VRE type as High Wind / High Solar / High Wind+Solar / Low VRE,
by comparing that country against the mean of all countries within the same
scenario name. See CONTEXT.md ("Scenario name", "Demand category", "VRE
category") for the precise definitions, and docs/adr/0003 for why this
script lives in top-level scripts/ and is driven by postprocess.smk rather
than the main DAG.

Created on 11.08.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import re
import sys
from importlib import resources
from pathlib import Path

# Add repo root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import click
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from decouple import config
from matplotlib.colors import to_rgba
from pybalmorel import Balmorel, geofiles

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

WIND_TECHNOLOGIES = ["WIND-ON", "WIND-OFF"]
SOLAR_TECHNOLOGIES = ["SOLAR-PV"]

# Trailing suffix on a scenario name that marks it as a dispatch (not
# investment) result, e.g. "EVN_R2050" -> base="EVN", run_type="R", year="2050".
RUN_TYPE_RE = re.compile(r"^(?P<base>.+)_(?P<run_type>F|R)(?P<year>\d{4})$")

# Fixed vocabulary so every map uses the same colour for the same category,
# regardless of which categories actually occur in a given scenario.
COMBINED_CATEGORIES = [
    f"{demand} Demand / {vre}"
    for demand in ("High", "Low")
    for vre in ("High Wind", "High Solar", "High Wind+Solar", "Low VRE")
]
CATEGORY_COLOURS = {
    category: plt.get_cmap("tab10")(i) for i, category in enumerate(COMBINED_CATEGORIES)
}


def select_scenario_names(scenario_names: list) -> list:
    """Fullyear/rolling results only (skips investment-only ``_INV`` names).
    When both a fullyear (``_F<year>``) and rolling (``_R<year>``) result
    exist for the same base scenario and year, keeps the rolling one."""
    chosen = {}
    for name in scenario_names:
        match = RUN_TYPE_RE.match(name)
        if not match:
            continue

        key = (match.group("base"), match.group("year"))
        run_type = match.group("run_type")
        if key not in chosen or (chosen[key][1] == "F" and run_type == "R"):
            chosen[key] = (name, run_type)

    return [name for name, _ in chosen.values()]


def scenario_target_year(*demand_frames: pd.DataFrame, scenario_name: str) -> str | None:
    """The single year a fullyear/rolling result represents. Takes the max
    year present across the demand symbols, in case more than one is echoed."""
    years = pd.concat(
        [frame.loc[frame["Scenario"] == scenario_name, "Year"] for frame in demand_frames]
    )
    if years.empty:
        return None
    return str(max(int(year) for year in years.unique()))


def country_demand(el: pd.DataFrame, h: pd.DataFrame, h2: pd.DataFrame, scenario_name: str, year: str) -> pd.Series:
    """Total demand (TWh) per country: electricity + heat + hydrogen summed
    directly, since all three are already in the same unit."""
    query = "Scenario == @scenario_name and Year == @year"
    parts = [frame.query(query).groupby("Country")["Value"].sum() for frame in (el, h, h2)]
    return pd.concat(parts, axis=1).sum(axis=1)


def country_vre_production(pro: pd.DataFrame, scenario_name: str, year: str) -> tuple:
    """Wind (on+offshore summed) and solar production (TWh) per country."""
    production = pro.query("Scenario == @scenario_name and Year == @year")
    wind = production.query("Technology in @WIND_TECHNOLOGIES").groupby("Country")["Value"].sum()
    solar = production.query("Technology in @SOLAR_TECHNOLOGIES").groupby("Country")["Value"].sum()
    return wind, solar


def categorize_scenario(
    el: pd.DataFrame, h: pd.DataFrame, h2: pd.DataFrame, pro: pd.DataFrame, scenario_name: str
) -> pd.DataFrame:
    """One row per country: Demand category and VRE category for this
    scenario name, each decided by comparison to the mean across countries
    within this same scenario name (not a fixed cutoff)."""
    year = scenario_target_year(el, h, h2, scenario_name=scenario_name)
    if year is None:
        return pd.DataFrame()

    demand = country_demand(el, h, h2, scenario_name, year)
    demand = demand[demand > 0]  # a country with no modelled demand has no meaningful ratio
    if demand.empty:
        return pd.DataFrame()

    wind, solar = country_vre_production(pro, scenario_name, year)
    wind = wind.reindex(demand.index, fill_value=0)
    solar = solar.reindex(demand.index, fill_value=0)

    wind_ratio = wind / demand
    solar_ratio = solar / demand

    demand_high = demand > demand.mean()
    wind_high = wind_ratio > wind_ratio.mean()
    solar_high = solar_ratio > solar_ratio.mean()

    vre_category = pd.Series("Low VRE", index=demand.index)
    vre_category[wind_high & ~solar_high] = "High Wind"
    vre_category[solar_high & ~wind_high] = "High Solar"
    vre_category[wind_high & solar_high] = "High Wind+Solar"

    demand_category = demand_high.map({True: "High", False: "Low"})

    result = pd.DataFrame(
        {
            "Scenario": scenario_name,
            "Year": year,
            "Country": demand.index,
            "demand_total": demand.values,
            "wind_ratio": wind_ratio.values,
            "solar_ratio": solar_ratio.values,
            "demand_category": demand_category.values,
            "vre_category": vre_category.values,
        }
    )
    result["combined_category"] = result["demand_category"] + " Demand / " + result["vre_category"]
    return result


def region_to_country_map(pro: pd.DataFrame) -> dict:
    return pro[["Region", "Country"]].drop_duplicates().set_index("Region")["Country"].to_dict()


def plot_category_map(categorized: pd.DataFrame, region_to_country: dict, scenario_name: str, output_path: Path) -> None:
    """One choropleth map of `combined_category` per country for this
    scenario name, drawn at Balmorel's region resolution (every region in a
    country shares its country's category)."""
    geofile_path = resources.files(geofiles) / "2024 BalmorelMap.geojson"
    gdf = gpd.read_file(str(geofile_path)).rename(columns={"id": "Region"})

    gdf["Country"] = gdf["Region"].map(region_to_country)
    category_by_country = categorized.set_index("Country")["combined_category"]
    gdf["combined_category"] = gdf["Country"].map(category_by_country)

    no_data_colour = to_rgba("lightgray")
    face_colours = [CATEGORY_COLOURS.get(c, no_data_colour) for c in gdf["combined_category"]]

    fig, ax = plt.subplots(figsize=(10, 8))
    gdf.plot(ax=ax, color=face_colours, edgecolor="white", linewidth=0.3)
    ax.set_xlim(-11, 35)
    ax.set_ylim(32, 72)
    ax.axis("off")
    ax.set_title(f"{scenario_name} ({categorized['Year'].iloc[0]})")

    present = [c for c in COMBINED_CATEGORIES if c in categorized["combined_category"].unique()]
    handles = [plt.Rectangle((0, 0), 1, 1, color=CATEGORY_COLOURS[c]) for c in present]
    ax.legend(handles, present, loc="lower left", fontsize=7, framealpha=0.9)

    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.command()
@click.option(
    "--balmorel-path",
    type=str,
    default="scripts/Balmorel",
    help="Path to the top level of Balmorel scenario folders",
)
@click.option(
    "--gams-sysdir",
    type=str,
    default=config("GAMS_SYSTEM_DIR", default=None),
    help="Path to GAMS system directory",
)
@click.option(
    "--output-dir",
    type=str,
    default="build_postprocess",
    help="Where to write categorization.csv and maps/",
)
def main(balmorel_path: str, gams_sysdir: str, output_dir: str):
    output_path = Path(output_dir)
    maps_dir = output_path / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)

    table_path = output_path / "categorization.csv"
    columns = [
        "Scenario", "Year", "Country", "demand_total", "wind_ratio",
        "solar_ratio", "demand_category", "vre_category", "combined_category",
    ]

    if not any(Path(balmorel_path).glob("*/model/MainResults_*.gdx")):
        print(f"No MainResults*.gdx files found under {balmorel_path} - nothing to categorize yet.")
        pd.DataFrame(columns=columns).to_csv(table_path, index=False)
        return

    model = Balmorel(balmorel_path, gams_system_directory=gams_sysdir)
    model.collect_results(suffix_naming_only=True)
    res = model.results

    el = res.get_result("EL_DEMAND_YCR")
    h = res.get_result("H_DEMAND_YCRA")
    h2 = res.get_result("H2_DEMAND_YCR")
    pro = res.get_result("PRO_YCRAGF")

    scenario_names = select_scenario_names(model.scenario_names)
    print(f"Categorizing {len(scenario_names)} fullyear/rolling scenario result(s): {scenario_names}")

    frames = [categorize_scenario(el, h, h2, pro, name) for name in scenario_names]
    categorized = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)
    categorized.to_csv(table_path, index=False)

    if categorized.empty:
        return

    region_to_country = region_to_country_map(pro)
    for scenario_name, group in categorized.groupby("Scenario"):
        plot_category_map(group, region_to_country, scenario_name, maps_dir / f"{scenario_name}.png")


if __name__ == "__main__":
    main()
