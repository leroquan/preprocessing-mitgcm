import json
import xarray as xr
import numpy as np
import glob as glob
import os
from scipy.interpolate import griddata
import requests
import re
from datetime import datetime, timedelta
from grid_and_bathy import MitgcmGrid


def download_weather_reanalysis(base_url, start_date, end_date, lat0, long0, lat1, long1, folder_path):
    # Convert input dates to datetime objects
    start_dt = datetime.strptime(start_date, "%Y%m%d")
    end_dt = datetime.strptime(end_date, "%Y%m%d")

    variables = ['T_2M', 'U', 'V', 'GLOB', 'RELHUM_2M', 'PMSL', 'CLCT', 'PS']
    # Loop through each day within the range
    current_date = start_dt
    while current_date < end_dt:
        next_date = current_date + timedelta(days=1)

        if next_date > end_dt:
            next_date = end_dt

        # Format dates for the API request
        start_window_str = current_date.strftime("%Y%m%d")
        end_window_str = next_date.strftime("%Y%m%d")

        for var in variables:
            # Construct the API URL for each 1-day window
            url = f"{base_url}/{start_window_str}/{end_window_str}/{lat0}/{long0}/{lat1}/{long1}?variables={var}"

            # Save the data to a file with date range in the filename
            file_name = f"{start_window_str}_{end_window_str}_{var}.json"
            file_path = os.path.join(folder_path, file_name)

            if os.path.isfile(file_path):
                print(f"Data already exists: {file_path}")
                continue

            # Fetch data from the API
            response = requests.get(url)

            if response.status_code == 200:
                with open(file_path, "w") as file:
                    file.write(response.text)
                    print(f"Saved data to {file_path}")
            else:
                print(
                    f"Failed to fetch data for {start_window_str} to {end_window_str}. Error : {response.text}. url : {url}")

        current_date = next_date


def download_weather_forecast(base_url, start_date, lat0, long0, lat1, long1, folder_path):
    # Convert input dates to datetime objects
    start_dt = datetime.strptime(start_date, "%Y%m%d")
    end_dt = start_dt + timedelta(days=4) #TO DO : change time window for different forecasts ?

    variables = ['T_2M', 'U', 'V', 'GLOB', 'RELHUM_2M', 'PMSL', 'CLCT', 'PS']
    for var in variables:
        url = f'{base_url}/{start_dt.strftime("%Y%m%d")}/{lat0}/{long0}/{lat1}/{long1}?variables={var}'
        # Fetch data from the API
        response = requests.get(url)

        if response.status_code == 200:
            # Save the data to a file with date range in the filename
            file_name = f'{start_dt.strftime("%Y%m%d")}_{end_dt.strftime("%Y%m%d")}_{var}.json'
            file_path = os.path.join(folder_path, file_name)

            with open(file_path, "w") as file:
                file.write(response.text)
                print(f"Saved data to {file_path}")
        else:
            print(f"Failed to fetch data for {start_dt} to {end_dt}. Error : {response.text}. url : {url}")


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


def interp_to_grid(json_file, data_type, mitgcm_grid: MitgcmGrid):
    '''
    json_file: path to json file
    data_type: string of parameter
    lat_grid, lon_grid: lat, lon mesh of grid for interpolation
    '''

    with open(json_file, "r") as file:
        json_data = json.load(file)
        time = np.array(json_data).item().get('time')
        lat = np.array(json_data['lat'])
        lon = np.array(json_data['lng'])
        try:
            data = np.array(json_data[data_type]['data'])
        except KeyError:
            data = np.array(json_data['variables'][data_type]['data'])

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

        if (start_date_json >= start_date) & (start_date_json < end_date) & (end_date_json > start_date):
            filtered_json_files.append(file)

    return filtered_json_files


