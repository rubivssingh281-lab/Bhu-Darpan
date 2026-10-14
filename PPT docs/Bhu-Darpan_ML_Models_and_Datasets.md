# Bhu-Darpan ML Models and Datasets

This document outlines the core Machine Learning models, their datasets, training methodologies, challenges, and core knowledge used in the Bhu-Darpan project.

---

## 1. Land-Cover Classification Model
- **Model Type:** CNN (ResNet-lite, 4 stages, 17 convolutional layers, residual connections + Global Average Pooling).
- **Dataset:** EuroSAT RGB dataset (`EuroSAT.zip`). Sentinel-2 satellite imagery labeled into 10 classes (Forest, Water, Agriculture, Urban, etc.).
- **Dataset Source:** Open-access dataset of Sentinel-2 satellite images covering 13 spectral bands (using RGB here).
- **How it was Trained:** 
  - Optimized via SGD-Nesterov with a OneCycle learning rate schedule.
  - Utilizes label smoothing (0.1) and maintains an Exponential Moving Average (EMA) of the weights to prevent the model from being dominated by random initializations.
  - Implements CutMix augmentation alongside brightness/contrast jitter and random reflect-pad crops.
- **Challenges & Core Knowledge:**
  - *Challenge:* Overhead satellite imagery lacks a strict "up" orientation (rotational invariance).
  - *Core Solution:* The model uses vectorised **Dihedral Augmentation** during training (8 total combinations of rotations and flips) to force the network to recognize geographic features regardless of their orientation. During inference, **Test-Time Augmentation (TTA)** using 4-way rotation is applied to average out uncertainties and boost final predictive accuracy.

---

## 2. Climate & Weather Forecaster (14-Day Outlook)
- **Model Type:** Ensemble blend of a PyTorch LSTM sequence model and a scikit-learn Gradient Boosted Regression Trees (GBRT / HistGradientBoostingRegressor) model.
- **Dataset:** J&K state daily climate data spanning 50 years (`jk_state_daily_50y.csv`). Contains temperature and rainfall.
- **Dataset Source:** Aggregated historical meteorological data (IMD, NASA POWER, Open-Meteo).
- **How it was Trained:**
  - *LSTM:* A 30-day lookback window predicting a 14-day horizon. Uses cyclical sine/cosine time embeddings to capture seasonality.
  - *GBRT:* Trained recursively on autoregressive lag features (1, 2, 3, 7, 14, 30 days) and rolling means over the same 50-year span.
  - *Blending:* A Non-Negative Least Squares (NNLS) optimizer computes per-lead-day optimal weights combining the LSTM, GBRT, and a Persistence baseline. Fit strictly on a validation year to avoid leakage.
- **Challenges & Core Knowledge:**
  - *Challenge:* Predicting absolute weather values accurately over a 14-day horizon is incredibly noisy and prone to drift. Global warming trends also shift the baseline over 50 years.
  - *Core Solution:* The models are trained to predict the **Anomaly** (z-score deviation) relative to the day-of-year climatology baseline, rather than the absolute temperature or rainfall. The final prediction reconstructs the value via `Trend-Adjusted Climatology + Predicted Anomaly`. This ensures the model beats a naive climatology baseline and safely incorporates long-term warming trends without destabilizing the neural network.

---

## 3. Disaster-Scene Classifier
- **Model Type:** Pre-trained Foundation CNN (EfficientNet-B0 default; fallbacks to ResNet50 or ConvNeXt) using Transfer Learning.
- **Dataset:** AIDER (fire, flood, collapsed building, traffic incident, normal).
- **Dataset Source:** External public disaster datasets (AIDER GitHub, xView2 challenge).
- **How it was Trained:**
  - Employs a Two-Phase fine-tuning strategy: Phase 1 freezes the backbone and warms up the new classifier head; Phase 2 unfreezes the entire network at a low learning rate.
  - Uses Mixed Precision (AMP) for speed, Cosine Annealing learning rate schedule, and heavy augmentation (Random Erasing, Color Jitter, MixUp).
- **Challenges & Core Knowledge:**
  - *Challenge:* Extreme class imbalance between overwhelming 'normal' everyday scenes and very rare disaster events. 
  - *Core Solution:* Addressed using **Class-Balanced Sampling** (weighted random sampler) to expose the network to rare classes equally. Model selection is based on the **Macro-F1 Score** rather than raw accuracy, which heavily penalizes poor performance on rare classes. **MixUp Augmentation** is used to create interpolated boundary examples and improve generalization.

---

## 4. Analytical Impact Models (Crop Stress, Drought, Reservoir Inflow)
- **Model Type:** Scikit-learn tabular models (e.g., Random Forests/GBRT). 
- **Dataset:** Historical agronomic indices, hydrological flow rates, and soil moisture measurements.
- **Role:** These models take the primary predicted variables (temperature, rainfall, soil moisture) and translate them into secondary impact indices (e.g. crop water stress, reservoir inflow).
- **Challenges & Core Knowledge:**
  - *Challenge:* High-capacity tabular models like Random Forests can easily exceed 100MB+ in memory footprint (e.g., `model_inflow.pkl` is 130MB), making them cumbersome to load into limited-memory servers and impossible to push directly to standard GitHub repositories due to file size limits.
  - *Core Solution:* These large models are managed by zipping the raw pickles (`.pkl.zip`) for storage. The system also implements streamlined heuristic bounds (e.g., `inflow_change = rain_pct * 1.6 - temp_c * 3.5`) to allow the web app to function responsively even when the heavy models aren't loaded into RAM.
