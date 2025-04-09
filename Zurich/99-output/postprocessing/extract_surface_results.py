#!/usr/bin/env python3
import xmitgcm as xm
import numpy as np
import os

ds = xm.open_mdsdataset("./", ref_date="2024-03-01 0:0:0", prefix='3Dsnaps', delta_t=32, endian=">")

ds_crop = ds[['THETA','UVEL','VVEL']].isel(Z=0)

output_dir = "../crop_results"
os.makedirs(output_dir, exist_ok=True)

output_file = os.path.join(output_dir, "surface.nc")
ds_crop.to_netcdf(output_file)

print(f'Lexplore time series saved at: {output_file}')
