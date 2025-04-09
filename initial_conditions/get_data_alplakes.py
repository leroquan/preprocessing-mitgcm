import glob
import os
import xarray as xr
import json
import numpy as np
from datetime import datetime


def parse_alplakes_1d_from_directory(folder_path: str) -> xr.Dataset:
    json_files = glob.glob(os.path.join(folder_path, f'*.json'))

    # Initialize lists to store combined data
    all_times = []
    all_depths = []
    all_temperatures = []

    # Loop through each JSON file
    for file_path in json_files:
        # Read the JSON file
        with open(file_path, 'r') as file:
            data = json.load(file)

        # Extract time data and convert to datetime
        times = [datetime.fromisoformat(t.replace('Z', '+00:00')) for t in data['time']]

        # Extract depth and temperature data
        depths = np.array(data['depth']['data'])
        temperatures = np.array(data['variables']['T']['data'])

        # Append to the combined lists
        all_times.append(times)
        all_depths.append(depths)
        all_temperatures.append(temperatures)

    # Ensure all depth arrays are consistent
    if len(set(len(d) for d in all_depths)) != 1:
        raise ValueError("Depth arrays are not consistent across files.")

    # Use the first depth array (assumed consistent across files)
    depths = all_depths[0]

    # Combine all time and temperature data
    all_times = np.concatenate(all_times)
    all_times = np.array([dt.replace(tzinfo=None) for dt in all_times])
    all_temperatures = np.hstack(all_temperatures)

    # Create xarray dataset
    simstrat_data = xr.Dataset(
        {
            'temp': (['depth', 'time'], np.stack(all_temperatures))
        },
        coords={
            'time': all_times,
            'depth': depths
        }
    )

    return simstrat_data
