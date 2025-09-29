# GEFS Precipitation Post-Processing Project Progress

## Overview

This document tracks progress on the toy ML project for post-processing GEFS precipitation ensembles to improve tail calibration for hydropower applications. The project follows the 6-phase plan in `docs/project_outline.md`, designed for a weekend build (10-12 hours total). We're using Jupyter notebooks for analysis and Python scripts for data processing.

**Project Goal**: Build and compare CRPS-optimized Gamma NN vs. Bayesian NN to adjust GEFS ensembles, focusing on extreme precipitation events. Output: Notebook with models, evaluations, and tail improvement plots.

**Current Date**: Monday, September 29, 2025  
**Overall Status**: Phase 1 complete (100%); Phases 2-6 pending. On track for weekend completion; data pipelines ready for execution.

## Phase-by-Phase Progress

### Phase 1: Data Acquisition and Processing (Complete - 100%)

**Goal**: Download and prep ~700 samples of GEFS ensemble precip + ERA5 ground truth + predictors for Rhine basin (lat 47-50°N, lon 7-10°E).

**Completed**:

- GEFS download pipeline: Standalone script (`scripts/download_gefs_ensemble.py`) handles 30 perturbed + control + spread + mean, 120-168 hour forecasts (3-hour intervals, 00z cycle).
- Rhine point extraction: tp values at (47.5565597, 8.0483).
- Incremental CSV saving with metadata (forecast_date, ensemble_member, forecast_hour, tp, valid_time).
- Robust features: Resume checkpointing, error handling, sequential processing, file cleanup.
- Local testing: 1-day validation (68 records).
- Directory structure aligned with scripts:
  - GEFS GRIB temp: `data/interim/gefs/`
  - GEFS extracted CSV: `data/processed/gefs_ensemble_tp.csv`
  - ERA5 NetCDF: `data/raw/era5/`
  - Logs/checkpoint: `scripts/`
- ERA5 downloader: Standalone script (`scripts/download_era5.py`) for tp/t2m via CDS API, with point extraction at Rhine location.
- Refactors: Both GEFS and ERA5 pipelines refactored to use dedicated classes (`GefsDownloader`, `Era5Downloader`) in `src/hydro/data/` for reusability.
- Path centralization: All project paths (DATA_DIR, SCRIPTS_DIR, RAW_ERA5_DIR, INTERIM_GEFS_DIR, etc.) moved to `src/hydro/common.py` for consistency.
- AWS deployment: Script ready for EC2; local validation complete.

- Dataset assembly: Implemented monthly indicator columns (jan–dec) and GEFS ensemble statistics (min, max, q10, q90, skew, kurtosis) in `src/hydro/data_processors/dataset_assembler.py`.

**Pending**: N/A (code ready; execution next).

**Estimated Time**: 0 hours remaining (pipelines built).  
**Status**: Data acquisition infrastructure complete; ready for full dataset collection.

### Phase 2: Exploratory Data Analysis (EDA) (0% - Next)

**Goal**: Visualize data to confirm tail biases and predictor correlations (1 hour).

**Completed**: N/A  
**Pending**:

- Run full GEFS download (1-month POC via AWS) to populate `gefs_ensemble_tp.csv`.
- Download ERA5 reanalysis (daily/hourly precip via CDS API) - Task document: `docs/task_docs/era5_data_acquisition.md`.
- Extract predictors: Lag-1/2 precip, 2m temperature from ERA5.
- Process: Resample GEFS to daily, interpolate missing values, 80/20 train/test split. Save as `processed_hydro_data.csv` (~500 train samples: lead_time, ensemble_members[31], obs_precip, lag1_precip, lag2_precip, temp).
- Time series plots: Ensemble mean/spread vs. obs precip (highlight extremes).
- Distributions: Histograms/KDE for obs/ensemble; QQ plots vs. Gamma/normal.
- Tail analysis: Empirical CDF for high-precip days; CRPS baseline.
- Correlation matrix for predictors (lags/temp vs. precip).