def interp_concat_json(folder_json_path, data_type, str_start_date: str, str_end_date: str, mitgcm_grid: MitgcmGrid,
                       weather_model_type: str = "") -> xr.DataArray:
    all_json_files = glob.glob(os.path.join(folder_json_path, f'*_{data_type}.json'))
    json_files = filter_json_files_by_date(all_json_files, str_start_date, str_end_date)

    all_data = []

    if weather_model_type == "forecast":
        data_type = data_type + "_MEAN"

    for file in json_files:
        data = interp_to_grid(file, data_type, mitgcm_grid)
        all_data.append(data)

    all_data = xr.concat(all_data, dim='T').sortby('T')

    # remove duplicate values - review download from COSMO
    unique_values, unique_ind = np.unique(all_data['T'].values, return_index=True)
    unique_ind_sorted = np.sort(unique_ind)
    all_data_cleaned = all_data.isel(T=unique_ind_sorted)

    # binary file for MITgcm should be in XYT
    all_data_transposed = all_data_cleaned.transpose('T', 'Y', 'X')

    return (all_data_transposed)


def calculate_specific_humidity(temp, relhum, atm_press):
    """
    Compute specific humidity from air temperature, relative humidity and atmospheric pressure.

    - temp: Air temperature in Kelvin
    - relhum: Relative humidity in %
    - atm_press: Atmospheric pressure in Pascal
    """
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


def extract_and_save_surface_forcings(output_folder_path, start_date, end_date, path_raw_weather_folder,
                                      mitgcm_grid: MitgcmGrid, weather_model_type: str =""):
    check_output_folder(output_folder_path)

    #extract wind speed
    print('Interpolating u10 to grid...')
    u10 = interp_concat_json(path_raw_weather_folder, 'U', start_date, end_date, mitgcm_grid, weather_model_type)
    print(f'Saving u10 to file {os.path.join(output_folder_path, "u10.bin")}')
    write_binary(os.path.join(output_folder_path, 'u10.bin'), u10)
    print('Interpolating v10 to grid...')
    v10 = interp_concat_json(path_raw_weather_folder, 'V', start_date, end_date, mitgcm_grid, weather_model_type)
    print(f'Saving v10 to file {os.path.join(output_folder_path, "v10.bin")}')
    write_binary(os.path.join(output_folder_path, 'v10.bin'), v10)

    #extract air temperature
    print('Interpolating air temperature (atemp) to grid...')
    atemp = interp_concat_json(path_raw_weather_folder, 'T_2M', start_date, end_date, mitgcm_grid, weather_model_type)
    print(f'Saving atemp.')
    write_binary(os.path.join(output_folder_path, 'atemp.bin'), atemp)

    #extract surface pressure
    print('Interpolating atmospheric pressure (apress) to grid...')
    apress = interp_concat_json(path_raw_weather_folder, 'PS', start_date, end_date, mitgcm_grid, weather_model_type)
    print(f'Saving apressure.')
    write_binary(os.path.join(output_folder_path, 'apressure.bin'), apress)

    #extract specific humidity
    print('Interpolating relative humidity (relhum) to grid...')
    relhum = interp_concat_json(path_raw_weather_folder, 'RELHUM_2M', start_date, end_date, mitgcm_grid, weather_model_type)
    print('Computing specific humidity (aqh) from air temperature and cloud cover...')
    aqh = calculate_specific_humidity(atemp, relhum, apress)
    print(f'Saving aqh.')
    write_binary(os.path.join(output_folder_path, 'aqh.bin'), aqh)

    #extract shortwave radiation
    print('Interpolating shortwave radiation (swdown) to grid...')
    swr = interp_concat_json(path_raw_weather_folder, 'GLOB', start_date, end_date, mitgcm_grid, weather_model_type)
    filled_swr = swr.fillna(0)
    print(f'Saving swdown.')
    write_binary(os.path.join(output_folder_path, 'swdown.bin'), filled_swr)

    # extract longwave radiation
    print('Interpolating cloud cover (CLCT) to grid...')
    CLCT = interp_concat_json(path_raw_weather_folder, 'CLCT', start_date, end_date, mitgcm_grid, weather_model_type)
    print('Computing long wave radiation (lwdown) from air temperature and cloud cover...')
    lwr = compute_longwave_radiation(atemp, CLCT)
    print(f'Saving lwdown.')
    write_binary(os.path.join(output_folder_path, 'lwdown.bin'), lwr)