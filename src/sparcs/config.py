"""Settings that can change between runs: which data to pull and where outputs go."""

from pathlib import Path

# Which data to pull
DATASET_ID = "46xm-urtu"  # Hospital Inpatient Discharges (SPARCS De-Identified): 2023
APR_DRG = "720"           # Septicemia & disseminated infections (194 = heart failure)

# Where to cache the download and save outputs (relative to the repo root)
DATA = Path("data")
FIGS = Path("figs")        # figures (.png)
RESULTS = Path("results")  # tables (.csv)
RAW_PATH = DATA / f"sparcs_2023_drg{APR_DRG}.parquet"

# Fixed so every run gives the same models and figures
SEED = 52
