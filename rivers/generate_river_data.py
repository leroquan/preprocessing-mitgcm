# https://github.com/leroquan/mitgcm_toolbox/blob/master/PythonScripts/generate_river_data.py

import shutil
import os
import numpy as np
import pandas as pd
import requests
import json
from datetime import datetime
import xarray as xr

from grid_and_bathy import convert_point_coord_to_mitgcm_coord, get_dz_grid
from configs.config_object import ConfigObject
from utils import modify_arguments


def build_river_config(config: ConfigObject, output_dir: str, save_files=True):
    river_dicts = []
    for river_point_config in config.rivers:
            coord_point = river_point_config.coordinates_lake_point
            x_coord, y_coord = convert_point_coord_to_mitgcm_coord(coord_point[0], coord_point[1], "2056", config)
            x_idx = int(x_coord / config.grid_resolution)
            y_idx = int(y_coord / config.grid_resolution)

            boundary_direction = river_point_config.direction

            river_dicts.append({
                "name": river_point_config.name,
                "bafu_id": river_point_config.bafu_id,
                "discharge_variable_name": river_point_config.discharge_variable_name,
                "temperature_variable_name": river_point_config.temperature_variable_name,
                "x_idx": x_idx,
                "y_idx": y_idx,
                "boundary_direction": boundary_direction,
                "in_or_out": river_point_config.in_or_out,
                "depth": river_point_config.river_depth
            })

    obs_indices_string = ''
    obs_path_string = ''
    for boundary_direction in ['north', 'south', 'east', 'west']:
        for dict in river_dicts:
            if boundary_direction == dict["boundary_direction"]:
                if boundary_direction == 'north':
                    obs_indices_string += f' OB_Jnorth({dict["x_idx"]+1}) = {dict["y_idx"]+1}\n'
                    obs_path_string += f"OBNvFile = '../binary_data/bc_north_v.bin'\n"
                elif boundary_direction == 'south':
                    obs_indices_string += f' OB_Jsouth({dict["x_idx"]+1}) = {dict["y_idx"]+1}\n'
                    obs_path_string += f"OBSvFile = '../binary_data/bc_south_v.bin'\n"
                elif boundary_direction == 'east':
                    obs_indices_string += f' OB_Ieast({dict["y_idx"]+1}) = {dict["x_idx"]+1}\n'
                    obs_path_string += f"OBEuFile = '../binary_data/bc_east_u.bin'\n"
                elif boundary_direction == 'west':
                    obs_indices_string += f' OB_Iwest({dict["y_idx"]+1}) = {dict["x_idx"]+1}\n'
                    obs_path_string += f"OBWuFile = '../binary_data/bc_west_u.bin'\n"

                if dict["in_or_out"] == 'in':
                    obs_path_string += f"OB{str.capitalize(boundary_direction[0])}TFile = '../binary_data/bc_{boundary_direction}_temp.bin'\n"

    if save_files:
        obcs_path = os.path.join(output_dir, 'data.obcs')
        modify_arguments('!set_obs_indices!', obs_indices_string[:-1], obcs_path)
        modify_arguments('!set_obs_path!', obs_path_string[:-1], obcs_path)

        river_dicts_path = os.path.join(output_dir, "river_dicts.json")
        with open(river_dicts_path, "w") as f:
            json.dump(river_dicts, f, indent=2)

    return river_dicts, obs_indices_string


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


def get_formatted_velocities(config, river_config,
                             date_list, z_grid, idx_max_z_river):
    url_discharge = (f"https://alplakes-internal-api.eawag.ch/bafu/hydrodata/measured/{river_config['bafu_id']}/"
           f"{river_config['discharge_variable_name']}/"
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


def get_formatted_temperature(config, river_config, date_list):
    url_temperature = (f"https://alplakes-internal-api.eawag.ch/bafu/hydrodata/measured/{river_config['bafu_id']}/"
       f"{river_config['temperature_variable_name']}/"
       f"{config.start_date}/"
       f"{config.end_date}/"
       "?resample=hourly"
       )
    response = try_download(url_temperature)
    json_temperature = response.json()
    temperature_data = parse_river_json(json_temperature)

    formatted_temperature = temperature_data.interp(time=date_list, method='linear')

    return formatted_temperature.data.values


def get_boundary_direction_factor(direction, in_or_out):
    factor = 1
    if direction == 'south' and in_or_out == 'out' :
        factor = -1
    if direction == 'north' and in_or_out == 'in' :
        factor = -1
    if direction == 'west' and in_or_out == 'out' :
        factor = -1
    if direction == 'east' and in_or_out == 'in' :
        factor = -1

    return factor


def define_direction_specific_variables(config, direction):
    velocity_variable = ''
    idx_var = ''
    boundary_length = 0
    if direction == 'south' or direction == 'north':
        velocity_variable = 'v'
        idx_var = 'x_idx'
        boundary_length = config.Nx
    if direction == 'west' or direction == 'east':
        velocity_variable = 'u'
        idx_var = 'y_idx'
        boundary_length = config.Ny

    return (velocity_variable, idx_var, boundary_length)


def write_river_binaries(binary_data_folder, boundary_direction, vel_var,
                         date_list, dz_grid, boundary_length, boundary_dicts):
    vel_file = open(f'{binary_data_folder}/bc_{boundary_direction}_{vel_var}.bin', 'ab')
    temperature_file = open(f'{binary_data_folder}/bc_{boundary_direction}_temp.bin', 'ab')

    for i_time, date in enumerate(date_list):
        velocities_bc = np.zeros((len(dz_grid), boundary_length), dtype='>f8')
        temperatures_bc = np.zeros((len(dz_grid), boundary_length), dtype='>f8')
        for dict in boundary_dicts:
            vel = dict['velocity'][i_time]
            temp = dict['temperature'][i_time]

            velocities_bc[0:(dict["max_z_idx"]+1), dict['horizontal_idx']] = vel
            temperatures_bc[0:(dict["max_z_idx"]+1), dict['horizontal_idx']] = temp

        velocities_bc.tofile(vel_file)
        temperatures_bc.tofile(temperature_file)

    vel_file.close()
    temperature_file.close()


def build_river_binaries(config, output_dir):
    river_config_path = os.path.join(config.paths.grid_folder_path, 'river_dicts.json')
    river_config = pd.read_json(river_config_path)
    date_list = pd.date_range(config.start_date, config.end_date, freq="1h")

    dz_grid = get_dz_grid(os.path.join(config.paths.grid_folder_path, 'dz.csv')).flatten()
    z_grid = np.cumsum(dz_grid)

    for boundary_direction in ['north', 'south', 'east', 'west']:
        (velocity_variable, idx_var, boundary_length) = define_direction_specific_variables(config, boundary_direction)

        boundary_dicts = []
        discharge_exist=False
        for idx, river in river_config.iterrows():
            if river['boundary_direction'] == boundary_direction:
                discharge_exist=True
                idx_max_z_river = np.abs(z_grid - river["depth"]).argmin()

                vel = get_formatted_velocities(config, river, date_list, z_grid, idx_max_z_river)
                vel_factor = get_boundary_direction_factor(boundary_direction, river['in_or_out'])

                temp = get_formatted_temperature(config, river, date_list)

                boundary_dicts.append({"horizontal_idx": river[idx_var],
                                      "max_z_idx": idx_max_z_river,
                                      "velocity": vel_factor * np.array(vel),
                                      "temperature": temp
                                      })
        if discharge_exist:
            write_river_binaries(output_dir, boundary_direction, velocity_variable,
                                date_list, dz_grid, boundary_length, boundary_dicts)