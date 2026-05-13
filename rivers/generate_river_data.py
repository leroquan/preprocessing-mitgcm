# https://github.com/leroquan/mitgcm_toolbox/blob/master/PythonScripts/generate_river_data.py

import glob, os
import numpy as np
import pandas as pd
import requests
import json
from datetime import datetime
import xarray as xr

from grid_and_bathy import convert_point_coord_to_mitgcm_coord, get_dz_grid
from configs.config_object import ConfigObject
from utils import modify_arguments

def cellFlow(maxH, h1, h2, totalFlow):
    '''
    Flow through a particular cell based on the logarithmic law of turbulent
    boundary layers, as per `Modelling Aquatic Ecosystems` by Reichert,
    Mieleitner and Schuwirth.
    '''

    kappa = 0.4
    S_0 = 0.01
    u_star = np.sqrt(9.8*maxH*S_0)

    if h1 > 0:
        return (totalFlow*(h2/maxH) + (u_star/kappa)*h2*np.log(h2/maxH) -
                totalFlow*(h1/maxH) - (u_star/kappa)*h1*np.log(h1/maxH))
    else:
        return totalFlow*(h2/maxH) + (u_star/kappa)*h2*np.log(h2/maxH)


def vectorFlow(totalFlow, h):
    '''
    Computes the entire flow profile with the zeroth cell corresponding to the
    top layer.
    '''

    n = len(h) - 1
    flows = np.zeros(n)
    for i in range(n):
        flows[n-i-1] = cellFlow(h[n], h[i], h[i+1], totalFlow) / (h[i+1]-h[i])
    return flows


def parse_river_data_from_folder(folder_path):
    json_files = glob.glob(os.path.join(folder_path, f'*.json'))

    # Initialize lists to store combined data
    all_times = []
    all_values = []

    # Loop through each JSON file
    for file_path in json_files:
        # Read the JSON file
        with open(file_path, 'r') as file:
            data = json.load(file)

        # Extract time data and convert to datetime
        times = [datetime.fromisoformat(t.replace('Z', '+00:00')) for t in data['time']]

        # Extract depth and temperature data
        values = np.array(data['variable']['data'])

        # Append to the combined lists
        all_times.append(times)
        all_values.append(values)


    # Combine all time and temperature data
    all_times = np.concatenate(all_times)
    all_times = np.array([dt.replace(tzinfo=None) for dt in all_times])
    all_values = np.hstack(all_values)

    # Create xarray dataset
    river_data = xr.Dataset(
        {
            'data': (['time'], np.stack(all_values))
        },
        coords={
            'time': all_times,
        }
    )

    unique_values, unique_ind = np.unique(river_data['time'].values, return_index=True)

    return river_data.isel(time=np.sort(unique_ind))


def parse_river_json(json_data):

    # Extract time data and convert to datetime
    times = [datetime.fromisoformat(t.replace('Z', '+00:00')).replace(tzinfo=None) for t in json_data['time']]

    # Extract depth and temperature data
    values = np.array(json_data['variable']['data'])

    # Create xarray dataset
    river_data = xr.Dataset(
        {
            'data': (['time'], np.stack(values))
        },
        coords={
            'time': times,
        }
    )

    return river_data


def try_download(url):
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(r"Didn't work, response.status_code = " + str(response.status_code) + ", url = " + url)

    return response


def get_formatted_velocities(config, river_point_config, date_list, z_grid, idx_max_z_river):
    url_discharge = (f"https://alplakes-internal-api.eawag.ch/bafu/hydrodata/measured/{river_point_config.bafu_id}/"
           f"{river_point_config.discharge_variable_name}/"
           f"{config.start_date}/"
           f"{config.end_date}/"
           "?resample=hourly"
           )
    response = try_download(url_discharge)
    json_discharge = response.json()
    discharge_data = parse_river_json(json_discharge)

    formatted_discharge = discharge_data.interp(time=date_list, method='linear')
    depth_profile = np.insert(z_grid[0:(idx_max_z_river+1)], 0, 0)

    vel_profile = []
    for i_time, date in enumerate(date_list):
        vel_profile.append(vectorFlow(formatted_discharge.isel(time = i_time).data.values, depth_profile) / config.grid_resolution)

    return vel_profile


def get_formatted_temperature(config, river_point_config, date_list):
    url_temperature = (f"https://alplakes-internal-api.eawag.ch/bafu/hydrodata/measured/{river_point_config.bafu_id}/"
       f"{river_point_config.temperature_variable_name}/"
       f"{config.start_date}/"
       f"{config.end_date}/"
       "?resample=hourly"
       )
    response = try_download(url_temperature)
    json_temperature = response.json()
    temperature_data = parse_river_json(json_temperature)

    formatted_temperature = temperature_data.interp(time=date_list, method='linear')

    return formatted_temperature.data.values


def get_boundary_direction_factor(river_point_config):
    if not (river_point_config.direction in ['north', 'south', 'east', 'west']
            and river_point_config.in_or_out in ['in', 'out']) :
        raise ValueError(
            f"River direction should be 'north', 'south', 'east' or 'west' (entered {river_point_config.direction}). \n"
            f"In_or_out should be 'in' or 'out' (entered {river_point_config.in_or_out})."
        )

    factor = 1
    if river_point_config.direction == 'south' and river_point_config.in_or_out == 'out' :
        factor = -1
    if river_point_config.direction == 'north' and river_point_config.in_or_out == 'in' :
        factor = -1
    if river_point_config.direction == 'west' and river_point_config.in_or_out == 'out' :
        factor = -1
    if river_point_config.direction == 'east' and river_point_config.in_or_out == 'in' :
        factor = -1

    return factor


