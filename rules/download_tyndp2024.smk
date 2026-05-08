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
        demand=expand("{dir}/Demand_Scenarios_TYNDP_2024.xlsb", dir=TYNDP_TARGET_DIR),
        reference_grid=expand("{dir}/Reference-Grid-Investment-Candidates.xlsx", dir=TYNDP_TARGET_DIR),
        line_data=expand("{dir}/line_data/", dir=TYNDP_TARGET_DIR),
        metadata=expand("{dir}/README.md", dir=TYNDP_TARGET_DIR),
    shell:
        """
        # Ensure target directory exists
        mkdir -p {TYNDP_TARGET_DIR}
        
        # Download demand scenarios
        echo "Downloading demand scenarios..."
        curl -L -o {TYNDP_TARGET_DIR}/Demand_Scenarios.zip "{TYNDP_URLS[demand_scenarios]}"
        unzip -o {TYNDP_TARGET_DIR}/Demand_Scenarios.zip -d {TYNDP_TARGET_DIR}/
        rm {TYNDP_TARGET_DIR}/Demand_Scenarios.zip
        
        # Download reference grid and investment candidates
        echo "Downloading reference grid..."
        curl -L -o {TYNDP_TARGET_DIR}/Reference_Grid.zip "{TYNDP_URLS[reference_grid]}"
        unzip -o {TYNDP_TARGET_DIR}/Reference_Grid.zip -d {TYNDP_TARGET_DIR}/
        rm {TYNDP_TARGET_DIR}/Reference_Grid.zip
        
        # Download line data
        echo "Downloading line data..."
        mkdir -p {TYNDP_TARGET_DIR}/line_data
        curl -L -o {TYNDP_TARGET_DIR}/line_data.zip "{TYNDP_URLS[line_data]}"
        unzip -o {TYNDP_TARGET_DIR}/line_data.zip -d {TYNDP_TARGET_DIR}/line_data/
        rm {TYNDP_TARGET_DIR}/line_data.zip
        
        # Create metadata file
        cat > {TYNDP_TARGET_DIR}/README.md << 'EOF'
# TYNDP 2024 Scenario Data

## Source
- **Provider**: ENTSOS (European Network of Transmission System Operators)
- **Scenario Document**: TYNDP 2024
- **Portal**: https://2024-data.entsos-tyndp-scenarios.eu/

## Files

### Demand Scenarios
- **File**: Demand_Scenarios_TYNDP_2024.xlsb
- **URL**: {TYNDP_URLS[demand_scenarios]}
- **Description**: Projected electricity and hydrogen demand by region, carrier type
- **Units**: MWh/h (electricity), kg/h or similar (hydrogen)
- **Coverage**: EU-27 + UK + Norway + Switzerland (typically)
- **Resolution**: Hourly or aggregated profiles

### Reference Grid & Investment Candidates
- **File**: Reference-Grid-Investment-Candidates.xlsx
- **URL**: {TYNDP_URLS[reference_grid]}
- **Description**: Reference transmission grid (baseline) + planned investment candidates
- **Contents**: AC/DC line data, capacity (MW), voltage levels, cross-border corridors
- **Usage**: For isolationism scenarios, use reference grid only; for baseline, include investment candidates

### Line Data
- **File**: line_data/
- **URL**: {TYNDP_URLS[line_data]}
- **Description**: Detailed line-level transmission network data
- **Coverage**: AC/DC transmission topology for scenario modeling

## Metadata
- **Downloaded**: {datetime.now().isoformat()}
- **License**: [Check ENTSOS terms; typically CC BY 4.0]
- **Preprocessing**: Files extracted from .zip archives as-is
- **Notes**: Verify data coverage and units against model requirements before integration

## Usage in GREAT Model

**Baseline Scenarios**:
- Use Demand_Scenarios_TYNDP_2024 (demand profiles)
- Include Reference Grid + Investment Candidates (transmission)

**Isolationism Scenarios**:
- Use Demand_Scenarios_TYNDP_2024 (demand profiles unchanged)
- Use Reference Grid only (no new transmission investment)

See `wiki/queries/great-scenario-data-sources.md` for full scenario dimension specifications.
EOF
        """

# Rule: Validate downloaded TYNDP2024 files
rule validate_tyndp2024:
    """
    Sanity checks on downloaded TYNDP2024 files:
    - Files exist and are readable
    - File sizes are non-zero
    - Metadata is present
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
        for file in "$dir"/Demand_Scenarios*.xlsb "$dir"/Reference*.xlsx; do
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
        
        # Check metadata
        if [ ! -f "$dir/README.md" ]; then
            echo "ERROR: Metadata file missing"
            exit 1
        fi
        echo "✓ Metadata file present"
        
        echo "All TYNDP2024 files validated successfully."
        touch {output.validation_log}
        """
