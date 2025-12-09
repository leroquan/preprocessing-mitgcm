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
    """Compute the angle (in radians) between the positive x-axis and the
    line segment from point (x0, y0) to point (x1, y1)."""
    grid_angle = np.arctan2(y1 - y0, x1 - x0)

    return grid_angle


def rotate_grid(x: np.ndarray, y: np.ndarray, x0: float, y0: float, rotation_angle: float) -> (np.ndarray, np.ndarray):
    x_translated_to_zero, y_translated_to_zero = translate_grid(x, y, -x0, -y0)

    x_rotated = np.cos(rotation_angle) * x_translated_to_zero - np.sin(rotation_angle) * y_translated_to_zero
    y_rotated = np.sin(rotation_angle) * x_translated_to_zero + np.cos(rotation_angle) * y_translated_to_zero

    x_translated_back, y_translated_back = translate_grid(x_rotated, y_rotated, x0, y0)

    return x_translated_back, y_translated_back


def save_grid(folder_path_out: str, x: np.array(float), y: np.array(float), x_rotated: np.array(float),
              y_rotated: np.array(float), lat_grid: np.array(float), lon_grid: np.array(float), crs_ini: str = "21781"):
    if not os.path.exists(folder_path_out):
        os.makedirs(folder_path_out)
        print(f"Directory '{folder_path_out}' created.")

    with open(os.path.join(folder_path_out, 'x.npy'), 'wb') as f:
        np.save(f, x)
    with open(os.path.join(folder_path_out, 'y.npy'), 'wb') as f:
        np.save(f, y)
    with open(os.path.join(folder_path_out, f'x_epsg{crs_ini}_grid.npy'), 'wb') as f:
        np.save(f, x_rotated)
    with open(os.path.join(folder_path_out, f'y_epsg{crs_ini}_grid.npy'), 'wb') as f:
        np.save(f, y_rotated)
    with open(os.path.join(folder_path_out, 'lat_grid.npy'), 'wb') as f:
        np.save(f, lat_grid)
    with open(os.path.join(folder_path_out, 'lon_grid.npy'), 'wb') as f:
        np.save(f, lon_grid)


def build_grid(nx: int, ny: int, resolution_x: int, resolution_y: int,
               x0: float, y0: float, rotation_angle,
               crs_ini: str = "21781", crs_target: str = "4326"):
    """
    return x, y, x_rotated, y_rotated, lat_grid, lon_grid
    """
    x, y, xgrid, ygrid = create_regular_grid(nx, ny, resolution_x, resolution_y)
    x_crs_ini, y_crs_ini = translate_grid(x, y, x0, y0)
    x_grid, y_grid = np.meshgrid(x_crs_ini, y_crs_ini)

    x_rotated, y_rotated = rotate_grid(x_grid, y_grid, x0, y0, rotation_angle)

    coord_converter = Transformer.from_crs(f"EPSG:{crs_ini}", f"EPSG:{crs_target}", always_xy=True)
    lon_grid, lat_grid = coord_converter.transform(x_rotated, y_rotated)

    return x, y, x_rotated, y_rotated, lat_grid, lon_grid


def build_and_save_mitgcm_grid(folder_path_out: str, nx: int, ny: int, grid_resolution: int, x0: float, y0: float,
                               x1: float, y1: float, crs_ini: str = "21781", crs_target: str = "4326"):
    x, y, x_rotated, y_rotated, lat_grid, lon_grid = build_grid(nx, ny, grid_resolution, grid_resolution,
                                                                x0, y0, x1, y1, crs_ini, crs_target)
    save_grid(folder_path_out, x, y, x_rotated, y_rotated, lat_grid, lon_grid)


def get_dz_grid(dz_grid_file_path: str) -> np.array:
    dz_grid = pd.read_csv(dz_grid_file_path, header=None).to_numpy()

    return dz_grid

from configs.config_object import ConfigObject
def convert_point_coord_to_mitgcm_coord(x_point, y_point, point_epsg_projection, config: ConfigObject):
    crs_target = '2056'
    config_coord_converter = Transformer.from_crs(f"EPSG:{config.epsg_projection}", f"EPSG:{crs_target}", always_xy=True)

    (x0, y0) = config_coord_converter.transform(config.x0, config.y0)
    rot_angle_in_radian = np.deg2rad(config.rotation)

    point_coord_converter = Transformer.from_crs(f"EPSG:{point_epsg_projection}", f"EPSG:{crs_target}", always_xy=True)
    x,y = point_coord_converter.transform(x_point,y_point)

    x_trans, y_trans = translate_grid(x, y, -x0, -y0)
    x_mitgcm, y_mitgcm = rotate_grid(x_trans, y_trans, 0, 0, -rot_angle_in_radian)

    return x_mitgcm, y_mitgcm