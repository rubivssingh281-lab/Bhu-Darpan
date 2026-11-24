"""Tests for ecological biomass and carbon sequestration flux accounting."""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # Backend/

from app.services import biomass


def test_estimate_carbon_flux_zero():
    res = biomass.estimate_carbon_flux(forest_delta_pct=0.0, agri_delta_pct=0.0, total_pixels=10000)
    assert res["forest_loss_ha"] == 0.0
    assert res["agri_loss_ha"] == 0.0
    assert res["biomass_loss_tons"] == 0.0
    assert res["carbon_flux_tco2e"] == 0.0
    assert res["status"] == "neutral_or_sequestering"


def test_estimate_carbon_flux_forest_loss():
    # 10,000 pixels @ 10m GSD = 1,000,000 m2 = 100 ha
    # 10% forest loss = 10 ha
    # 10 ha * 125 t/ha = 1250 tons biomass
    # 1250 * 0.47 * (44 / 12) = 2154.17 tCO2e
    res = biomass.estimate_carbon_flux(
        forest_delta_pct=-10.0,
        agri_delta_pct=0.0,
        total_pixels=10000,
        gsd_m=10.0,
    )
    assert res["forest_loss_ha"] == 10.0
    assert res["biomass_loss_tons"] == 1250.0
    assert abs(res["carbon_flux_tco2e"] - 2154.17) < 0.1
    assert res["status"] == "net_emissions"
    assert "IPCC" in res["guideline"]


def test_estimate_carbon_flux_positive_delta_neutral():
    # Reforestation / positive vegetation delta should not report positive loss
    res = biomass.estimate_carbon_flux(forest_delta_pct=5.0, agri_delta_pct=2.0)
    assert res["biomass_loss_tons"] == 0.0
    assert res["carbon_flux_tco2e"] == 0.0
    assert res["status"] == "neutral_or_sequestering"


if __name__ == "__main__":
    test_estimate_carbon_flux_zero()
    test_estimate_carbon_flux_forest_loss()
    test_estimate_carbon_flux_positive_delta_neutral()
    print("All carbon biomass accounting tests passed successfully!")
