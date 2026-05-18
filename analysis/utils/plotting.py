"""Formatting of plots"""

# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import cmcrameri.cm as cmc
import matplotlib.pyplot as plt
import yaml

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def setup_plot(
    colourmap: str = "",
    dark: bool = False,
    colour_range: tuple = tuple(range(0, 255, 52)),
):
    """
    Replace matplotlib's default colormap with cmcrameri (perceptually uniform,
    color-deficiency friendly) and set related style parameters.

    Returns: facecolor (str): Value for ax.set_facecolor function
    """

    if colourmap == "":
        with open("config/default.yaml", "r") as f:
            config = yaml.safe_load(f)
        if dark:
            colourmap = config["dark_colourmap"]
        else:
            colourmap = config["white_colourmap"]
        print(f"setting colourmap to {colourmap}")

    if dark:
        plt.style.use("dark_background")
        facecolor = "none"  # Facecolor
    else:
        facecolor = "white"

    # Set default colormap to 'batlow' (perceptually uniform, works for ~95% color vision)
    plt.rcParams["image.cmap"] = "cmc." + colourmap

    # Optional: set line color cycle for multi-line plots
    # Uses a subset of cmcrameri colors that are distinguishable across color-vision deficiencies
    plt.rcParams["axes.prop_cycle"] = plt.cycler(  # type: ignore
        color=[getattr(cmc, colourmap)(i) for i in colour_range]
    )

    # Improve figure defaults
    plt.rcParams["figure.figsize"] = (7, 4)
    plt.rcParams["figure.dpi"] = 100
    plt.rcParams["savefig.dpi"] = 300
    plt.rcParams["font.size"] = 11

    return facecolor
