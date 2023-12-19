#!/bin/bash -l
#SBATCH --no-requeue
#SBATCH --job-name="aiida-974205"
#SBATCH --get-user-env
#SBATCH --output=_scheduler-stdout.txt
#SBATCH --error=_scheduler-stderr.txt
#SBATCH --partition=normal
#SBATCH --account=s1073
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=12
#SBATCH --time=10:00:00

### computer prepend_text start ###
#SBATCH --constraint=gpu
#SBATCH --hint=nomultithread

module load daint-gpu

if [ $NTASKS_PER_NODE -eq 1 ]; then
    CRAY_CUDA_MPS=0
else
    CRAY_CUDA_MPS=1
fi

export CRAY_CUDA_MPS=$CRAY_CUDA_MPS
export MPICH_MAX_THREAD_SAFETY=multiple
export MKL_NUM_THREADS=$SLURM_CPUS_PER_TASK
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

ulimit -s unlimited
### computer prepend_text end ###


module load QuantumESPRESSO/7.2-CrayNvidia-21.09


'srun' '-n' '1' '/apps/daint/UES/jenkins/7.0.UP03/21.09/daint-gpu/software/QuantumESPRESSO/7.2-CrayNvidia-21.09/bin/pw.x' '-npool' '1' '-in' 'aiida.in'  > 'aiida.out'

 
