import numpy as np
import pandas as pd
import xarray as xr


def create_initial_temperature_from_measure_profile(dz_grid: np.array, xr_measure: xr.Dataset) -> np.array:

    z_grid = np.cumsum(dz_grid.flatten())

    temp_initial = xr_measure.interp(depth=z_grid, method='linear')
    filled_temp_initial = temp_initial.ffill(dim='depth').bfill(dim='depth')
    shaped_temp_initial = filled_temp_initial['temp'].values.reshape(dz_grid.shape)

    return shaped_temp_initial


