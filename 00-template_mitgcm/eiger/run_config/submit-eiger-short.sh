#!/bin/bash -l

#SBATCH --account=em09
#SBATCH --job-name="MITgcmInference"
#SBATCH --time=00:05:00
#SBATCH --ntasks=512
#SBATCH --ntasks-per-node=64
#SBATCH --cpus-per-task=1
#SBATCH --partition=normal
#SBATCH --mail-user=anne.leroquais@eawag.ch
#SBATCH --mail-type=end
# Script to run the simulation on the CSSC cluster

source /opt/cray/pe/cpe/23.12/restore_lmod_system_defaults.sh

module load PrgEnv-cray            # or PrgEnv-cray / PrgEnv-intel
module load craype-network-ofi
module load cray-mpich

# Optional: ensure CXI is the active provider
export FI_PROVIDER=cxi
unset MPICH_OFI_NIC_POLICY

# Quick fabric sanity check (prints provider info for node)
fi_info -p cxi | head

# Run your MPI program
srun ./mitgcmuv