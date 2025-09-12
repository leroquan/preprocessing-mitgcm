import orjson
import xarray as xr
import numpy as np
import pandas as pd
import glob as glob
import os
from scipy.interpolate import griddata
import requests
import re
from datetime import datetime, timedelta
from grid_and_bathy import MitgcmGrid
from concurrent.futures import ThreadPoolExecutor


def fetch_and_save(url, file_path):
    """Fetch data from the API and save it to a file."""
    if os.path.isfile(file_path):
        print(f"Data already exists: {file_path}")
        return

    response = requests.get(url)
    if response.status_code == 200:
        with open(file_path, "w") as file:
            file.write(response.text)
        print(f"Saved data to {file_path}")
    else:
        print(f"Failed to fetch data from {url}. Error: {response.text}")


def download_weather_reanalysis(base_url, start_date, end_date, lat0, long0, lat1, long1, folder_path):
    start_dt = datetime.strptime(start_date, "%Y%m%d")
    end_dt = datetime.strptime(end_date, "%Y%m%d")

    variables = ['T_2M', 'U', 'V', 'GLOB', 'RELHUM_2M', 'PMSL', 'CLCT', 'PS']
    current_date = start_dt

    with ThreadPoolExecutor(max_workers=8) as executor:  # Adjust workers as needed
        futures = []

        while current_date <= end_dt:
            start_window_str = current_date.strftime("%Y%m%d")
            end_window_str = current_date.strftime("%Y%m%d")

            for var in variables:
                url = f"{base_url}/{start_window_str}/{end_window_str}/{lat0}/{long0}/{lat1}/{long1}?variables={var}"
                file_name = f"{start_window_str}_{end_window_str}_{var}.json"
                file_path = os.path.join(folder_path, file_name)

                # Submit each request as a separate thread
                futures.append(executor.submit(fetch_and_save, url, file_path))

            current_date += timedelta(days=1)

        # Wait for all threads to finish
        for future in futures:
            future.result()


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


def load_json(file_path: str) -> dict:
    with open(file_path, "rb") as file:
        return orjson.loads(file.read())


def extract_data_from_json(json_data: dict, json_path: str, data_type: str) -> np.array:
    # Handle possible different data structures
    if data_type in json_data:
        data = np.array(json_data[data_type]["data"])
    elif "variables" in json_data and data_type in json_data["variables"]:
        data = np.array(json_data["variables"][data_type]["data"])
    else:
        raise KeyError(f"Data type '{data_type}' not found in JSON {json_path}.")

    return data


def select_first_24h(parsed_times: np.array(datetime), data: np.array):
    start_time = parsed_times[0]  # Assuming times are sorted
    end_time = start_time + pd.Timedelta(hours=24)
    valid_indices = (parsed_times >= start_time) & (parsed_times < end_time)

    parsed_times = parsed_times[valid_indices]  # Filter timestamps
    data = data[valid_indices]  # Filter data

    return parsed_times, data


def interp_to_grid(json_file: str, data_type: str, mitgcm_grid: MitgcmGrid, weather_model_type: str = ""):
    # Load JSON data once with orjson
    json_data = load_json(json_file)

    # Extract timestamps and convert to datetime
    parsed_times = pd.to_datetime(
        np.array(json_data).item().get('time')
        ).tz_localize(None)

    # Extract latitude and longitude
    lat, lon = np.array(json_data['lat']), np.array(json_data['lng'])
    coord_raw_data = np.column_stack((lat.flatten(), lon.flatten()))

    data = extract_data_from_json(json_data, json_file, data_type)
    if weather_model_type == 'forecast':
        filtered_parsed_times, filtered_data = parsed_times, data
    else:
        filtered_parsed_times, filtered_data = select_first_24h(parsed_times, data)

    # Interpolate over all time steps (first 24h)
    data_interp = [
        xr.DataArray(
            griddata(coord_raw_data, filtered_data[i].flatten(),
                     (mitgcm_grid.lat_grid, mitgcm_grid.lon_grid),
                     method="linear"),
            dims=["Y", "X"],
            coords={"X": mitgcm_grid.x, "Y": mitgcm_grid.y, "T": time_i}
        )
        for i, time_i in enumerate(filtered_parsed_times)
    ]

    return xr.concat(data_interp, dim="T").sortby("T")


def filter_json_files_by_date(all_json_files: list[str], str_start_date: str, str_end_date: str) -> list[str]:
    start_date = datetime.strptime(str_start_date, '%Y%m%d')
    end_date = datetime.strptime(str_end_date, '%Y%m%d')

    def is_within_range(file):
        json_dates = re.findall(r'\d{8}', file)
        start_date_json = datetime.strptime(json_dates[0], '%Y%m%d')
        end_date_json = datetime.strptime(json_dates[1], '%Y%m%d')
        return (start_date_json >= start_date) & (start_date_json <= end_date) & (end_date_json >= start_date)

    return list(filter(is_within_range, all_json_files))


def interp_concat_json(folder_json_path, data_type, str_start_date, str_end_date, mitgcm_grid,
                       weather_model_type=""):
    all_json_files = glob.glob(os.path.join(folder_json_path, f'*_{data_type}.json'))
    json_files = filter_json_files_by_date(all_json_files, str_start_date, str_end_date)

    #if weather_model_type == "forecast":
    #    data_type += "_MEAN"

    all_data = [interp_to_grid(file, data_type, mitgcm_grid, weather_model_type) for file in json_files]

    all_data = xr.concat(all_data, dim='T').sortby('T')

    unique_values, unique_ind = np.unique(all_data['T'].values, return_index=True)
    all_data_cleaned = all_data.isel(T=np.sort(unique_ind))

    parsed_start_date = pd.to_datetime(str_start_date, format="%Y%m%d")
    parsed_end_date = pd.to_datetime(str_end_date, format="%Y%m%d")
    datetime_list = pd.date_range(start=parsed_start_date, end=parsed_end_date, freq="h").to_list()
    interp_data = all_data_cleaned.interp({'T': datetime_list})  # make sure that time is consistent

    return interp_data.transpose('T', 'Y', 'X')


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


