from model_wrappers import ModelWrapper
import os

# Define template and output directories
templates_dir = "templates/xbeach_holland_default"
output_dir = "xbeach_holland_exp"

os.chdir('examples')
# Variable parameters (mapping thetamin to var1 and thetamax to var2 according to params.txt)
variable_parameters = {
    "var1": [225, 226, 227],  # These correspond to {{var1}} in the template
    "var2": [514, 315, 316]   # These correspond to {{var2}} in the template
}

# Fixed parameters (empty in this case)
fixed_parameters = {"var_fixed": 0}

# Create a simple child class (although ModelWrapper is no longer abstract,
# it is common to inherit to define specific behaviors if needed)
class HollandWrapper(ModelWrapper):
    # available_launchers = {
    #     "serial": "swash_serial.exe",
    #     "mpi": "mpirun -np 2 swash_mpi.exe",
    #     "docker_serial": "docker run --rm -v .:/case_dir -w /case_dir geoocean/rocky8 swash_serial.exe",
    #     "docker_mpi": "docker run --rm -v .:/case_dir -w /case_dir geoocean/rocky8 mpirun -np 2 swash_mpi.exe",
    #     "geoocean-cluster": "launchSwash.sh",
    # }
    pass

# Instantiate the wrapper
wrapper = HollandWrapper(
    templates_dir=templates_dir,
    variable_parameters=variable_parameters,
    fixed_parameters=fixed_parameters,
    output_dir=output_dir,
    cases_name_format="holland_{var1:04}_{var2:04}",
    log_level="DEBUG",
#    log_file="holland.log",
    #mode="all_combinations"
)

# Generate cases (build)
print("Generating cases in directory:", output_dir)
df_context = wrapper.get_context()

#wrapper.build_cases(cases=[0, 1, 2])
wrapper.build_cases()

df_context = wrapper.get_context()

wrapper.run_cases_in_background(launcher="sleep 10", num_workers=2)
#wrapper.run_cases(launcher="sbatch /nfs/home/geocean/valvanuz/model_wrappers/examples/launchers/slurm_xbeach.sh")
