#!/bin/bash
#SBATCH --no-requeue
#SBATCH --job-name="aiida-127282"
#SBATCH --get-user-env
#SBATCH --output=_scheduler-stdout.txt
#SBATCH --error=_scheduler-stderr.txt
#SBATCH --partition=small-g
#SBATCH --account=project_465000416
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=56
#SBATCH --time=02:00:00
#SBATCH --mem=390625

 


module purge
module load PrgEnv-gnu/8.3.3
module load craype-x86-milan
module load cray-libsci/23.02.1.1
module load cray-fftw/3.3.10.3
module load cray-hdf5-parallel/1.12.2.3
module load cray-netcdf-hdf5parallel/4.9.0.3

export OMP_NUM_THREADS=1


'srun' '-u' '-n' '56' '/scratch/project_465000106/src/mbx/qe-dev/build/bin/pw.x' '-npool' '7' '-in' 'aiida.in'  > 'aiida.out'

 
