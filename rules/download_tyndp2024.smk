# Snakemake rule template: Download and extract TYNDP 2024 scenario data
#
# This rule demonstrates the pattern for data acquisition:
# - Download from remote URL
# - Extract/preprocess into data/ directory
# - Log metadata (source, access date, format)
#
# Usage: Add to rules/ directory, then include in Snakefile:
#   include: "rules/download_tyndp2024.smk"

from datetime import datetime

# Configuration: TYNDP 2024 data URLs
TYNDP_URLS = {
    "demand_scenarios": "https://2024-data.entsos-tyndp-scenarios.eu/files/scenarios-inputs/Demand_Scenarios_TYNDP_2024_After_Public_Consultation.xlsb.zip",
    "reference_grid": "https://2024-data.entsos-tyndp-scenarios.eu/files/scenarios-inputs/20231103-Electricity-and-Hydrogen-Reference-Grid-Investment-Candidates.xlsx.zip",
    "line_data": "https://2024-data.entsos-tyndp-scenarios.eu/files/scenarios-inputs/Line-data.zip",
}

TYNDP_TARGET_DIR = "data/tyndp-2024"
TYNDP_DOWNLOAD_TIMESTAMP = datetime.now().isoformat()

# Rule: Download all TYNDP2024 files
rule download_tyndp2024:
    """
    Download TYNDP 2024 scenario data for demand, reference grid, and transmission.

    Outputs:
        - data/tyndp-2024/Demand_Scenarios_*.xlsb
        - data/tyndp-2024/Reference_Grid_*.xlsx
        - data/tyndp-2024/line_data/
        - data/tyndp-2024/README.md (metadata)

    Notes:
        - May require registration or authentication on ENTSOS portal
        - Files are provided as .zip archives; extracted automatically
        - Metadata is logged for reproducibility
    """
    output:
        demand=expand("{dir}/Demand_Scenarios_TYNDP_2024_After_Public_Consultation.xlsb", dir=TYNDP_TARGET_DIR),
        reference_grid=expand("{dir}/20231103 - Electricity and Hydrogen Reference Grid & Investment Candidates.xlsx", dir=TYNDP_TARGET_DIR),
        # line_data=expand("{dir}/line_data/", dir=TYNDP_TARGET_DIR),
        # metadata=expand("{dir}/README.md", dir=TYNDP_TARGET_DIR),
    params:
        timestamp=TYNDP_DOWNLOAD_TIMESTAMP,
        demand_url=TYNDP_URLS["demand_scenarios"],
        ref_grid_url=TYNDP_URLS["reference_grid"],
        line_data_url=TYNDP_URLS["line_data"],
    shell:
        """
        # Ensure target directory exists
        mkdir -p {TYNDP_TARGET_DIR}

        # Download demand scenarios
        echo "Downloading demand scenarios..."
        curl -L -o {TYNDP_TARGET_DIR}/Demand_Scenarios.zip "{params.demand_url}"
        unzip -o {TYNDP_TARGET_DIR}/Demand_Scenarios.zip -d {TYNDP_TARGET_DIR}/
        rm {TYNDP_TARGET_DIR}/Demand_Scenarios.zip

        # Download reference grid and investment candidates
        echo "Downloading reference grid..."
        curl -L -o {TYNDP_TARGET_DIR}/Reference_Grid.zip "{params.ref_grid_url}"
        unzip -o {TYNDP_TARGET_DIR}/Reference_Grid.zip -d {TYNDP_TARGET_DIR}/
        rm {TYNDP_TARGET_DIR}/Reference_Grid.zip

        # Download line data
        echo "Downloading line data..."
        mkdir -p {TYNDP_TARGET_DIR}/line_data
        curl -L -o {TYNDP_TARGET_DIR}/line_data.zip "{params.line_data_url}"
        unzip -o {TYNDP_TARGET_DIR}/line_data.zip -d {TYNDP_TARGET_DIR}/line_data/
        rm {TYNDP_TARGET_DIR}/line_data.zip

        # Remove __MACOSX
        rm -rf {TYNDP_TARGET_DIR}/__MACOSX
        """

# Rule: Validate downloaded TYNDP2024 files
rule validate_tyndp2024:
    """
    Sanity checks on downloaded TYNDP2024 files:
    - Files exist and are readable
    - File sizes are non-zero
    """
    input:
        rules.download_tyndp2024.output,
    output:
        validation_log=expand("{dir}/.validation_passed", dir=TYNDP_TARGET_DIR),
    shell:
        """
        set -e
        dir={TYNDP_TARGET_DIR}

        echo "Validating TYNDP2024 downloads..."

        # Check file existence and size
        for file in "$dir"/Demand_Scenarios*.xlsb "$dir"/*\ -\ Electricity\ and\ Hydrogen\ Reference\ Grid\ \&\ Investment\ Candidates.xlsx; do
            if [ ! -f "$file" ]; then
                echo "ERROR: Expected file not found: $file"
                exit 1
            fi
            size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "unknown")
            if [ "$size" = "0" ]; then
                echo "ERROR: File is empty: $file"
                exit 1
            fi
            echo "✓ $file ($size bytes)"
        done

        # Check line_data directory
        if [ ! -d "$dir/line_data" ] || [ -z "$(ls -A $dir/line_data)" ]; then
            echo "ERROR: Line data directory is empty or missing"
            exit 1
        fi
        echo "✓ Line data directory present"

        echo "All TYNDP2024 files validated successfully."
        touch {output.validation_log}
        """
