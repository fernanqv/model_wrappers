from galerna import Galerna
import os

os.chdir('examples/xbeach')

# Define template and output directories
templates_dir = "holland_template"
output_dir = "holland_output"

# Variable parameters (mapping thetamin to var1 and thetamax to var2 according to params.txt)
variable_parameters = {
    "var1": [225, 226],  # These correspond to {{var1}} in the template
    "var2": [514, 315],   # These correspond to {{var2}} in the template
    "compilation": ["gcc4", "intel"],  # Example of a parameter that could be used in the command
    "cores": [1, 2]  # Example of a parameter that could be used in the command
    #"launcher": ["ls", "pwd"]
}

# Fixed parameters (empty in this case)
fixed_parameters = {"var_fixed": 0}


# Create a simple child class (although Galerna is no longer abstract,
# it is common to inherit to define specific behaviors if needed)
# class HollandWrapper(Galerna):
#     available_launchers = {
#         "default": "xbeach.exe"
#     }

from aux.xbeach_wrapper import XbeachWrapper

# Instantiate the wrapper
wrapper = XbeachWrapper(
    templates_dir=templates_dir,
    variable_parameters=variable_parameters,
    fixed_parameters=fixed_parameters,
    output_dir=output_dir,
    cases_name_format="holland_{{ var1 }}_{{ var2 }}_{{ compilation }}_{{ cores }}",
    command="echo 'Running {{compilation}}_{{ cores }}' && pwd",
    log_level="DEBUG",
#    log_file="holland.log",
    mode="all_combinations"
)

# Generate cases (build)
print("Generating cases in directory:", output_dir)
df_context = wrapper.get_context()
print(df_context)

#wrapper.build_cases(cases=[0, 1, 2])
wrapper.build_cases()
wrapper.run_cases(cases=[0, 1])

data=wrapper.postprocess_cases(cases=[0])
print(data)



#wrapper.run_cases_in_background(launcher="sleep 100 && echo 'hello'", detached=True, num_workers=2)
#wrapper.run_cases(launcher="sbatch /nfs/home/geocean/valvanuz/galerna/examples/launchers/slurm_xbeach.sh")
#from galerna.execution import exec_bash_command, parallel_execute
