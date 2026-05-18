import pandas as pd


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
