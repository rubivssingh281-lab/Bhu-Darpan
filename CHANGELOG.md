# Changelog

All notable changes to the **Bhū-Darpan** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- High-resolution INSAT-3DR multispectral thermal ingestion pipeline.
- Multi-basin boundary scaling beyond the Jammu & Kashmir regional pilot.

## [1.0.0] - 2026-11-05

### Added
- **Climate Digital Twin**:
  - Unified 0.25° coordinate mesh fusion (NASA POWER, IMD gridded feeds, Open-Meteo).
  - Hazard risk scoring algorithms for real-time drought, flood, and fire risk assessment.
  - Interactive multi-parameter anomaly baselines computed against 50-year regional records.
- **Satellite Image Analysis**:
  - Pretrained EuroSAT CNN deep learning classifier achieving 95.9% test accuracy across 10 land-cover classes.
  - K-Means spectral clustering and texture segmentation for automated spatial partitioning.
  - Pairwise temporal difference analysis for vegetative and urban land-cover change detection.
  - Automated PDF assessment report compilation via ReportLab with embedded classification tables.
- **Backend Architecture & APIs**:
  - Single-process FastAPI server with zero-build front-end mounting.
  - JWT token and email OTP authentication system with offline dev-OTP fallback mode.
  - Local SQLite metadata storage and NetCDF gridded data cache.
- **DevOps & Tooling**:
  - Multi-stage production `Dockerfile` and `docker-compose.yml` service orchestration.
  - Pre-commit formatting hygiene with Ruff and GitHub Actions CI workflow.
