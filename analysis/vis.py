"""Demo visualisation — replace with your real plots."""

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from formats import setup_plot


def visualise_model_results(path_to_results, path_to_figure, dark=False):
    """Plot the results."""
    sns.set_context("paper")
    results = pd.read_pickle(path_to_results)
    facecolor = setup_plot(dark=dark)
    fig = plt.figure(figsize=(8, 4))
    ax = fig.add_subplot(111)
    ax.plot(results)
    ax.set_facecolor(facecolor)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    fig.savefig(path_to_figure, dpi=300)


if __name__ == "__main__":
    visualise_model_results(
        path_to_results=snakemake.input.results[0],
        path_to_figure=snakemake.output[0],
        dark=snakemake.params.dark_plots,
    )
