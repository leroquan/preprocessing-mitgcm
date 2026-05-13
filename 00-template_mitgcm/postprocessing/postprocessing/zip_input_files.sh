#!/bin/bash

BINARY_DATA_DIR="/home/leroquan@eawag.wroot.emp-eaw.ch/work_space/lucerne_100m_2025/binary_data"
CODE_DIR="/home/leroquan@eawag.wroot.emp-eaw.ch/work_space/lucerne_100m_2025/code"
GRID_DIR="/home/leroquan@eawag.wroot.emp-eaw.ch/work_space/lucerne_100m_2025/grid"
RUN_CONFIG_DIR="/home/leroquan@eawag.wroot.emp-eaw.ch/work_space/lucerne_100m_2025/run_config"
POSTPROCESSING_DIR="/home/leroquan@eawag.wroot.emp-eaw.ch/work_space/lucerne_100m_2025/postprocessing"

OUTPUT_PATH="./input_files.zip"
rm -f "$OUTPUT_PATH"

zip -r "$OUTPUT_PATH" \
    "$BINARY_DATA_DIR" \
    "$CODE_DIR" \
    "$GRID_DIR" \
    "$RUN_CONFIG_DIR" \
    "$POSTPROCESSING_DIR"
