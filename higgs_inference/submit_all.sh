#!/bin/bash

# sbatch run_truth.sh

sleep 30

sbatch run_scoreregression.sh

sleep 30

sbatch run_carl_point_by_point.sh
sbatch run_regression_point_by_point.sh

sleep 30

sbatch run_carl.sh
sbatch run_combined.sh
sbatch run_regression.sh
sbatch run_score.sh
sbatch run_combinedregression.sh

# sleep 60

# sbatch run_carl_aware.sh
# sbatch run_combined_aware.sh
# sbatch run_regression_aware.sh
# sbatch run_score_aware.sh
# sbatch run_combinedregression_aware.sh