def build_river_dict(river_dicts, config, river_point_config, z_grid, date_list):
    coord_point = river_point_config.coordinates_lake_point
    x_coord, y_coord = convert_point_coord_to_mitgcm_coord(coord_point[0], coord_point[1], "2056", config)
    x_idx = int(x_coord / config.grid_resolution)
    y_idx = int(y_coord / config.grid_resolution)

    idx_max_z_river = np.abs(z_grid - river_point_config.river_depth).argmin()

    vel = get_formatted_velocities(config, river_point_config, date_list, z_grid, idx_max_z_river)
    direction_factor = get_boundary_direction_factor(river_point_config)
    temperature = None
    if river_point_config.in_or_out == 'in':
        temperature = get_formatted_temperature(config, river_point_config, date_list)

    river_dicts.append({
        "name": river_point_config.name,
        "x_idx": x_idx,
        "y_idx": y_idx,
        "max_z_idx": idx_max_z_river,
        "boundary_direction": river_point_config.direction,
        "in_or_out": river_point_config.in_or_out,
        "velocity": direction_factor * np.array(vel),
        "temperature": temperature
    })

    return river_dicts


def define_direction_specific_variables(boundary_direction, config):
    boundary_length = 0
    vel_var = ''
    idx_var = ''
    prefix = ''
    idx_ortho=''
    prefix_ortho=''
    if boundary_direction == 'north' or boundary_direction == 'south':
        boundary_length = config.Nx
        vel_var = 'v'
        idx_var = 'x_idx'
        prefix = 'J'
        prefix_ortho='I'
        idx_ortho = 'y_idx'
    elif boundary_direction == 'east' or boundary_direction == 'west':
        boundary_length = config.Ny
        vel_var = 'u'
        idx_var = 'y_idx'
        prefix = 'I'
        prefix_ortho='J'
        idx_ortho = 'x_idx'

    return boundary_length, vel_var, idx_var, prefix, prefix_ortho, idx_ortho


def write_discharge_binaries(binary_data_folder, boundary_direction, vel_var,
                         date_list, dz_grid, boundary_length, river_dicts, idx_var):
    vel_file = open(f'{binary_data_folder}/bc_{boundary_direction}_{vel_var}.bin', 'ab')
    for i_time, date in enumerate(date_list):
        velocities_bc = np.zeros((len(dz_grid), boundary_length), dtype='>f8')
        for dict in river_dicts:
            if boundary_direction == dict["boundary_direction"]:
                vel = np.asarray(dict['velocity'][i_time], dtype='>f8')
                velocities_bc[0:(dict["max_z_idx"]+1), dict[idx_var]] = vel

        velocities_bc.tofile(vel_file)
    vel_file.close()


def write_temperature_binaries(binary_data_folder, boundary_direction,
                         date_list, dz_grid, boundary_length, river_dicts, idx_var):
    temperature_file = open(f'{binary_data_folder}/bc_{boundary_direction}_temp.bin', 'ab')
    for i_time, date in enumerate(date_list):
        temperatures_bc = np.zeros((len(dz_grid), boundary_length), dtype='>f8')
        for dict in river_dicts:
            if boundary_direction == dict["boundary_direction"] and dict['temperature'] is not None:
                temp = np.asarray(dict['temperature'][i_time], dtype='>f8')
                temperatures_bc[0:(dict["max_z_idx"]+1), dict[idx_var]] = temp
        temperatures_bc.tofile(temperature_file)
    temperature_file.close()


def build_river_files(config: ConfigObject, output_folder: str, save_files=True):
    binary_data_folder = os.path.join(output_folder, 'binary_data')
    obcs_file_path = os.path.join(output_folder, 'run_config', 'data.obcs')
    date_list = pd.date_range(config.start_date, config.end_date, freq="1h")

    dz_grid = get_dz_grid(os.path.join(config.paths.grid_folder_path, 'dz.csv')).flatten()
    z_grid = np.cumsum(dz_grid)

    river_dicts = []
    for river_point_config in config.rivers:
        river_dicts = build_river_dict(river_dicts, config, river_point_config, z_grid, date_list)

    obs_indices_string = ''
    obs_path_string = ''
    for boundary_direction in ['north', 'south', 'east', 'west']:
        (boundary_length, vel_var,
         idx_var, prefix, prefix_ortho, idx_ortho) = define_direction_specific_variables(boundary_direction, config)

        discharge_exist=False
        temperature_exist=False
        for dict in river_dicts:
            if boundary_direction == dict["boundary_direction"]:
                discharge_exist=True
                obs_indices_string += f' OB_{prefix}{boundary_direction}({dict[idx_var]+1}) = {dict[idx_ortho]+1}\n'
                #obs_indices_string += f' OB_{prefix_ortho}{dict["blocked_direction"]}({dict[idx_ortho]+1}) = {dict[idx_var]+1}\n'
                obs_path_string += f"OB{str.capitalize(boundary_direction[0])}{vel_var}File = '../binary_data/bc_{boundary_direction}_{vel_var}.bin'\n"
                if dict['temperature'] is not None:
                    temperature_exist=True
                    obs_path_string += f"OB{str.capitalize(boundary_direction[0])}TFile = '../binary_data/bc_{boundary_direction}_temp.bin'\n"

        if discharge_exist and save_files:
            write_discharge_binaries(binary_data_folder, boundary_direction, vel_var,
                         date_list, dz_grid, boundary_length, river_dicts, idx_var)
        if temperature_exist and save_files:
            write_temperature_binaries(binary_data_folder, boundary_direction,
                         date_list, dz_grid, boundary_length, river_dicts, idx_var)

    if save_files:
        modify_arguments('!set_obs_indices!', obs_indices_string[:-1], obcs_file_path)
        modify_arguments('!set_obs_path!', obs_path_string[:-1], obcs_file_path)

    return river_dicts, obs_indices_string
