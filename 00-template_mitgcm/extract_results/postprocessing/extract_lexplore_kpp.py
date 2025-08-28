#!/usr/bin/env python3
import xmitgcm as xm
import numpy as np
import os

ds = xm.open_mdsdataset("../run", ref_date="!formatted_ref_date!", prefix='kpp_diag', delta_t=!time_step!, endian=">")

x_lexplore = 49850
y_lexplore = 18100

i_xc = np.argmin(np.abs(ds['XC'].values - x_lexplore))
i_yc = np.argmin(np.abs(ds['YC'].values - y_lexplore))

ds_crop = ds[['KPPhbl','MXLDEPTH','KPPfrac']].isel(XC=i_xc, YC=i_yc)

output_dir = "../crop_results"
os.makedirs(output_dir, exist_ok=True)

output_file = os.path.join(output_dir, "lexplore_kpp.nc")
ds_crop.to_netcdf(output_file)

print(f'Lexplore kpp time series saved at: {output_file}')
