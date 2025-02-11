#!/bin/bash -l

#SBATCH --account=em09
#SBATCH --job-name="MITgcmInference"
#SBATCH --time=00:05:00
#SBATCH --ntasks=576
#SBATCH --cpus-per-task=1
#SBATCH --partition=normal
#SBATCH --mail-user=anne.leroquais@eawag.ch
#SBATCH --mail-type=end
# Script to run the simulation on the CSSC cluster

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}

srun --ntasks=${SLURM_NTASKS} ./mitgcmuv

