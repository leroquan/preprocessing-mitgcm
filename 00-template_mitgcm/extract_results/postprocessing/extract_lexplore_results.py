#!/usr/bin/env python3
import xmitgcm as xm
import numpy as np
import os

ds = xm.open_mdsdataset("../run", ref_date="!formatted_ref_date!", prefix='3Dsnaps', delta_t=!time_step!, endian=">")

x_lexplore = 49850
y_lexplore = 18100

i_xc = np.argmin(np.abs(ds['XC'].values - x_lexplore))
i_yc = np.argmin(np.abs(ds['YC'].values - y_lexplore))
i_xg = np.argmin(np.abs(ds['XG'].values - x_lexplore))
i_yg = np.argmin(np.abs(ds['YG'].values - y_lexplore))

ds_crop = ds[['THETA','UVEL','VVEL']].isel(XC=i_xc, YC=i_yc, XG=i_xg, YG=i_yg)

output_dir = "../crop_results"
os.makedirs(output_dir, exist_ok=True)

output_file = os.path.join(output_dir, "lexplore_depth_time.nc")
ds_crop.to_netcdf(output_file)

print(f'Lexplore time series saved at: {output_file}')
