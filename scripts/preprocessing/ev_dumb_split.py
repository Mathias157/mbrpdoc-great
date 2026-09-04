"""
EV Dumb-Charging Fleet-Split Preprocessing

Works around a bug in the EV addon (scripts/Balmorel/base/addons/EV/bb4/):
raising EV_BEV_dumb's dumb-charging fraction forces a hard lower bound on
VEV_G2V_BEV that is independent of actual charging need, so it inflates
total EV demand instead of reallocating a fixed total between smart/dumb
shares - and drives infeasibility without V2G once the floor exceeds
available SOC headroom.

Instead of touching EV_BEV_dumb, this script shrinks the fleet the addon
sees (EV_BEV_available) to the "smart charging" share only, and adds the
excluded "dumb charging" share as an ordinary exogenous DE demand user
(DEUSER 'EV_DUMB'), sized from the same return/leave trip-energy signal
the addon itself would have used for that share. Validated against a real
GAMS run: a 50/50 split reproduces the addon's own un-split ENDO_EV to
within 0.6% when summed back together.

Raw EV input data (EV_BEV_available, return/leave profiles, tech data) is
read through pybalmorel's Balmorel.load_incfiles()/get_input(), not parsed
from the .inc files directly - this reproduces the framework's own
%low_ev%/%EV_profile% branching exactly (see EV_pardefine.inc), rather than
re-guessing it by hand. load_incfiles() runs GAMS once per scenario and
caches the result to <scenario>/model/<scenario>_input_data.gdx; reruns
against unchanged input data reload that cache instead of re-running GAMS.

Created on 04.09.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import sys
from pathlib import Path

# Add repo root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import click
import pandas as pd
from decouple import config
from pybalmorel import Balmorel, IncFile

REPO = Path(__file__).resolve().parents[2]
BALMOREL_PATH = REPO / "scripts/Balmorel"

# The addon unconditionally doubles IEV_BEV_return/IEV_BEV_leave for any
# active BEV region (EV_ipardecdef.inc:295-297, reached via
# $label YES_EV_INTERSEASONAL) - both are EV_BEV_available x profile
# products, so this doubling has to be reproduced here too, or the
# exogenous "dumb" share represents half the population it should.
# Confirmed empirically: halving EV_BEV_available exactly halves a real
# run's ENDO_EV (196.015 -> 98.0075 TWh). Not exposed by load_incfiles():
# EV_ipardecdef.inc is only $INCLUDE'd from the full model build
# (base/model/Balmorelbb4.inc via addons/_hooks/ipardecdef.inc), which
# load_incfiles()'s ReadData-only GAMS job never reaches.
EV_ADDON_RETURN_LEAVE_DOUBLING = 2


# ------------------------------- #
#          1. Data loading        #
# ------------------------------- #


def load_ev_inputs(
    scenario: str, gams_system_directory: str
) -> tuple[Balmorel, list[str], set[str], set[str]]:
    """Load <scenario>'s resolved input data (GAMS's own reading of the
    .inc files - including whichever %low_ev%/%EV_profile% branch that
    scenario's own settings select) and its active regions/full S,T domain.
    """
    balm = Balmorel(str(BALMOREL_PATH), gams_system_directory=gams_system_directory)
    balm.load_incfiles(scenario=scenario)

    countries = set(balm.get_input("C")["CCC"])
    ccrrr = balm.get_input("CCCRRR")
    regions = sorted(ccrrr.loc[ccrrr["CCC"].isin(countries), "RRR"].unique())

    # Full SSS/TTT domain (S01-S52 x T001-T168), not just whichever S(SSS)/T(TTT)
    # subset happens to be active - the same scenario gets re-run at different
    # time resolutions, and DE_VAR_T/DE_EV_DUMB need a value for every (S,T)
    # combination any of those resolutions might activate.
    seasons = set(balm.get_input("SSS").iloc[:, -1])
    timesteps = set(balm.get_input("TTT").iloc[:, -1])

    return balm, regions, seasons, timesteps


def year_indexed(
    balm: Balmorel, symbol: str, regions: list[str] | None = None
) -> pd.DataFrame:
    """get_input(symbol) with YYY cast to int and (optionally) restricted to
    `regions`."""
    df = balm.get_input(symbol).astype({"YYY": int})
    if regions is not None:
        df = df[df["RRR"].isin(regions)]
    return df


# ------------------------------- #
#          2. Main                #
# ------------------------------- #


@click.command()
@click.option(
    "--scenario", default="test", help="Scenario folder under scripts/Balmorel/"
)
@click.option(
    "--dumb-share",
    default=0.5,
    type=float,
    help="Share of the EV fleet represented as inflexible exogenous demand (0-1)",
)
@click.option(
    "--shape-year",
    default=2050,
    type=int,
    help="Year whose return/leave profile shape is used for DE_VAR_T (year-invariant in Balmorel's own structure - only the annual total in DE_EV_DUMB.inc varies by year)",
)
@click.option(
    "--gams-sysdir",
    default=config("GAMS_SYSTEM_DIR"),
    help="Path to GAMS system directory",
)
def main(scenario: str, dumb_share: float, shape_year: int, gams_sysdir: str):
    scen_dir = BALMOREL_PATH / scenario / "data"

    balm, regions, seasons, timesteps = load_ev_inputs(scenario, gams_sysdir)
    # WEIGHT_S/WEIGHT_T are uniform (168h/season-step, 1h/timestep in base/data),
    # so at full S01-S52 x T001-T168 resolution IHOURSINST reduces to one
    # constant (~1h/cell); a non-uniform active S/T subset would need the real
    # IHOURSINST(S,T) weighting instead.
    ihoursinst = 8760 / (len(seasons) * len(timesteps))

    # EV_BEV_available is read from 'base', never from `scenario` - this script
    # writes EV_BEV_available.inc back into <scenario>/data/ as its own output,
    # so reading it from `scenario` would feed a prior run's already-split
    # smart-only fleet back in as if it were the raw fleet, compounding the
    # dumb_share reduction on every rerun. base/data/EV_BEV_available.inc is
    # never written by this script, so it's a safe, uncontaminated source -
    # confirmed no scenario in this repo overrides %low_ev% (which is where
    # EV_BEV_available.inc's own scaling branches on), so base's reading of it
    # matches every scenario's own.
    base_balm = Balmorel(str(BALMOREL_PATH), gams_system_directory=gams_sysdir)
    base_balm.load_incfiles(scenario="base")
    available = year_indexed(base_balm, "EV_BEV_available", regions)
    return_profile = year_indexed(balm, "EV_BEV_return_profile", regions)
    leave_profile = year_indexed(balm, "EV_BEV_leave_profile", regions)
    return_energy = year_indexed(balm, "EV_BEV_return_energy").set_index("YYY")["Value"]
    leave_energy = year_indexed(balm, "EV_BEV_leave_energy").set_index("YYY")["Value"]
    g2v_eff = year_indexed(balm, "EV_BEV_G2V_EFF").set_index("YYY")["Value"]

    years = sorted(
        set(available["YYY"])
        & set(return_profile["YYY"])
        & set(leave_profile["YYY"])
        & set(return_energy.index)
        & set(leave_energy.index)
        & set(g2v_eff.index)
    )
    if not years:
        raise ValueError(
            "No year has EV_BEV_available, both profiles, and tech data all defined"
        )
    click.echo(f"Years with full data (available + profiles + tech data): {years}")
    skipped = sorted(set(available["YYY"]) - set(years))
    if skipped:
        click.echo(
            f"Skipping years with EV_BEV_available but no profile data: {skipped}"
        )

    # ------------------------------------------------------------ #
    #  Smart/dumb fleet split
    # ------------------------------------------------------------ #

    available = available[available["YYY"].isin(years)]
    smart_fleet = available.assign(Value=lambda d: d["Value"] * (1 - dumb_share))

    # Raw hourly net trip-energy signal for the dumb share: return/leave
    # profiles (fraction of fleet connecting/disconnecting) x their trip
    # energy, doubled to match the addon's own IEV_BEV_return/leave
    # convention, scaled to only the dumb share, sign-flipped so
    # "grid draw" is positive (both profiles carry their own signs from
    # the input tables - leave_profile is negative by convention).
    # get_input() only returns nonzero (Y,S,T,R) cells, and return/leave
    # profiles are sparse over different (S,T) cells - so this must be an
    # explicit outer merge on keys (missing = 0), not positional alignment.
    key_cols = ["YYY", "SSS", "TTT", "RRR"]
    raw = (
        return_profile[return_profile["YYY"].isin(years)][key_cols + ["Value"]]
        .rename(columns={"Value": "Return"})
        .merge(
            leave_profile[leave_profile["YYY"].isin(years)][
                key_cols + ["Value"]
            ].rename(columns={"Value": "Leave"}),
            on=key_cols,
            how="outer",
        )
        .fillna({"Return": 0.0, "Leave": 0.0})
        .merge(available.rename(columns={"Value": "Available"}), on=["YYY", "RRR"])
    )
    raw["ReturnEnergy"] = raw["YYY"].map(return_energy)
    raw["LeaveEnergy"] = raw["YYY"].map(leave_energy)
    raw["G2V_EFF"] = raw["YYY"].map(g2v_eff)
    raw["Value"] = (
        -dumb_share
        * EV_ADDON_RETURN_LEAVE_DOUBLING
        * raw["Available"]
        * (raw["Return"] * raw["ReturnEnergy"] + raw["Leave"] * raw["LeaveEnergy"])
        / raw["G2V_EFF"]
    )
    raw = raw[key_cols + ["Value"]]

    annual_total = (
        raw
        .assign(Value=lambda d: d["Value"] * ihoursinst)
        .groupby(["YYY", "RRR"])["Value"]
        .sum()
        .unstack("YYY")  # index=region, columns=year
        .fillna(0.0)
    )

    if shape_year not in years:
        raise ValueError(
            f"--shape-year {shape_year} is not among the usable years {years}"
        )
    shape = raw[raw["YYY"] == shape_year].copy()
    shape["Value"] = shape["Value"].clip(lower=0.0)
    # A region can be entirely absent from a given (S,T)'s sparse rows when
    # both return and leave are exactly zero there for that region - the
    # pivot below then leaves that (ST,RRR) cell as NaN (missing), not 0.0,
    # even though "no return/leave activity that hour" genuinely means 0.
    shape_table = (
        shape
        .assign(ST=lambda d: d["SSS"] + " . " + d["TTT"])
        .pivot(index="ST", columns="RRR", values="Value")
        .fillna(0.0)
    )

    click.echo(
        f"Smart-fleet share: {1 - dumb_share:.0%}, dumb (exogenous) share: {dumb_share:.0%}"
    )
    for year in years:
        total_twh = annual_total[year].sum() / 1e6
        click.echo(
            f"  {year}: exogenous EV_DUMB demand = {total_twh:.2f} TWh across {len(regions)} regions"
        )

    # ------------------------------------------------------------ #
    #  Write override .inc files into <scenario>/data/
    #  (DE.inc / DEUSER.inc are wired up in base/data by hand, not here)
    # ------------------------------------------------------------ #

    smart_table = smart_fleet.pivot(index="YYY", columns="RRR", values="Value").fillna(
        0.0
    )  # index=year, columns=region

    def format_table(df: pd.DataFrame, float_fmt: str = "{:.4f}") -> str:
        """DataFrame -> GAMS TABLE body: fixed-point (not pandas' default
        scientific notation, which GAMS TABLE parsing shouldn't be trusted
        with) and no blank line between header and first data row (pandas
        emits one for an empty columns.name)."""
        df = df.copy()
        df.index.name = ""
        df.columns.name = ""
        text = df.to_string(float_format=lambda x: float_fmt.format(x))
        return "\n".join(line for line in text.splitlines() if line.strip())

    # 1. EV_BEV_available.inc - smart-charging-only fleet fed to the addon
    IncFile(
        prefix=(
            f"* Fleet-split EV dumb-charging ({scenario}): addon only sees the SMART-charging\n"
            f"* share of the fleet ({1 - dumb_share:.0%}) - the {dumb_share:.0%} dumb share is\n"
            "* represented exogenously instead (see DE_EV_DUMB.inc). Values already reflect\n"
            "* whatever %low_ev% branch this scenario's own settings selected.\n"
            "TABLE EV_BEV_available\n"
        ),
        body=format_table(smart_table),
        suffix="\n;\n",
        name="EV_BEV_available",
        path=str(scen_dir),
    ).save()

    # 2. EV_BEV_dumb.inc - zero: addon's own (reduced) fleet has no forced floor left
    IncFile(
        prefix=(
            f"* Fleet-split EV dumb-charging ({scenario}): dumb charging is handled exogenously\n"
            "* (DE_EV_DUMB.inc), so the addon's own smart-only fleet has EV_BEV_dumb=0 - no\n"
            "* forced VEV_G2V_BEV.LO floor, no infeasibility risk without V2G.\n"
        ),
        body="EV_BEV_dumb(YYY,RRR)=0;\n",
        name="EV_BEV_dumb",
        path=str(scen_dir),
    ).save()

    # 3. DE_EV_DUMB.inc - true annual totals per year (unclipped need, so
    #    DE/DE_VAR_T's own self-normalization via IDE_SUMST preserves the
    #    full annual energy regardless of DE_VAR_T's shape-clipping below -
    #    this is also why one fixed shape-year is fine for every other year:
    #    the shape only redistributes each year's own DE total across hours,
    #    it never changes that total)
    IncFile(
        prefix=f"TABLE   DE_EV_DUMB(RRR,YYY)   'Fleet-split ({scenario}): exogenous dumb-charging-share EV consumption (MWh)'\n",
        body=format_table(annual_total),
        suffix=(
            "\n;\nDE(YYY,RRR,'EV_DUMB')=DE_EV_DUMB(RRR,YYY);\nDE_EV_DUMB(RRR,YYY)=0;\n"
        ),
        name="DE_EV_DUMB",
        path=str(scen_dir),
    ).save()

    # 4. EV_DUMB_DE_VAR_T.inc - standalone shape from shape_year only (DE_VAR_T
    #    has no year dimension in Balmorel's structure; per-year magnitude is
    #    carried entirely by DE_EV_DUMB.inc above, see its comment). Not
    #    appended into DE_VAR_T.inc - wire this in with your own $ifi in
    #    base/data/DE_VAR_T.inc instead.
    IncFile(
        prefix=f'PARAMETER DE_VAR_T_EVDUMB(SSS,TTT,RRR) "Fleet-split ({scenario}, shape year {shape_year}): dumb EV demand shape";\nTABLE DE_VAR_T_EVDUMB(SSS,TTT,RRR)\n',
        body=format_table(shape_table, float_fmt="{:.6f}"),
        suffix="\n;\nDE_VAR_T(RRR,'EV_DUMB',SSS,TTT) = DE_VAR_T_EVDUMB(SSS,TTT,RRR);\n",
        name="EV_DUMB_DE_VAR_T",
        path=str(scen_dir),
    ).save()

    click.echo("\nFiles written to " + str(scen_dir) + ":")
    for fn in [
        "EV_BEV_available.inc",
        "EV_BEV_dumb.inc",
        "DE_EV_DUMB.inc",
        "EV_DUMB_DE_VAR_T.inc",
    ]:
        click.echo(f"  - {fn}")
    click.echo(
        "\nNot written (wire these into base/data yourself, gated by your own scenario switch,\n"
        "e.g. %dumbevshare%==yes):\n"
        "  - DE.inc: DE_EV_DUMB.inc's $INCLUDE\n"
        "  - DEUSER.inc: the 'EV_DUMB' set element\n"
        "  - DE_VAR_T.inc: EV_DUMB_DE_VAR_T.inc's $INCLUDE"
    )


if __name__ == "__main__":
    main()
