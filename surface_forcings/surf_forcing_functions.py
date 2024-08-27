import json
import xarray as xr
import numpy as np
import glob as glob
import os
from scipy.interpolate import griddata
import re
from datetime import datetime

class MitgcmGrid():
    def __init__(self, path_grid):
        self.x = np.load(os.path.join(path_grid, 'x.npy'))
        self.y = np.load(os.path.join(path_grid, 'y.npy'))
        self.lat_grid = np.load(os.path.join(path_grid, 'lat_grid.npy'))
        self.lon_grid = np.load(os.path.join(path_grid, 'lon_grid.npy'))

def write_binary(path_fname,data):
    '''
    Saves data in the right binary format for MITgcm, in the dimension order XYT
    Output binary files have been read and tested
    '''

    data = data.to_numpy() #convert to xarray to numpy first - and then save to binary
    dtype = '>f8'  # big-endian and precision 64 (small-endian with precision 32 is '<f4')
    data = data.astype(dtype)

    # Write to file
    fid = open(path_fname, 'wb')
    data.tofile(fid)
    fid.close()


def interp_to_grid(json_file, data_type, mitgcm_grid):
    '''
    json_file: path to json file
    data_type: string of parameter
    lat_grid, lon_grid: lat, lon mesh of grid for interpolation
    '''

    with open(json_file, "r") as file:
        data = json.load(file)
        time = np.array(data).item().get('time')
        lat = np.array(data['lat'])
        lon = np.array(data['lng'])
        data = np.array(data[data_type]['data'])

    data_interp = []

    for ii in np.arange(len(time)):
        time_ii = time[ii]
        # Flatten the original lat/lon mesh and data
        coord_raw_data = np.array([lat.flatten(), lon.flatten()]).T
        data_flat = data[ii, :, :].flatten()
        data_interp_tt = griddata(coord_raw_data, data_flat, (mitgcm_grid.lat_grid, mitgcm_grid.lon_grid),
                                  method='cubic')

        # set as xarray - replace lat_grid and lon_grid with XY grid
        data_interp_tt = xr.DataArray(data_interp_tt, dims=["Y", "X"],
                                      coords={"X": mitgcm_grid.x, "Y": mitgcm_grid.y, })

        data_interp_tt = data_interp_tt.assign_coords({"T": time_ii})

        data_interp.append(data_interp_tt)

    data_interp = xr.concat(data_interp, dim='T').sortby('T')

    return (data_interp)


def filter_json_files_by_date(all_json_files: list[str], str_start_date: str, str_end_date: str) -> list[str]:
    start_date = datetime.strptime(str_start_date, '%Y%m%d')
    end_date = datetime.strptime(str_end_date, '%Y%m%d')

    filtered_json_files = []
    for file in all_json_files:
        json_dates = re.findall(r'\d{8}', file)
        start_date_json = datetime.strptime(json_dates[0], '%Y%m%d')
        end_date_json = datetime.strptime(json_dates[1], '%Y%m%d')

        if (start_date_json >= start_date) & (start_date_json < end_date) & (end_date_json > start_date) & (
                end_date_json <= end_date):
            filtered_json_files.append(file)

    return filtered_json_files


def interp_concat_json(folder_json_path, data_type, str_start_date: str, str_end_date: str, mitgcm_grid: MitgcmGrid) \
        -> xr.DataArray:
    all_json_files = glob.glob(os.path.join(folder_json_path, f'*_{data_type}.json'))
    json_files = filter_json_files_by_date(all_json_files, str_start_date, str_end_date)

    all_data = []

    for file in json_files:
        data = interp_to_grid(file, data_type, mitgcm_grid)
        all_data.append(data)

    all_data = xr.concat(all_data, dim='T').sortby('T')

    # remove duplicate values - review download from COSMO
    _, unique_ind = np.unique(np.unique(all_data['T'].values), return_index=True)
    unique_ind_sorted = np.sort(unique_ind)
    all_data = all_data.isel(T=unique_ind_sorted)

    # binary file for MITgcm should be in XYT
    all_data = all_data.transpose('T', 'Y', 'X')

    return (all_data)