**Deliverable**: 4-5 plots; notes on GEFS tail underestimation (e.g., "Misses 15% of >50mm events").  
**Libraries**: `matplotlib`, `seaborn`, `scipy.stats`.  
**Estimated Time**: 1.5 hours (includes data collection/processing).

### Phase 3: Baseline Evaluation (0%)

**Goal**: Quantify raw GEFS skill (CRPS/MAE/tail hit rates) for benchmarking (30-45 min).

**Completed**: N/A  
**Pending**:

- Aggregate ensemble (mean/std from 32 members).
- Metrics: CRPS (custom func), MAE, tail hit rate (>95th percentile).
- Calibration plots focusing on tails.

**Deliverable**: Baseline scores table; plot showing tail underconfidence.  
**Libraries**: Custom CRPS or `scores` package.  
**Estimated Time**: 45 min (post-Phase 2).

### Phase 4: CRPS-Optimized Neural Network Development (0%)

**Goal**: MLP for Gamma params (shape/scale) with CRPS loss (2 hours).

**Completed**: N/A  
**Pending**:

- Inputs: Ensemble + predictors (~50+ features, incl. ensemble stats and monthly indicators).
- Architecture: 2-3 layer MLP (64 units, ReLU) → 2 Gamma params.
- Loss: CRPS approx via Monte Carlo samples.
- Train: 50-100 epochs, Adam, batch 32; validate on holdout.
- Inference: Sample from adjusted Gamma dist.

**Deliverable**: Trained model; prediction dist plots vs. baseline.  
**Libraries**: `tensorflow`, `tensorflow_probability`.  
**Estimated Time**: 2 hours.

### Phase 5: Bayesian Neural Network Development (0%)

**Goal**: BNN for uncertainty-aware adjustments (2 hours).

**Completed**: N/A  
**Pending**:

- Reuse Phase 4 inputs/arch.
- Bayesian setup: PyMC variational inference on weights.
- Priors: Normal on weights; Gamma on precip params.
- Likelihood: Student-t/Gamma for tails; 1000 posterior samples.
- Inference: ADVI; predictive dist via weight sampling.

**Deliverable**: Posterior samples; uncertainty bands on predictions.  
**Libraries**: `pymc`.  
**Estimated Time**: 2 hours.

### Phase 6: Evaluation, Comparison, and Polish (0%)

**Goal**: Compare models and prep demo (1-2 hours).

**Completed**: N/A  
**Pending**:

- Metrics table: CRPS, tail hit rate, calibration—baseline vs. NN vs. BNN.
- Plots: Side-by-side dists for 5 extreme days; uncertainty analysis.
- Insights: Bullets on tail improvements (e.g., "BNN boosts extreme capture 20%").
- Export: Save models/plots; README with hydro relevance.

**Deliverable**: Full notebook; 1-page summary PDF/slides.  
**Libraries**: `pandas`, `matplotlib`.  
**Estimated Time**: 1.5 hours.

## Timeline & Milestones

- **Today (Sep 29, 2025)**: Execute GEFS/ERA5 downloads; merge datasets.
- **Phase 1 Complete**: Done (pipelines ready).
- **Phases 2-3**: 2 hours (EDA + baseline) - Today afternoon.
- **Phases 4-5**: 4 hours (models) - Tomorrow morning/afternoon.
- **Phase 6**: 1.5 hours (eval/polish) - Tomorrow evening.
- **Total**: ~8 hours remaining; buffer for debugging.

**Risks**: Data quality issues—validate with 1-day local run. Weak results—emphasize methodology.

## Next Immediate Steps

1. Run GEFS downloader for Jan 2025 via AWS to `data/processed/gefs_ensemble_tp.csv`.
2. Run ERA5 downloader for matching period to `data/raw/era5/` (tp, t2m).
3. Process/merge: Resample to daily; assemble dataset with monthly indicators and ensemble stats + ERA5 lags → `data/processed_hydro_data.csv`.
4. Start Phase 2 EDA on merged data.

This keeps us organized—let me know when downloads finish or if you need processing scripts! 🚀
