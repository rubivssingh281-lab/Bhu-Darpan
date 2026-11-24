"""Ecological Biomass & Carbon Sequestration Accounting.

Computes above-ground biomass (AGB) flux and gross carbon equivalent emissions (tCO2e)
resulting from vegetation/forest loss, based on IPCC Tier-1 and Forest Survey of India
(FSI) forestry allometrics for Western Himalayan ecosystems.
"""
from __future__ import annotations

# Forest Survey of India (FSI) & IPCC mean Above-Ground Biomass density (tonnes dry matter / hectare)
# for subtropical/temperate Western Himalayan mixed forest and agricultural cropland:
FOREST_AGB_TONS_PER_HA = 125.0
AGRI_AGB_TONS_PER_HA = 15.0

# Carbon fraction of dry biomass (IPCC default: ~47% carbon content)
CARBON_FRACTION = 0.47

# Stoichiometric conversion factor: C -> CO2 (44 / 12 = 3.667)
CO2_TO_C_RATIO = 44.0 / 12.0

# Default Sentinel-2 Ground Sampling Distance (GSD): 10 meters per pixel
DEFAULT_GSD_M = 10.0


def estimate_carbon_flux(
    forest_delta_pct: float,
    agri_delta_pct: float = 0.0,
    total_pixels: int = 100000,
    gsd_m: float = DEFAULT_GSD_M,
) -> dict:
    """Calculate estimated biomass loss (tons) and carbon flux (tCO2e).

    A negative delta indicates loss of vegetative cover.
    """
    pixel_area_m2 = gsd_m * gsd_m
    total_scene_ha = (total_pixels * pixel_area_m2) / 10000.0  # 1 ha = 10,000 m2

    forest_loss_pct = max(0.0, -forest_delta_pct)
    agri_loss_pct = max(0.0, -agri_delta_pct)

    forest_loss_ha = round((forest_loss_pct / 100.0) * total_scene_ha, 2)
    agri_loss_ha = round((agri_loss_pct / 100.0) * total_scene_ha, 2)

    biomass_loss_tons = round(
        (forest_loss_ha * FOREST_AGB_TONS_PER_HA) + (agri_loss_ha * AGRI_AGB_TONS_PER_HA), 2
    )
    carbon_flux_tco2e = round(biomass_loss_tons * CARBON_FRACTION * CO2_TO_C_RATIO, 2)

    return {
        "forest_loss_ha": forest_loss_ha,
        "agri_loss_ha": agri_loss_ha,
        "biomass_loss_tons": biomass_loss_tons,
        "carbon_flux_tco2e": carbon_flux_tco2e,
        "status": "net_emissions" if carbon_flux_tco2e > 0 else "neutral_or_sequestering",
        "guideline": "IPCC Tier-1 / Forest Survey of India (FSI)",
    }