def calculate_specific_humidity(temp, relhum, atm_press):
    # temp needs to be in celcius
    temp = temp - 273.15

    # atmospheric pressure should be in hPa
    atm_press = atm_press / 100.0

    # saturation vapour pressure (e_s)
    e_s = 6.112 * np.exp((17.67 * temp) / (temp + 243.5))

    # actual vapour pressure (e)
    e = (relhum / 100) * e_s

    # Step 3: Calculate the specific humidity (q)
    q = (0.622 * e) / (atm_press - (0.378 * e))

    return (q)


def compute_longwave_radiation(atemp, cloud_cover):
    """
    Compute longwave radiation from air temperature and cloud cover.

    - temp: Air temperature in Kelvin
    - cloud_cover: %
    """
    # cloud cover should be from 0 to 1
    cloud_cover = cloud_cover/100
    cloud_cover = cloud_cover.where(cloud_cover > 0,0)
    vaporPressure = 6.11 * np.exp(17.67 * (atemp-273.15) / (atemp-29.65)) # in units of hPa
    A_L = 0.03   # Infrared radiation albedo
    a = 1.09     # Calibration parameter
    E_a = a * (1 + 0.17 * np.power(cloud_cover, 2)) * 1.24 * np.power(vaporPressure / atemp, 1./7)
    lwr = (1 - A_L) * 5.67e-8 * E_a * np.power(atemp, 4)
    return lwr

def check_output_folder(output_folder_path):
    if not os.path.exists(output_folder_path):
        os.makedirs(output_folder_path)
        print(f"Directory '{output_folder_path}' created.")


def extract_and_save_surface_forcings(output_folder_path, start_date, end_date, path_raw_weather_folder, path_grid):
    check_output_folder(output_folder_path)

    #load mitgcm model grid
    mitgcm_grid = MitgcmGrid(path_grid)

    #extract wind speed
    u10 = interp_concat_json(path_raw_weather_folder, 'U', start_date, end_date, mitgcm_grid)
    v10 = interp_concat_json(path_raw_weather_folder, 'V', start_date, end_date, mitgcm_grid)
    write_binary(os.path.join(output_folder_path, 'u10.bin'), u10)
    write_binary(os.path.join(output_folder_path, 'v10.bin'), v10)

    #extract air temperature
    atemp = interp_concat_json(path_raw_weather_folder, 'T_2M', start_date, end_date, mitgcm_grid)
    write_binary(os.path.join(output_folder_path, 'atemp.bin'), atemp)

    #extract surface pressure
    apress = interp_concat_json(path_raw_weather_folder, 'PS', start_date, end_date, mitgcm_grid)
    pmsl = interp_concat_json(path_raw_weather_folder, 'PMSL', start_date, end_date, mitgcm_grid)
    write_binary(os.path.join(output_folder_path, 'apressure.bin'), apress)

    #extract specific humidity
    relhum = interp_concat_json(path_raw_weather_folder, 'RELHUM_2M', start_date, end_date, mitgcm_grid)
    aqh = calculate_specific_humidity(atemp, relhum, apress)
    write_binary(os.path.join(output_folder_path, 'aqh.bin'), aqh)

    #extract shortwave radiation
    swr = interp_concat_json(path_raw_weather_folder, 'GLOB', start_date, end_date, mitgcm_grid)
    write_binary(os.path.join(output_folder_path, 'swdown.bin'), swr)

    # extract longwave radiation
    CLCT = interp_concat_json(path_raw_weather_folder, 'CLCT', start_date, end_date, mitgcm_grid)
    lwr = compute_longwave_radiation(atemp, CLCT)
    write_binary(os.path.join(output_folder_path, 'lwdown.bin'), lwr)