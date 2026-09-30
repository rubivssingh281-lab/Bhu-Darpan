[33mcommit af7e1ac34e95bd61063170254b388721e69b24c2[m[33m ([m[1;36mHEAD[m[33m -> [m[1;32mmain[m[33m, [m[1;31morigin/main[m[33m, [m[1;31morigin/HEAD[m[33m)[m
Author: rubivssingh281-lab <rubivssingh281@gmail.com>
Date:   Tue Sep 29 10:22:48 2026 +0530

    Update data and ingest folders

[33mcommit 9c8c2b34b2f57b5d60c8eb676c5b248e6cbb7d8b[m
Author: rubivssingh281-lab <rubivssingh281@gmail.com>
Date:   Sun Sep 27 17:55:16 2026 +0530

    Raise model accuracy end-to-end and keep every section within a week of real time
    
    Land cover: promote ResNet-lite CNN (98.33% 10-class / 99.59% grouped, was 95.22 / 98.0) and replace the rule-first segmenter with a CNN-first hybrid fed the unenhanced image. Full pipeline on 2,700 EuroSAT test tiles 20.2% -> 84.8%; hand-labelled real scenes 37.3% -> 66.7%; scene checks 13/21 -> 16/21 (scripts/eval_segmentation.py -> models/segmentation_eval.json, served at /api/analysis/model).
    
    Forecast: unified 14-day backtest with a per-lead GBRT/LSTM/persistence blend (temperature +26.3%, rainfall +1.5% vs climatology); per-cell optimised persistence beats climatology at every lead; forecasts seeded from the live record.
    
    Fusion: BLUE with bias correction (rain -15.5%, temperature -3.9% error vs best source). Disaster: baseline suppresses permanent-water flood alerts, arid scenes use segmenter bare share, alpine snow threshold fixed (11/13 test scenes as expected).
    
    Freshness: 7-layer auto-refresh every 6 h and at startup, cache warm-up, live NASA POWER / Open-Meteo in the source registry; all 22 audited sections <= 3 days old. UI reads model accuracy from metrics files instead of hard-coded numbers.
    
    Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

[33mcommit ab60e2115d2353978530cdc84284e10e15561e22[m
Author: rubivssingh281-lab <rubivssingh281@gmail.com>
Date:   Sat Sep 26 14:40:00 2026 +0530

    Add region-at-a-glance facts and live seasonal-signals panels to Overview
    
    Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

[33mcommit 60d347fc512c5b71a62df34099e0541f4cf185d0[m
Author: rubivssingh281-lab <rubivssingh281@gmail.com>
Date:   Sat Sep 26 14:20:20 2026 +0530

    Extend hazards and data record to the current month with live NASA POWER
    
    The hazard indices and the daily-record span read from the 50-year CSV that ends 2023-12-30, so everything showed 'as of 2023'. Now the daily record is extended with a live NASA POWER tail (day-after-CSV to today), reconstructed on the CSV's day-of-year climatology via anomaly transfer so it splices continuously. Drought SPI, heatwave, monsoon, warming, extreme-rain, cold-wave and the Data & Models record span now run through the current month; falls back to the CSV alone if the POWER fetch fails. Cached per day.
    
    Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

[33mcommit 8437fe0ad45b997e771a6df5393a08da408d8d05[m
Author: rubivssingh281-lab <rubivssingh281@gmail.com>
Date:   Sat Sep 26 14:08:17 2026 +0530

    Push Overview content down so it clears the top-right login button
    
    Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

[33mcommit 061675b5d39ed4ddb88133af063480a11ee00ea0[m
Author: rubivssingh281-lab <rubivssingh281@gmail.com>
Date:   Sat Sep 26 14:04:56 2026 +0530

    Swap Overview and satellite Region landing content
    
    Climate-twin Overview now shows the EO-mission hero: live LIVE CLIMATE DOWNLINK telemetry card, mission-status chips, national-EO provenance badges and the 6-tile stat band (no map). The satellite Region tab's top half now shows the full Current climate state — live KPI cards with sparklines, regional summary, data-assimilation pipeline and per-district conditions — while keeping the pilot-region Leaflet map below it.
    
    Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
