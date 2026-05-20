"""Snakemake DAG for the research template.

Pipeline: data -> analysis -> visualisation -> report (HTML/PDF) + tests.

Edit `rules/` files for additional analysis steps. The demo rules below
(`run`, `plot`, `report`, `test`) prove the pipeline works end-to-end on a
fresh clone — replace them once you have real analyses.
"""
from pathlib import Path
from glob import glob

from snakemake.utils import min_version
include: "rules/download_data.smk"

configfile: "config/default.yaml"

min_version("8.0")


rule all:
    message: "Run entire analysis and compile LaTeX report."
    input:
        "build/main.pdf",
        "build/test.success",

rule preprocessing:
    message: "Pre-processing raw data to Balmorel input"
    input:
        tyndp=rules.validate_tyndp2024.output,
        af25=rules.download_af25.output,
        script=[
            "analysis/preprocessing/datacentres.py",
            "analysis/preprocessing/grids.py"
        ]
    output:
        "analysis/Balmorel/base/data/DE_DATACENTER.inc",
        "analysis/Balmorel/base/data/XMAXINV.inc",
        "analysis/Balmorel/base/data/HYDROGEN_XH2MAXINV.inc"
    shell:
        """
        python analysis/preprocessing/datacentres.py datacenterload
        python analysis/preprocessing/grids.py electricity-transmission
        python analysis/preprocessing/grids.py hydrogen-transmission
        """

rule run:
    message: "Runs the demo model."
    input:
        "analysis/Balmorel/base/data/DE_DATACENTER.inc"
    params:
        slope=config["slope"],
        x0=config["x0"],
    output: "build/results.pickle"
    script: "analysis/model.py"


rule plot:
    message: "Visualises the demo results."
    input:
        results=rules.run.output,
    params:
        dark_plots=config["dark_plots"],
        dark_colourmap=config["dark_colourmap"],
        white_colourmap=config["white_colourmap"]
    output: "build/plot.pdf"
    script: "analysis/vis.py"


rule copy_figures:
    message: "Copy figures to report directory."
    input: "build/test.success"
    params:
        plot_path="analysis/plots",
        build_path="build",
        output_path="report/figures",
    output:
        glob("report/figures/*.pdf")
    shell:
        """
        cp {params.build_path}/plot.pdf {params.output_path}/
        cp {params.plot_path}/datacenter_electricity_consumption.pdf {params.output_path}/
        """


rule latex_report:
    message: "Compile LaTeX report via latexmk."
    input:
        main="report/main.tex",
        preamble="report/preamble.tex",
        bib="report/bibliography.bib",
        figures=rules.copy_figures.output,
    output: "build/main.pdf"
    shell:
        """
        cd report
        latexmk -pdf main.tex
        """


rule dag_dot:
    input:
        "Snakefile",
        glob("rules/*.smk")
    output: temp("build/dag.dot")
    shell: "snakemake --rulegraph > {output}"


rule dag:
    message: "Plot dependency graph of the workflow."
    input: rules.dag_dot.output[0]
    # Output is deliberately omitted so rule is executed each time.
    shell: "dot -Tpdf {input} -o build/dag.pdf"


rule clean:
    message: "Remove all build results but keep downloaded data."
    run:
        import shutil

        shutil.rmtree("build", ignore_errors=True)
        print("Data downloaded to data/ has not been cleaned.")


rule archive:
    message: "Package, zip, and move entire build."
    params:
        push_from_directory=config["push"]["from"],
        push_to_directory=config["push"]["to"],
        exclude_paths=config["push"]["exclude-paths"],
    run:
        import tarfile
        from datetime import datetime
        from pathlib import Path

        today = datetime.today().strftime("%Y-%m-%d")
        from_folder = Path(params.push_from_directory)
        to_folder = Path(params.push_to_directory).expanduser()
        build_archive_filename = to_folder / f"research-template-{today}.gz"

        to_folder.mkdir(parents=True, exist_ok=True)
        assert to_folder.is_dir(), f"Archive folder {to_folder} does not exist."

        exclude_paths = params.exclude_paths if params.exclude_paths else []

        with tarfile.open(build_archive_filename, "w:gz") as tar:
            tar.add(from_folder, filter=lambda x: None if x.name in exclude_paths else x)


rule test:
    # To add more tests:
    # (1) Add to-be-tested workflow outputs as inputs to this rule.
    # (2) Turn them into pytest fixtures in tests/test_runner.py.
    # (3) Create or reuse a test file in tests/my-test.py and use fixtures in tests.
    message: "Run tests"
    input:
        test_dir="tests",
        tests=map(str, Path("tests").glob("**/test_*.py")),
        model_results=rules.run.output[0],
    log: "build/test-report.html"
    output: "build/test.success"
    script: "./tests/test_runner.py"
