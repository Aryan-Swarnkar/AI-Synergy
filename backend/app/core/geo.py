"""Haversine distances, vectorised with numpy (SPEC §5.3 step 3). Pure: no DB imports."""
from __future__ import annotations

import numpy as np

EARTH_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Great-circle distance from one point to arrays of points (km)."""
    lat1r = np.radians(np.asarray(lat1, dtype=float))
    lon1r = np.radians(np.asarray(lon1, dtype=float))
    lat2r = np.radians(np.asarray(lats, dtype=float))
    lon2r = np.radians(np.asarray(lons, dtype=float))
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2.0) ** 2
    return 2.0 * EARTH_KM * np.arcsin(np.sqrt(a))
