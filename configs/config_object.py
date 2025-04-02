import json


class Paths:
    def __init__(self, config, weather_model_config):
        self.grid_folder_path = config['grid_folder_path']
        self.dz_grid_csv_path = config['dz_grid_csv_path']
        self.bathy_path = config['bathy_path']
        self.swiss_topo_path = config['swiss_topo_path']
        self.raw_results_from_api_folder = weather_model_config['raw_results_from_api_folder']


class ConfigObject:
    def __init__(self, config_file_path):
        with open(config_file_path, 'r') as file:
            current_project = json.load(file)["current_project"]

        self.grid_config_name = current_project['grid_config_name']
        self.start_date = current_project['start_date']
        self.end_date = current_project['end_date']
        self.reference_date = current_project['reference_date']
        self.weather_model = current_project['weather_model']
        self.computer_config = current_project['computer_config']
        self.template_folder = current_project['template_folder']
        self.with_pickup = eval(current_project['with_pickup'])

        with open(config_file_path, 'r') as file:
            grid_config = json.load(file)["grid_config"][self.grid_config_name]

        with open(config_file_path, 'r') as file:
            weather_model_config = json.load(file)["weather_model_config"][self.weather_model]

        with open(config_file_path, 'r') as file:
            computer_config = json.load(file)["computer_config"][self.computer_config]

        # Grid parameters
        self.grid_resolution = grid_config['grid_resolution']
        self.time_step = grid_config['time_step']
        self.x0_ch1903 = grid_config["x0_ch1903"]
        self.y0_ch1903 = grid_config["y0_ch1903"]
        self.x1_ch1903 = grid_config["x1_ch1903"]
        self.y1_ch1903 = grid_config["y1_ch1903"]
        self.Nx = grid_config["Nx"]
        self.Ny = grid_config["Ny"]

        # Computer parameters
        self.Px = computer_config["Px"]
        self.Py = computer_config["Py"]
        self.endian_type = computer_config["endian_type"]

        # Lake characteristics
        self.lake_altitude = grid_config["lake_altitude"]

        # Weather model
        self.weather_api_base_url = weather_model_config['base_url']
        self.weather_download_buffer = weather_model_config['buffer']
        self.weather_model_type = weather_model_config['type']

        # Paths
        self.paths = Paths(grid_config, weather_model_config)

    def write_metadata_to_file(self, output_file_path):
        with open(output_file_path, 'w') as file:
            file.write("ConfigObject Metadata\n")
            file.write("=====================\n\n")

            for arg, value in vars(self).items():
                if isinstance(value, Paths):
                    file.write(f"{arg}:\n")
                    for path_attr, path_value in vars(value).items():
                        file.write(f"  {path_attr}: {path_value}\n")
                else:
                    file.write(f"{arg}: {value}\n")
