#!/usr/bin/env python3
import xmitgcm as xm
import numpy as np
import os

ds = xm.open_mdsdataset("./", ref_date="2024-03-01 0:0:0", prefix='3Dsnaps', delta_t=32, endian=">")

i_xc = np.argmin(np.abs(ds['XC'].values - 49850))
i_yc = np.argmin(np.abs(ds['YC'].values - 18100))
i_xg = np.argmin(np.abs(ds['XG'].values - 49850))
i_yg = np.argmin(np.abs(ds['YG'].values - 18100))

ds_crop = ds[['THETA','UVEL','VVEL']].isel(XC=i_xc, YC=i_yc, XG=i_xg, YG=i_yg)

output_dir = "../crop_results"
os.makedirs(output_dir, exist_ok=True)

output_file = os.path.join(output_dir, "lexplore_depth_time.nc")
ds_crop.to_netcdf(output_file)

print(f'Lexplore time series saved at: {output_file}')
