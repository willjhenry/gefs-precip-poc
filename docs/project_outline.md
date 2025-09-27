# Toy Model for Post-Processing GEFS Precipitation Ensembles

This plan is designed for a weekend build (e.g., Saturday: Phases 1-3; Sunday: Phases 4-6), assuming 4-6 hours per day. Total estimated time: 10-12 hours, plus polishing. We'll use Python in Jupyter Notebook for reproducibility. Focus: Adjust GEFS ensemble distributions for better tail calibration on precipitation, comparing CRPS-optimized Gamma NN vs. Bayesian NN. Output: A notebook with models, evals, and plots showing tail improvements—perfect for interview demo.

## Phase 1: Data Acquisition and Processing (1-2 hours)

- **Goal**: Download and prep a small, focused dataset for a European hydropower-relevant region (e.g., Rhine basin or Alps proxy: lat 47-50°N, lon 7-10°E).
- **Steps**:
  1. Download GEFS ensemble data: Use NOAA's AWS Open Data (free, no API key). Pull 2-3 day lead-time daily total precipitation (TP) for ~2 years (e.g., 2023-2024; ~700 samples). Grab 30 perturbed members (p01-p30) + control (c00) + spread (gespr) + mean (geavg) via `boto3` or `cdsapi` if needed—focus on surface-level TP variable. Code snippet: Use `xarray` to load NetCDF files from s3://noaa-gefs-pds/.
  2. Get ground truth: Pull ERA5 hourly/daily precip reanalysis (free via CDS API) for the same grid point/region to serve as "observations."
  3. Add predictors: Extract lagged vars from ERA5—lag-1 precip, lag-2 precip, surface temp (2m)—as time series for the same location.
  4. Process: Resample to daily, handle missing values (interpolate), split 80/20 train/test. Save as Pandas DataFrame or xarray Dataset. Shape: ~500 train samples, columns like [lead_time, ensemble_members[31], obs_precip, lag1_precip, lag2_precip, temp].
- **Deliverable**: Clean CSV/NetCDF files; quick sanity plot of ensemble spread vs. obs.
- **Libraries**: `xarray`, `pandas`, `cdsapi`, `boto3` (install if needed, but all free/open).
- **Risk/Mitigation**: Download limits—start with 1 year if slow; test on a single grid point.

## Phase 2: Exploratory Data Analysis (EDA) (1 hour)

- **Goal**: Understand data quirks, especially tails, to motivate models.
- **Steps**:
  1. Plot time series: GEFS ensemble mean/spread vs. obs precip; highlight extremes (e.g., >90th percentile events).
  2. Distribution checks: Histograms/KDE of obs precip (confirm skew/heavy tails), ensemble members; QQ plots vs. Gamma/normal.
  3. Tail focus: Compute empirical CDF for high precip days; check if GEFS underestimates tails (e.g., CRPS baseline).
  4. Predictors: Correlation matrix—ensure lags/temp correlate with precip (~0.3-0.5 expected).
- **Deliverable**: 4-5 plots in notebook; notes on tail bias (e.g., "GEFS misses 15% of >50mm events").
- **Libraries**: `matplotlib`, `seaborn`, `scipy.stats`.
- **Risk/Mitigation**: No surprises—skip deep dives if data looks good.

## Phase 3: Baseline Evaluation (30-45 min)

- **Goal**: Quantify raw GEFS skill to benchmark improvements.
- **Steps**:
  1. Aggregate ensemble: Compute mean, std from 21 members as "forecast dist."
  2. Metrics: CRPS (via `prophet` or custom func), MAE for mean, tail-specific (e.g., hit rate for >95th percentile events).
  3. Plot: Calibration plots (predicted vs. observed quantiles, focus on tails).
- **Deliverable**: Baseline scores table; plot showing tail underconfidence.
- **Libraries**: Custom CRPS (simple integral approx) or `crps` from `scores`.
- **Risk/Mitigation**: If CRPS code bugs, use MAE as fallback.

## Phase 4: CRPS-Optimized Neural Network Development (2 hours)

- **Goal**: Build a fast NN that adjusts GEFS ensemble to Gamma params via CRPS loss.
- **Steps**:
  1. Inputs: Concat ensemble members + predictors (flatten to ~25 features).
  2. Architecture: Simple MLP (2-3 layers, 64 units, ReLU) outputting Gamma shape/scale (2 params).
  3. Loss: CRPS for Gamma dist (use `tensorflow_probability` for dist; approx CRPS via Monte Carlo samples from predicted Gamma).
  4. Train: 50-100 epochs, Adam optimizer, batch 32. Validate on holdout.
  5. Inference: For test, sample from adjusted Gamma to get dist; compute ensemble blend if needed.
- **Deliverable**: Trained model; prediction dist plots vs. baseline.
- **Libraries**: `tensorflow` (or `pytorch`), `tensorflow_probability` for Gamma.
- **Risk/Mitigation**: CRPS non-differentiable—use soft approx (e.g., 100 samples); if slow, reduce layers.

## Phase 5: Bayesian Neural Network Development (2 hours)

- **Goal**: Build BNN variant for uncertainty-aware adjustments.
- **Steps**:
  1. Reuse inputs/arch from Phase 4.
  2. Bayesian setup: Use PyMC for variational inference on weights (or simple priors on output params).
  3. Priors: Normal(0,1) on weights; Gamma prior on precip params.
  4. Likelihood: Student-t or Gamma for precip (tail-friendly); sample posterior (1000 draws).
  5. Inference: ADVI for speed; generate predictive dist by sampling weights and running forward.
  6. Compare to Phase 4: Same CRPS eval.
- **Deliverable**: Sampled posteriors; uncertainty bands on predictions.
- **Libraries**: `pymc` (with `aesara` backend).
- **Risk/Mitigation**: Sampling slow—use fewer draws (200); fallback to MAP if VI fails.

## Phase 6: Evaluation, Comparison, and Polish (1-2 hours)

- **Goal**: Show why this rocks for tails/hydropower; prep interview-ready.
- **Steps**:
  1. Metrics table: CRPS, tail hit rate, calibration score—compare baseline, CRPS-NN, BNN.
  2. Plots: Side-by-side dists for 5 extreme test days; uncertainty vs. overconfidence.
  3. Insights: Bullet why BNN wins tails (e.g., "20% better extreme capture via weight uncertainty").
  4. Export: Save models/plots; add README with "How this adjusts GEFS for hydro extremes."
- **Deliverable**: Full notebook; 1-page summary PDF/slides outline.
- **Libraries**: `pandas` for tables, `matplotlib` for plots.
- **Risk/Mitigation**: Weak skill? Emphasize concepts ("Proof tails improve 10-15%"); test on synthetic spikes if needed.

## Total Timeline

Weekend coding done by Sunday night; week for presentation tweaks (e.g., 5-min demo script). If stuck, ping for code snippets. This'll make you shine—hands-on + thoughtful on uncertainty! Ready to dive into Phase 1 code?
