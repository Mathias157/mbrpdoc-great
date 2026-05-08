"""
Global matplotlib configuration for color-deficiency-friendly palettes.

Usage:
    import scripts.plotting as plotting
    plotting.setup_cmcrameri()

    import matplotlib.pyplot as plt
    plt.plot(x, y)  # Now uses cmcrameri palettes
"""

import matplotlib.pyplot as plt
import cmcrameri.cm as cmc


def setup_plot(colourmap: str = "batlowW", dark: bool = False):
    """
    Replace matplotlib's default colormap with cmcrameri (perceptually uniform,
    color-deficiency friendly) and set related style parameters.
    """
    # Set default colormap to 'batlow' (perceptually uniform, works for ~95% color vision)
    plt.rcParams["image.cmap"] = "cmc." + colourmap

    # Optional: set line color cycle for multi-line plots
    # Uses a subset of cmcrameri colors that are distinguishable across color-vision deficiencies
    plt.rcParams["axes.prop_cycle"] = plt.cycler(
        color=[
            getattr(cmc, colourmap)(0),  # Dark
            getattr(cmc, colourmap)(0.1),  # Dark
            getattr(cmc, colourmap)(0.2),  # Dark
            getattr(cmc, colourmap)(0.3),  # Dark
            getattr(cmc, colourmap)(0.4),  # Mid-dark
            getattr(cmc, colourmap)(0.5),  # Mid-dark
            getattr(cmc, colourmap)(0.6),  # Mid-light
            getattr(cmc, colourmap)(0.7),  # Mid-light
            getattr(cmc, colourmap)(0.8),  # Light
            getattr(cmc, colourmap)(0.9),  # Light
            getattr(cmc, colourmap)(1),  # Light
        ]
    )

    # Improve figure defaults
    plt.rcParams["figure.figsize"] = (7, 4)
    plt.rcParams["figure.dpi"] = 100
    plt.rcParams["savefig.dpi"] = 300
    plt.rcParams["font.size"] = 11

    if dark:
        plt.style.use("dark_background")
        facecolor = "none"  # Facecolor
    else:
        facecolor = "white"

    return facecolor


def get_cmap(name="batlow"):
    """
    Get a cmcrameri colormap by name.

    Common cmcrameri options:
    - 'cmc.batlow': perceptually uniform (default)
    - 'cmc.batlowW': white background friendly
    - 'devon': blue-based
    - 'lapaz': purple-blue
    - 'lajolla': warm
    - 'turku': blue-orange
    - 'acton': grey-friendly
    - 'grayC': uniform grey scale

    Args:
        name: cmcrameri colormap name

    Returns:
        matplotlib colormap object
    """
    try:
        return getattr(cmc, name)
    except AttributeError:
        raise ValueError(
            f"Unknown cmcrameri colormap: {name}. "
            "See https://www.fabiocrameri.ch/querying-cmcrameri/"
        )


if __name__ == "__main__":
    # Demo: show available cmcrameri colormaps
    import numpy as np

    setup_cmcrameri()

    x = np.linspace(0, 2 * np.pi, 100)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))

    for ax, cmap_name in zip(axes.flat, ["batlow", "devon", "lapaz", "lajolla"]):
        cmap = get_cmap(cmap_name)
        for i in range(4):
            ax.plot(x, np.sin(x + i * np.pi / 4), color=cmap(i / 4), linewidth=2)
        ax.set_title(f"cmcrameri: {cmap_name}")
        ax.set_xlabel("x")
        ax.set_ylabel("y")

    plt.tight_layout()
    plt.savefig("/tmp/cmcrameri_demo.png")
    print("Demo plot saved to /tmp/cmcrameri_demo.png")
