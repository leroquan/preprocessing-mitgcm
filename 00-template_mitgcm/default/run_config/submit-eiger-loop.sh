#!/bin/bash -l

#SBATCH --account=em09
#SBATCH --job-name="MITgcmInference"
#SBATCH --time=!time!
#SBATCH --ntasks=929
#SBATCH --cpus-per-task=1
#SBATCH --partition=normal
#SBATCH --mail-user=anne.leroquais@eawag.ch
#SBATCH --mail-type=end
# Script to run the simulation on the CSSC cluster

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export MPICH_GPU_SUPPORT_ENABLED=0
source ~/eiger_venv/bin/activate

NLOOPS=!NLOOPS!
STEPDURATION=!STEPDURATION!
SIMTIMESTEP=!SIMTIMESTEP!

sed -i "s/pChkptFreq.*=.*/pChkptFreq=${STEPDURATION}/" data
mkdir -p ../outputs
mkdir -p ../to_delete

for (( i=0; i<NLOOPS; i++ ))
do
	echo "=== Loop $i: Updating configuration at $(date '+%Y-%m-%d %H:%M:%S') ==="

	i_start=$((i * STEPDURATION))
	end_time=$((i_start + STEPDURATION))
	sed -i "s/startTime.*=.*/startTime=${i_start}/" data
	sed -i "s/endTime.*=.*/endTime=${end_time}/" data

	echo "startTime: $i_start"
	echo "end_time: $end_time"

	if [ "$i" -gt 0 ]; then
	  pickup_suff=$(printf "%010d" $((i_start / SIMTIMESTEP)))
	  sed -i "s/pickupSuff.*=.*/pickupSuff=${pickup_suff}/" data
	  echo "Pickup iteration number: $pickup_suff"
	fi

	echo "=== Loop $i: Starting MITgcm at $(date '+%Y-%m-%d %H:%M:%S') ==="

	# Run MITgcm
	srun --ntasks=${SLURM_NTASKS} ./mitgcmuv || { echo "MITgcm failed at loop $i"; exit 1; }

	echo "=== Loop $i: Postprocessing at $(date '+%Y-%m-%d %H:%M:%S') ==="

	# Run your Dask-based Python crop_results
	python ./check_valid_simulation.py || { echo "main.py failed at loop $i"; exit 1; }

done