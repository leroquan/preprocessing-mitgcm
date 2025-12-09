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

    river_angle = river_point_config.angle_from_north_direction[0] + config.rotation
    u_flow = formatted_discharge.data.values * np.sin(np.deg2rad(river_angle))
    v_flow = formatted_discharge.data.values * np.cos(np.deg2rad(river_angle))


    depth_profile = np.insert(z_grid[0:(idx_max_z_river+1)], 0, 0)

    uvel_profile = []
    vvel_profile = []
    for i_time, date in enumerate(date_list):
        uvel_profile.append(vectorFlow(u_flow[i_time], depth_profile) / config.grid_resolution)
        vvel_profile.append(vectorFlow(v_flow[i_time], depth_profile) / config.grid_resolution)

    return uvel_profile, vvel_profile


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


def get_boundary_directions(river_point_config, u_mean, v_mean):
    boundary_directions = []
    if river_point_config.in_or_out == 'in':
        if u_mean < 0:
            boundary_directions.append('east')
        elif u_mean > 0:
            boundary_directions.append('west')
        if v_mean < 0:
            boundary_directions.append('north')
        elif v_mean > 0:
            boundary_directions.append('south')
    elif river_point_config.in_or_out == 'out':
        if u_mean < 0:
            boundary_directions.append('west')
        elif u_mean > 0:
            boundary_directions.append('east')
        if v_mean < 0:
            boundary_directions.append('south')
        elif v_mean > 0:
            boundary_directions.append('north')
    else:
        raise ValueError('river_point_config.in_or_out must be "in" or "out"')

    return boundary_directions


def build_river_dict(river_dicts, config, river_point_config, z_grid, date_list):
    coord_point = river_point_config.coordinates_lake_point[0]
    x_coord, y_coord = convert_point_coord_to_mitgcm_coord(coord_point[0], coord_point[1], "2056", config)
    x_idx = int(x_coord / config.grid_resolution)+1
    y_idx = int(y_coord / config.grid_resolution)+1

    idx_max_z_river = np.abs(z_grid - river_point_config.river_depth).argmin()

    uvel, vvel = get_formatted_velocities(config, river_point_config, date_list, z_grid, idx_max_z_river)
    temp = get_formatted_temperature(config, river_point_config, date_list)

    river_dicts.append({
        "name": river_point_config.name,
        "x_idx": x_idx,
        "y_idx": y_idx,
        "max_z_idx": idx_max_z_river,
        "boundary_directions": get_boundary_directions(river_point_config, np.mean(uvel), np.mean(vvel)),
        "u_velocity": uvel,
        "v_velocity": vvel,
        "temperature": temp
    })

    return river_dicts


def define_direction_specific_variables(boundary_direction, config):
    boundary_length = 0
    vel_var = ''
    idx_var = ''
    prefix = ''
    idx_ortho=''
    if boundary_direction == 'north' or boundary_direction == 'south':
        boundary_length = config.Nx
        vel_var = 'v'
        idx_var = 'x_idx'
        prefix = 'J'
        idx_ortho = 'y_idx'
    elif boundary_direction == 'east' or boundary_direction == 'west':
        boundary_length = config.Ny
        vel_var = 'u'
        idx_var = 'y_idx'
        prefix = 'I'
        idx_ortho = 'x_idx'

    return boundary_length, vel_var, idx_var, prefix, idx_ortho


def write_river_binaries(binary_data_folder, boundary_direction, vel_var,
                         date_list, dz_grid, boundary_length, river_dicts, idx_var):
    vel_file = open(f'{binary_data_folder}/bc_{boundary_direction}_{vel_var}.bin', 'ab')
    temperature_file = open(f'{binary_data_folder}/bc_{boundary_direction}_temp.bin', 'ab')

    for i_time, date in enumerate(date_list):
        velocities_bc = np.zeros((len(dz_grid), boundary_length))
        temperatures_bc = np.zeros((len(dz_grid), boundary_length))
        for dict in river_dicts:
            if boundary_direction in dict["boundary_directions"]:
                vel = dict[f"{vel_var}_velocity"][i_time]
                temp = dict['temperature'][i_time]

                velocities_bc[0:(dict["max_z_idx"]+1), dict[idx_var]] = vel
                temperatures_bc[0:(dict["max_z_idx"]+1), dict[idx_var]] = temp

        velocities_bc.tofile(vel_file)
        temperatures_bc.tofile(temperature_file)

    vel_file.close()
    temperature_file.close()


def build_river_files(config: ConfigObject, output_folder: str):
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
         idx_var, prefix, idx_ortho) = define_direction_specific_variables(boundary_direction, config)

        discharge_exist=False
        for dict in river_dicts:
            if boundary_direction in dict["boundary_directions"]:
                discharge_exist=True
                obs_indices_string += f' OB_{prefix}{boundary_direction}({dict[idx_var]}) = {dict[idx_ortho]}\n'
                obs_path_string += f"OB{str.capitalize(boundary_direction[0])}{vel_var}File = '../binary_data/bc_{boundary_direction}_{vel_var}.bin'\n"
                obs_path_string += f"OB{str.capitalize(boundary_direction[0])}TFile = '../binary_data/bc_{boundary_direction}_T.bin'\n"

        if discharge_exist:
            write_river_binaries(binary_data_folder, boundary_direction, vel_var,
                         date_list, dz_grid, boundary_length, river_dicts, idx_var)

    modify_arguments('!set_obs_indices!', obs_indices_string[:-1], obcs_file_path)
    modify_arguments('!set_obs_path!', obs_path_string[:-1], obcs_file_path)

    return river_dicts, obs_indices_string
