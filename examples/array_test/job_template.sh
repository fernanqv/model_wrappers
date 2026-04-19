#!/bin/bash
#SBATCH --array=0-{{max_array}}
#SBATCH --cpus-per-task={{max_workers}}
#SBATCH -o logs/job_%A_%a.out

module load 2024
module load parallel
module load parallel/20240722-GCCcore-13.3.0


## DO NOT TOUCH
START_LINE=$(( SLURM_ARRAY_TASK_ID * {{tasks_per_node}} + 1 ))
END_LINE=$(( START_LINE + {{tasks_per_node}} - 1 ))

sed -n "${START_LINE},${END_LINE}p" commands.txt | parallel -j {{max_workers}} python dummy_script.py {}
