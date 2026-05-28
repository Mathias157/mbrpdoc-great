import os
import pandas as pd
from pybalmorel import MainResults
from .formats import setup_plot


def load_excel_sheet(filename, sheet_name, headers):
    """
    Load excel file with sheet name

    Returns:
        pd.DataFrame: Demand output data indexed by region/scenario combinations.

    Raises:
        FileNotFoundError: If TYNDP2024 file not found.
        ValueError: If sheet "3_DEMAND_OUTPUT" not found or is empty.
    """
    try:
        df = pd.read_excel(filename, sheet_name=sheet_name, header=headers)
        if df.empty:
            raise ValueError(f"Sheet '{sheet_name}' is empty")
        return df
    except FileNotFoundError:
        raise FileNotFoundError(
            f"File not found at {filename}. "
            "Ensure data has been downloaded via Snakemake rule 'download_data'."
        )
    except ValueError as e:
        if "does not contain sheet" in str(e):
            raise ValueError(
                f"Sheet '{sheet_name}' not found in {filename}. "
                "Check available sheets with: pd.read_excel(..., sheet_name=None)"
            )
        raise


def load_industry_production(scenario, scenario_folder: str = "base"):
    """Excluding electricity production"""
    results = MainResults(
        "MainResults_%s.gdx" % scenario,
        paths=f"analysis/Balmorel/{scenario_folder}/model",
        system_directory=os.getenv("GAMS_SYSTEM_DIR"),
    )
    df = results.get_result("PRO_YCRAGF").query(
        '(Area.str.contains("IND") or Commodity == "HYDROGEN") and Commodity != "ELECTRICITY"'
    )
    return df
