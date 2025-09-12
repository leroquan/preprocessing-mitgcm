import numpy as np
import glob
import os

def modify_arguments(param_name: str, values, file_path, wrap=9):
    """
    Function to modify run-time parameters, based on variable name, with the
    assumption that they are stored the file as '!varName!'
      param_name  - parameter name that should be replaced in the config file
      values - values replacing the param_name in the config file
      fileIn  - 00-template_mitgcm configuration
      fileOut - output run-time configuration
    """

    with open(file_path, 'r') as infile:
        content = infile.read()

    if isinstance(values, np.ndarray):
        if values.ndim == 1:
            lines = []
            for i in range(0, len(values), wrap):
                chunk = values[i:i + wrap]
                line_str = ",".join(str(v) for v in chunk if not np.isnan(v))
                lines.append(line_str)
            str_values = "\n".join(lines)
        else:
            lines = []
            for row in values:
                row_str = ",".join(str(v) for v in row if not np.isnan(v))
                lines.append(row_str)
            str_values = "\n".join(lines)
    else:
        str_values = str(values)

    modified_content = content.replace(param_name, str_values)

    with open(file_path, 'w') as outfile:
        outfile.write(modified_content)


def convert_binary_files(folder_path: str, input_datatype, output_datatype):
    input_files = glob.glob(os.path.join(folder_path, '*.bin'))
    for file in input_files:
        with open(file, 'rb') as fid:
            binary_data = np.fromfile(fid, dtype=input_datatype)

        # Convert
        data = binary_data.astype(output_datatype)
        # Write to file
        fid = open(os.path.join(folder_path, os.path.basename(file)), 'wb')
        data.tofile(fid)
        fid.close()