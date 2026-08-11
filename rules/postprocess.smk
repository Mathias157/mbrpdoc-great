"""Postprocessing Snakemake flow.

Deliberately separate from `Snakefile` and never referenced by
`.github/workflows/reproduction.yaml` (see docs/adr/0003) — CI has no HPC
access, so no `MainResults*.gdx` files ever exist there. Run manually, once
results are synced down (`pixi run sync-mainresults <scenario>`):

    pixi run postprocess
"""
from glob import glob

rule all:
    input:
        "build_postprocess/categorization.csv",
        "build_postprocess/category_costs.csv",

rule categorize_countries:
    message: "Categorize Balmorel scenario results by Demand/VRE type."
    input:
        results=glob("scripts/Balmorel/*/model/MainResults_*.gdx"),
        script="scripts/postprocessing/categorize_countries.py",
    output:
        table="build_postprocess/categorization.csv",
        maps=directory("build_postprocess/maps"),
    shell:
        "python {input.script} --output-dir build_postprocess"

rule aggregate_category_costs:
    message: "Aggregate system cost by VRE/Demand category, across scenarios."
    input:
        results=glob("scripts/Balmorel/*/model/MainResults_*.gdx"),
        categorization="build_postprocess/categorization.csv",
        script="scripts/postprocessing/aggregate_category_costs.py",
    output:
        table="build_postprocess/category_costs.csv",
    shell:
        "python {input.script} --output-dir build_postprocess"
