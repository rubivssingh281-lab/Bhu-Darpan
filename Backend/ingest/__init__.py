"""Bhū-Darpan national-data ingestion ETL.

Pluggable sources → decode → regrid to a common grid → store as NetCDF, with a
manifest the API/UI can read.

Sources
-------
- power   : NASA POWER regional daily grid (open, no credentials) — the live,
            runnable source used to prove the pipeline end-to-end now.
- imd     : IMD Pune gridded rainfall/temperature via `imdlib` (public, but the
            IMD server must be reachable) — the intended production ground source.
- mosdac  : INSAT L2B products (LST/SST/rainfall) from MOSDAC — requires a MOSDAC
            account (MOSDAC_USER / MOSDAC_PASS); credential-gated adapter.
"""
