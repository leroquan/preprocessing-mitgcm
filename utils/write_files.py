import numpy as np
import glob
import os

def modify_arguments(param_name: str, values: np.array, file_path):
    '''
    Function to modify run-time parameters, based on variable name, with the
    assumption that they are stored the file as '!varName!'
      param_name  - parameter name that should be replaced in the config file
      values - values replacing the param_name in the config file
      fileIn  - 00-template_mitgcm configuration
      fileOut - output run-time configuration
    '''

    with open(file_path, 'r') as infile:
        content = infile.read()

    str_values = ''
    if len(values) > 1:
        for row in values:
            for val in row:
                str_values += str(str(val) + ',')
            str_values += '\n'
    else:
        str_values = str(values[0])

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