import os
from pathlib import Path

# Path configuration (using pathlib for Windows/Mac compatibility)

# Get the root directory
BASE_DIR = Path(__file__).parent.absolute()

INPUT_DIR = BASE_DIR / "InstaScope_data" 

TEMP_OUTPUT_DIR = BASE_DIR / "temp_r_output"

AUTOMATION_FILE = BASE_DIR / "automated_results.csv"

# Rscript path
# Windows example:
RSCRIPT_PATH = Path(r"C:\Program Files\R\R-4.5.0\bin\Rscript.exe")
# Mac/Linux example:
# RSCRIPT_PATH = Path("/usr/local/bin/Rscript")


# Runtime parameters
TIME_INT = 'mins' # Time granularity for the R script
FILENAME_PREFIX = 'batch_process' # Output filename prefix for the R script
WAIT_TIME = 60 # Wait time for each loop (seconds) 

# Ensure directories exist
if not INPUT_DIR.exists():
    print(f"Warning: Input directory {INPUT_DIR} does not exist.")
if not TEMP_OUTPUT_DIR.exists():
    TEMP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)