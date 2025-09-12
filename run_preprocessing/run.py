import numpy as np
import shutil
import os

from utils import modify_arguments
from configs import config_object


def remove_all_files_and_folders(directory):
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        if os.path.isdir(item_path):
            shutil.rmtree(item_path)  # Remove the directory and its contents
        else:
            os.remove(item_path)  # Remove the file



def copy_template(template_folder, output_folder):

    # Iterate through the source directory
    for item in os.listdir(template_folder):
        s = os.path.join(template_folder, item)
        d = os.path.join(output_folder, item)
        if os.path.isdir(s):
            # Copy directory and its contents
            shutil.copytree(s, d, dirs_exist_ok=True)  # dirs_exist_ok allows overwriting if subdirectories exist
        else:
            # Copy file
            shutil.copy2(s, d)


def write_data_config_files(data_config_path: str, initial_temperature: np.ndarray, initial_salt: np.ndarray,
                            start_time_in_second: int, end_time_in_second: int, pickup_number: str,
                            dz_grid: np.ndarray, grid_resolution: int, time_step: int):
    modify_arguments('!initial_temperature!', initial_temperature, data_config_path)
    modify_arguments('!initial_salt!', initial_salt, data_config_path)
    modify_arguments('!start_time!', start_time_in_second, data_config_path)
    modify_arguments('!end_time!', end_time_in_second, data_config_path)
    modify_arguments('!pickup_number!', pickup_number, data_config_path)
    modify_arguments('!grid_resolution!', grid_resolution, data_config_path)
    modify_arguments('!time_step!', time_step, data_config_path)
    modify_arguments('!dz_grid!', dz_grid, data_config_path)


def write_size_config_files(size_config_path: str, Px: int, Py: int, Nx: int, Ny: int, Nr: int, sNx: int, sNy: int):
    modify_arguments('!Px!', Px, size_config_path)
    modify_arguments('!Py!', Py, size_config_path)
    modify_arguments('!Nx!', Nx, size_config_path)
    modify_arguments('!Ny!', Ny, size_config_path)
    modify_arguments('!Nr!', Nr, size_config_path)
    modify_arguments('!sNx!', sNx, size_config_path)
    modify_arguments('!sNy!', sNy, size_config_path)


def write_secchi(swfrac_path, secchi_depths):
    depths = "_RL secchiDepths({})".format(len(secchi_depths))
    secchi = "DATA secchiDepths / {} _d 0".format(secchi_depths[0])
    for i in range(1, len(secchi_depths)):
        secchi = secchi + ",\n     &                    {} _d 0".format(secchi_depths[i])
    secchi = secchi + " /"

    modify_arguments('!depths!', depths, swfrac_path)
    modify_arguments('!secchi!', secchi, swfrac_path)