def compute_vapor_pressure(atemp, relhum):
    """
    Calculate vapor pressure using the Magnus formula.

    Parameters:
    - temperature (float or numpy array): Air temperature in Kelvin
    - relhum (float or numpy array): Relative humidity as a percentage (e.g., 60 for 60%)

    Returns:
    - vapor_pressure (float or numpy array): Vapor pressure in hPa (hectopascals)
    """
    a = 17.27
    b = 237.7

    rh_fraction = relhum / 100.0
    atemp_celsius = atemp-273.15

    saturation_vapor_pressure = 6.112 * np.exp((a * atemp_celsius) / (atemp_celsius + b))

    return rh_fraction * saturation_vapor_pressure  # vapor pressure in mbar (=hPa)


def compute_longwave_radiation(atemp, relhum, cloud_cover, a = 1.09):
    """
    Compute longwave radiation from air temperature and cloud cover.

    - temp: Air temperature in Kelvin
    - cloud_cover: %
    """
    # cloud cover should be from 0 to 1
    cloud_cover = cloud_cover/100
    vaporPressure = compute_vapor_pressure(atemp, relhum)  # in units mbar
    A_L = 0.03   # Infrared radiation albedo
    #a = 1.03 #1.09     # Calibration parameter

    E_a = a * (1 + 0.17 * np.power(cloud_cover, 2)) * 1.24 * np.power(vaporPressure / atemp, 1./7)  # emissivity

    lwr = (1 - A_L) * 5.67e-8 * E_a * np.power(atemp, 4)
    return lwr


def get_cloud_from_simstrat_input(start_date, end_date, mitgcm_grid):
    simstrat_forcings = pd.read_csv(r"C:\Users\leroquan\Documents\Data\meteo\simstrat forcings\Forcing.dat",
                                    sep='\s+')
    cloud_timeserie = simstrat_forcings[['Time_[d]', 'cloud_[-]']]

    date_ref = datetime(1981, 1, 1)
    cloud_timeserie['time'] = (pd.to_timedelta(cloud_timeserie['Time_[d]'], 'd') + date_ref).dt.round('h')

    parsed_start_date = pd.to_datetime(start_date, format="%Y%m%d")
    parsed_end_date = pd.to_datetime(end_date, format="%Y%m%d")
    datetime_list = pd.date_range(start=parsed_start_date, end=parsed_end_date, freq="h").to_list()

    data_interp = [
        xr.DataArray(
            np.full((len(mitgcm_grid.y), len(mitgcm_grid.x)),
                    cloud_timeserie.loc[cloud_timeserie["time"] == time_i, 'cloud_[-]'].values),
            dims=["Y", "X"],
            coords={"X": mitgcm_grid.x, "Y": mitgcm_grid.y, "T": time_i}
        )
        for i, time_i in enumerate(datetime_list)
    ]

    data = xr.concat(data_interp, dim="T").sortby("T")

    return data.transpose('T', 'Y', 'X')


def extract_and_save_surface_forcings(output_folder_path: str, start_date: str, end_date: str,
                                      path_raw_weather_folder: str, mitgcm_grid: MitgcmGrid,
                                      a_lw: float,
                                      weather_model_type=""):
    """
    Extract surface forcings from json files coming from the Alplakes API and save them as binary files for MITgcm use.

    - output_folder_path: Path to the output folder
    - start_date: Start date of the extraction in format string '%Y%m%d' (ex: "20190301")
    - end_date: Start date of the extraction in format string '%Y%m%d' (ex: "20190301")
    - path_raw_weather_folder: Path to the folder containing the jsons files
    - mitgcm_grid: MitgcmGrid object corresponding to the MITgcm grid. Can be created with class MitgcmGrid() and
    function get_grid(path_folder_grid: str) from grid_and_bathy
    - weather_model_type: current options = 'reanalysis' or 'forecast'
    """

    os.makedirs(output_folder_path, exist_ok=True)

    def process_variable(var_name, output_name):
        print(f'Interpolating {var_name} to grid...')
        data = interp_concat_json(path_raw_weather_folder, var_name, start_date, end_date, mitgcm_grid,
                                  weather_model_type)
        # data = data.fillna(0)  # Handle missing values early
        print(f'Saving {output_name}...')
        write_binary(os.path.join(output_folder_path, f'{output_name}.bin'), data)

        return data

    process_variable('U', 'u10')
    process_variable('V', 'v10')
    swdown = process_variable('GLOB', 'swdown')

    atemp = process_variable('T_2M', 'atemp')
    apress = process_variable('PS', 'apressure')

    print('Computing specific humidity (aqh)...')
    relhum = process_variable('RELHUM_2M', 'relhum')
    aqh = calculate_specific_humidity(atemp, relhum, apress)
    print('Saving aqh...')
    write_binary(os.path.join(output_folder_path, 'aqh.bin'), aqh)

    print('Computing longwave radiation (lwdown)...')

    clct = process_variable('CLCT', 'clct')

    # test to use simstrat clct data instead of cosmo/icon
    #clct = get_cloud_from_simstrat_input(start_date, end_date, mitgcm_grid)
    #write_binary(os.path.join(output_folder_path, f'clct.bin'), clct)

    lwr = compute_longwave_radiation(atemp, relhum, clct, a_lw)
    print('Saving lwdown...')
    write_binary(os.path.join(output_folder_path, 'lwdown.bin'), lwr)

    print('Done computing binary data.')
