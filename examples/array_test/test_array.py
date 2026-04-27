import os
from galerna.bulk_array import BulkArrayRunner

def main():
    # We define the runner strictly using the Object Oriented approach 
    # instead of passing a YAML file and relying on the CLI.
    wrapper = BulkArrayRunner(
        tasks_per_node=5,
        max_workers=4,
        variable_parameters={"station": list(range(1, 16))},
        output_dir="output_array",
        mode="one_by_one",
        command="python dummy_script.py {{station}}",
        sbatch_template="/Users/valva/Library/CloudStorage/OneDrive-UNICAN/repos/galerna_old/examples/array_test/job_template.sh"
    )
    
    print("Building cases...")
    wrapper.build_cases()
    
    print("Done! You can submit the batch natively using slurm if inside a cluster.")
    # uncomment below to run:
    # wrapper.run_cases()

if __name__ == "__main__":
    main()
