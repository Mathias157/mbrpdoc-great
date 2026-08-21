"""Weather-year input preparation flow.

Deliberately separate from `Snakefile` and never included by it (see
docs/adr/0014) — 39 years of pybalmorel WEATHERYEAR calls is expensive,
manually-triggered data prep, not something every `pixi run snakemake`
should redo. Still gets Snakemake's own incremental/skip-if-done behaviour
per year, just not on the default path. Requires
data/weatheryear_inputs/ (manually downloaded, e.g. from DTU Data — see
CONTEXT.md's "Weather year"). Run manually:

    pixi run snakemake --snakefile rules/weatheryear.smk --cores 4
"""
YEARS = list(range(1982, 2021))  # 1982-2020, see CONTEXT.md's "Weather year"

# Must match clean_weather_year_inputs.py's own _VARIANTS list.
VARIANTS = ["data_raw", "data_scaled"]

rule all:
    input:
        expand("scripts/Balmorel/weatheryeardata/{variant}/{year}", variant=VARIANTS, year=YEARS),

rule generate_weather_year_inputs:
    message: "Generate raw weather year {wildcards.year} inputs via pybalmorel WEATHERYEAR."
    input:
        inputs="data/weatheryear_inputs",
        config="config/weatheryear.yml",
        script="scripts/preprocessing/generate_weather_year_inputs.py",
    output:
        directory("data/weatheryear_raw/{year}/to_balmorel"),
    shell:
        "python {input.script} --year {wildcards.year} --config {input.config} --output-dir data/weatheryear_raw"

rule clean_weather_year_inputs:
    message: "Trim weather year {wildcards.year} down to Balmorel-ready .inc files."
    input:
        raw="data/weatheryear_raw/{year}/to_balmorel",
        script="scripts/preprocessing/clean_weather_year_inputs.py",
    output:
        [directory(f"scripts/Balmorel/weatheryeardata/{variant}/{{year}}") for variant in VARIANTS],
    shell:
        "python {input.script} --year {wildcards.year} --raw-dir data/weatheryear_raw --output-dir scripts/Balmorel/weatheryeardata"
