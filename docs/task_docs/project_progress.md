# GEFS Precipitation Post-Processing Project Progress

## Overview

This document tracks progress on the toy ML project for post-processing GEFS precipitation ensembles to improve tail calibration for hydropower applications. The project follows the 6-phase plan in `docs/project_outline.md`, designed for a weekend build (10-12 hours total). We're using Jupyter notebooks for analysis and Python scripts for data processing.

**Project Goal**: Build and compare CRPS-optimized Gamma NN vs. Bayesian NN to adjust GEFS ensembles, focusing on extreme precipitation events. Output: Notebook with models, evaluations, and tail improvement plots.

**Current Date**: Sunday, September 28, 2025  
**Overall Status**: Phase 1 in progress (85% complete); Phases 2-6 pending. On track for weekend completion.

## Phase-by-Phase Progress

### Phase 1: Data Acquisition and Processing (In Progress - 85%)

**Goal**: Download and prep ~700 samples of GEFS ensemble precip + ERA5 ground truth + predictors for Rhine basin (lat 47-50°N, lon 7-10°E).

**Completed**:

- GEFS download pipeline: Standalone script (`scripts/download_gefs_ensemble.py`) handles 30 perturbed + control + spread + mean, 120-168 hour forecasts (3-hour intervals, 00z cycle).
- Rhine point extraction: tp values at (47.5565597, 8.0483).
- Incremental CSV saving with metadata (forecast_date, ensemble_member, forecast_hour, tp_value, valid_time).
- Robust features: Resume checkpointing, error handling, sequential processing, file cleanup.
- Local testing: 1-day validation (68 records).
- Directory structure aligned with scripts:
  - GEFS GRIB temp: `data/interim/gefs/`
  - GEFS extracted CSV: `data/processed/gefs_ensemble_tp.csv`
  - ERA5 NetCDF: `data/raw/era5/`
  - Logs/checkpoint: `scripts/`
- ERA5 downloader updated to default to `data/raw/era5` and fixed CDS API target writing.
- AWS deployment: Script running on EC2 for 1-month POC (2025-01-01 to 2025-01-31, ~22,000 files; expected 15-20 hours compute).

**Pending**:

- Complete AWS run and download `gefs_ensemble_tp.csv`.
- Download ERA5 reanalysis (daily/hourly precip via CDS API) - Task document created: `docs/task_docs/era5_data_acquisition.md`.
- Extract predictors: Lag-1/2 precip, 2m temperature from ERA5.
- Process: Resample GEFS to daily, interpolate missing values, 80/20 train/test split. Save as `processed_hydro_data.csv` (~500 train samples: lead_time, ensemble_members[31], obs_precip, lag1_precip, lag2_precip, temp).
- Expand to 2 years (2023-2024) if POC succeeds.

**Estimated Time**: 1-2 hours remaining (post-AWS: ERA5 + processing).  
**Status**: GEFS data collection ongoing; unlocks all downstream phases.

### Phase 2: Exploratory Data Analysis (EDA) (0% - Next)

**Goal**: Visualize data to confirm tail biases and predictor correlations (1 hour).

**Completed**: N/A  
**Pending**:

- Time series plots: Ensemble mean/spread vs. obs precip (highlight extremes).
- Distributions: Histograms/KDE for obs/ensemble; QQ plots vs. Gamma/normal.
- Tail analysis: Empirical CDF for high-precip days; CRPS baseline.
- Correlation matrix for predictors (lags/temp vs. precip).

**Deliverable**: 4-5 plots; notes on GEFS tail underestimation (e.g., "Misses 15% of >50mm events").  
**Libraries**: `matplotlib`, `seaborn`, `scipy.stats`.  
**Estimated Time**: 1 hour (after Phase 1 data ready).

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

- Inputs: Ensemble + predictors (~33 features).
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

- **Today (Sep 28, 2025)**: Monitor AWS GEFS run; start ERA5 if ready.
- **Phase 1 Complete**: By end of day (post-AWS download + processing).
- **Phases 2-3**: 1.5-2 hours (EDA + baseline) - Tomorrow morning.
- **Phases 4-5**: 4 hours (models) - Tomorrow afternoon.
- **Phase 6**: 1.5 hours (eval/polish) - Tomorrow evening.
- **Total**: ~10 hours; buffer for debugging.

**Risks**: AWS delays—use local 1-day data for Phases 2-3 POC. Weak results—emphasize methodology.

## Next Immediate Steps

1. Run ERA5 downloader for Jan 2025 to `data/raw/era5` (hourly tp, t2m).
2. Transform to daily aggregates + lag features → `data/processed/era5_processed_daily.csv`.
3. When AWS completes, merge GEFS CSV with ERA5 daily for modeling dataset.
4. Start Phase 2 EDA on merged data.

This keeps us organized—let me know when AWS finishes or if you need ERA5 code! 🚀
