import os

import numpy as np
import pandas as pd
from pyproj import Transformer


def create_regular_grid(Nx: int, Ny: int, grid_resolution: int) -> (np.ndarray, np.ndarray, np.ndarray, np.ndarray):
    # XY on mitgcm grid
    x = np.arange(0, Nx * grid_resolution, grid_resolution)
    y = np.arange(0, Ny * grid_resolution, grid_resolution)
    xgrid, ygrid = (np.meshgrid(x, y))

    return x, y, xgrid, ygrid


def place_grid_on_swiss_grid(x: np.array(float), y: np.array(float), XO_SG: float, YO_SG: float) \
        -> (np.ndarray, np.ndarray):
    # XY on swiss grid
    x_sg = x + XO_SG
    y_sg = y + YO_SG
    xsg_grid, ysg_grid = np.meshgrid(x_sg, y_sg)

    return xsg_grid, ysg_grid


def translate_grid_to_origin(x: np.ndarray, y: np.ndarray, dx: float, dy: float) -> (np.ndarray, np.ndarray):
    trans_x = x + dx
    trans_y = y + dy

    return trans_x, trans_y


def get_grid_angle(x0: float, y0: float, x1: float, y1: float) -> float:
    grid_angle = np.arctan2(y1 - y0, x1 - x0)

    return grid_angle


def rotate_grid(x: np.ndarray, y: np.ndarray, x0: float, y0: float, rotation_angle: float) -> (np.ndarray, np.ndarray):
    x_translated_to_zero, y_translated_to_zero = translate_grid_to_origin(x, y, -x0, -y0)

    x_rotated = np.cos(rotation_angle) * x_translated_to_zero - np.sin(rotation_angle) * y_translated_to_zero
    y_rotated = np.sin(rotation_angle) * x_translated_to_zero + np.cos(rotation_angle) * y_translated_to_zero

    x_translated_back, y_translated_back = translate_grid_to_origin(x_rotated, y_rotated, x0, y0)

    return x_translated_back, y_translated_back


def save_grid(folder_path_out: str, x: np.array(float), y: np.array(float), x_rotated: np.array(float),
              y_rotated: np.array(float), lat_grid: np.array(float), lon_grid: np.array(float)):
    if not os.path.exists(folder_path_out):
        os.makedirs(folder_path_out)
        print(f"Directory '{folder_path_out}' created.")

    with open(os.path.join(folder_path_out, 'x.npy'), 'wb') as f:
        np.save(f, x)
    with open(os.path.join(folder_path_out, 'y.npy'), 'wb') as f:
        np.save(f, y)
    with open(os.path.join(folder_path_out, 'x_sg_grid.npy'), 'wb') as f:
        np.save(f, x_rotated)
    with open(os.path.join(folder_path_out, 'y_sg_grid.npy'), 'wb') as f:
        np.save(f, y_rotated)
    with open(os.path.join(folder_path_out, 'lat_grid.npy'), 'wb') as f:
        np.save(f, lat_grid)
    with open(os.path.join(folder_path_out, 'lon_grid.npy'), 'wb') as f:
        np.save(f, lon_grid)


def build_and_save_mitgcm_grid(folder_path_out: str, Nx: int, Ny: int, grid_resolution: int, XO_SG: float, YO_SG: float,
                               X1_SG: float, Y1_SG: float):
    x, y, xgrid, ygrid = create_regular_grid(Nx, Ny, grid_resolution)
    xsg_grid, ysg_grid = place_grid_on_swiss_grid(x, y, XO_SG, YO_SG)

    rotation_angle = get_grid_angle(XO_SG, YO_SG, X1_SG, Y1_SG)
    x_rotated, y_rotated = rotate_grid(xsg_grid, ysg_grid, XO_SG, YO_SG, rotation_angle)

    coord_converter = Transformer.from_crs("EPSG:21781", "EPSG:4326", always_xy=True)
    lon_grid, lat_grid = coord_converter.transform(x_rotated, y_rotated)

    save_grid(folder_path_out, x, y, x_rotated, y_rotated, lat_grid, lon_grid)


def get_dz_grid(dz_grid_file_path: str) -> np.array:
    dz_grid = pd.read_csv(dz_grid_file_path, header=None).to_numpy()

    return dz_grid
