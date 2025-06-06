import os

import numpy as np
import pandas as pd
from pyproj import Transformer


class MitgcmGrid:
    """Class representing an MITgcm grid, with optional loading from .npy files."""

    def __init__(self):
        """Initialize an empty MITgcm grid."""
        self.x = np.array([])
        self.y = np.array([])
        self.lat_grid = np.array([])
        self.lon_grid = np.array([])

    def load_from_path(self, path_grid: str):
        """
        Load grid data from a given folder containing .npy files.

        Args:
            path_grid (str): Path to the folder containing the grid files.

        Raises:
            FileNotFoundError: If any required grid file is missing.
            RuntimeError: If loading fails due to other errors.
        """
        try:
            self.x = np.load(os.path.join(path_grid, 'x.npy'))
            self.y = np.load(os.path.join(path_grid, 'y.npy'))
            self.lat_grid = np.load(os.path.join(path_grid, 'lat_grid.npy'))
            self.lon_grid = np.load(os.path.join(path_grid, 'lon_grid.npy'))
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Missing grid file: {e.filename}") from e
        except Exception as e:
            raise RuntimeError(f"Error loading grid data: {e}") from e


def get_grid(path_folder_grid: str) -> MitgcmGrid:
    mitgcm_grid = MitgcmGrid()
    mitgcm_grid.load_from_path(path_folder_grid)

    return mitgcm_grid


def create_regular_grid(nx: int, ny: int, x_resolution: int, y_resolution: int) \
        -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    # XY on mitgcm grid
    x = np.arange(0, nx * x_resolution, x_resolution)
    y = np.arange(0, ny * y_resolution, y_resolution)
    xgrid, ygrid = (np.meshgrid(x, y))

    return x, y, xgrid, ygrid


def translate_grid(x: np.ndarray, y: np.ndarray, dx: float, dy: float) -> (np.ndarray, np.ndarray):
    trans_x = x + dx
    trans_y = y + dy

    return trans_x, trans_y


def get_grid_angle(x0: float, y0: float, x1: float, y1: float) -> float:
    grid_angle = np.arctan2(y1 - y0, x1 - x0)

    return grid_angle


def rotate_grid(x: np.ndarray, y: np.ndarray, x0: float, y0: float, rotation_angle: float) -> (np.ndarray, np.ndarray):
    x_translated_to_zero, y_translated_to_zero = translate_grid(x, y, -x0, -y0)

    x_rotated = np.cos(rotation_angle) * x_translated_to_zero - np.sin(rotation_angle) * y_translated_to_zero
    y_rotated = np.sin(rotation_angle) * x_translated_to_zero + np.cos(rotation_angle) * y_translated_to_zero

    x_translated_back, y_translated_back = translate_grid(x_rotated, y_rotated, x0, y0)

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


def build_grid(nx: int, ny: int, x_resolution: int, y_resolution: int,
               x0_sg: float, y0_sg: float, x1_sg: float, y1_sg: float) \
        -> (np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray):
    x, y, xgrid, ygrid = create_regular_grid(nx, ny, x_resolution, y_resolution)
    xsg, ysg = translate_grid(x, y, x0_sg, y0_sg)
    xsg_grid, ysg_grid = np.meshgrid(xsg, ysg)

    rotation_angle = get_grid_angle(x0_sg, y0_sg, x1_sg, y1_sg)
    x_rotated, y_rotated = rotate_grid(xsg_grid, ysg_grid, x0_sg, y0_sg, rotation_angle)

    coord_converter = Transformer.from_crs("EPSG:21781", "EPSG:4326", always_xy=True)
    lon_grid, lat_grid = coord_converter.transform(x_rotated, y_rotated)

    return x, y, x_rotated, y_rotated, lat_grid, lon_grid


def build_and_save_mitgcm_grid(folder_path_out: str, nx: int, ny: int, grid_resolution: int, x0_sg: float, y0_sg: float,
                               x1_sg: float, y1_sg: float):
    x, y, x_rotated, y_rotated, lat_grid, lon_grid = build_grid(nx, ny, grid_resolution, grid_resolution,
                                                                x0_sg, y0_sg, x1_sg, y1_sg)
    save_grid(folder_path_out, x, y, x_rotated, y_rotated, lat_grid, lon_grid)


def get_dz_grid(dz_grid_file_path: str) -> np.array:
    dz_grid = pd.read_csv(dz_grid_file_path, header=None).to_numpy()

    return dz_grid
