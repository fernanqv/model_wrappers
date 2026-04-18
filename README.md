# Model Wrappers

**This project is a minimal fork of [BlueMath_tk](https://github.com/GeoOcean/BlueMath_tk).**

Minimal infrastructure for managing and running numerical model cases. This project provides a base `Galerna` class to handle templating, parameter management, and parallel execution of numerical models.

## Installation

This package requires Python 3.11+ and `jinja2`.

```bash
pip install -e .
```

## Usage

The main workflow involves creating a custom wrapper class that inherits from `Galerna`, defining your parameters, and then building and running the cases.

### Example: Holland Model

Here is how to use the wrapper for a Holland model, based on the `examples/example_holland.py` script.

```python
from galerna import Galerna
import os

# 1. Define template and output directories
templates_dir = "templates/xbeach_holland_default"
output_dir = "xbeach_holland_exp"

# 2. Define Variable parameters
# Each key corresponds to a placeholder in your template files (e.g., {{var1}})
variable_parameters = {
    "var1": [225, 226, 227],
    "var2": [514, 315, 316]
}

# 3. Define Fixed parameters (optional)
fixed_parameters = {}

# 4. Create a custom wrapper class
class HollandWrapper(Galerna):
    # Available launchers for this wrapper
    available_launchers = {
        "default": "sbatch /path/to/your/launcher.sh",
        "local": "bash /path/to/your/local_launcher.sh"
    }

# 5. Instantiate the wrapper
wrapper = HollandWrapper(
    templates_dir=templates_dir,
    variable_parameters=variable_parameters,
    fixed_parameters=fixed_parameters,
    output_dir=output_dir,
    mode="all_combinations"  # Default mode for case generation
)

# 6. Generate cases (rendering templates)
# The mode defined in __init__ will be used by default
wrapper.build_cases()

# 7. Run cases (optional)
# Uses the 'default' launcher from available_launchers.
# You can override the execution passing: launcher="alias" or custom_launcher="mpirun -np {{np}} model"
wrapper.run_cases()
```

### Example: Using the CLI

You can also run Galerna via the command line interface using a YAML configuration file.

1. Create a `config.yaml` file:

```yaml
wrapper_code: examples/example_holland.py
wrapper_class: HollandWrapper
templates_dir: templates/xbeach_holland_default
output_dir: xbeach_holland_exp
variable_parameters:
  var1: [225, 226, 227]
  var2: [514, 315, 316]
fixed_parameters: {}
custom_launcher: sbatch /path/to/your/launcher.sh
mode: all_combinations
```

2. Run the CLI:
```bash
galerna all --config config.yaml
```

3. Run the CLI for specific cases:
You can use the `--cases` argument to specify a subset of cases to process using comma-separated numbers or ranges:
```bash
# Build only cases 0, 1, and 2
galerna build --config config.yaml --cases 0-2

# Run only cases 1, 3, and 5
galerna run --config config.yaml --cases 1,3,5

# Both comma-separated lists and ranges are supported
galerna all --config config.yaml --cases 0,2,5-7
```

### Advanced Usage

#### Inspecting Case Parameters
You can inspect the parameters of all generated cases using `get_context()`. This is particularly useful after `load_cases()` or before `build_cases()`.

```python
# 8. Inspect the context (optional)
# This returns a DataFrame (if pandas is installed) with parameters and 'case_dir'
df_context = wrapper.get_context()
print(df_context)
```

#### Building a Subset of Cases
If you only want to build or re-build specific cases, you can pass a list of indices to `build_cases()`.

```python
# Only build the first and sixth cases (indices 0 and 5)
wrapper.build_cases(cases=[0, 5])
```

#### Custom Case Naming
You can customize how the case directories are named. This can be defined at the instance level (recommended) or overridden in `build_cases()`. It supports both string templates and functions.

**Option A: Jinja2 String Template (Recommended)**
Use standard Jinja2 format strings. Any variable parameter name or `case_num` can be used.
```python
wrapper = HollandWrapper(
    ...,
    cases_name_format="case_{{ '%04d' | format(var1) }}_{{ '%04d' | format(var2) }}"
)
```

**Option B: Callable (Function/Lambda)**
For more complex logic, pass a function that receives the case context dictionary.
```python
def my_custom_naming(ctx):
    prefix = "high" if ctx["var1"] > 226 else "low"
    return f"{prefix}_case_{ctx['case_num']}"

wrapper.build_cases(cases_name_format=my_custom_naming)
```

#### Dynamic Jinja2 Launchers
You can run cases dynamically with commands that adjust depending on the model configuration. The `custom_launcher` property supports evaluating any variable using Jinja2 syntax before dispatching the execution:

```yaml
# config.yaml example
templates_dir: templates
output_dir: exp_results_dynamic
mode: all_combinations

# The cases_name_format must include the combinatorics variables so folders do not overwrite each other
cases_name_format: "case-{{model_version}}_{{compilation}}_{{np}}cpus"

# The command is built securely checking variables available from the context
custom_launcher: "mpirun -np {{np}} model.{{model_version}}_{{compilation}}"

variable_parameters:
  compilation: ["gfortran", "ifort"]
  np: [1, 2, 4]
fixed_parameters:
  model_version: "4.1"
```

In this setup, each generated case will dispatch its corresponding isolated script execution, e.g., `mpirun -np 4 model.4.1_gfortran` running directly inside `case-4.1_gfortran_4cpus`.

## Creating Custom Wrapper Classes

The power of Galerna lies in its extensibility. You can create child classes that inherit from `Galerna` to add custom behavior for your specific workflow. This is useful when you need to:

- **Build custom inputs** for each case (e.g., generate configuration files based on parameters)
- **Extract and postprocess results** after cases run (e.g., read output files and aggregate metrics)
- **Define convenient launcher aliases** for your environment
- **Implement complex multi-step workflows** (build → run → postprocess combined)

### Extension Points: Overridable Methods

The following methods can be overridden in your child class to customize behavior:

| Method | Purpose | When to Override |
|--------|---------|------------------|
| `build_case(case_context)` | Add custom build logic for each case **before** templates are rendered | Generate case-specific input files, compute derived parameters, create case-specific directories |
| `available_launchers` (class dict) | Define command aliases for easy reuse | Create shortcuts for common commands (e.g., `"local"`, `"slurm"`) |
| `postprocess_case(**kwargs)` | Extract or process individual case results | Read output files, compute metrics, validate results for a single case |
| `postprocess_cases(cases, ...)` | Aggregate results from multiple cases | Combine metrics, create summary reports, perform statistical analysis |

### Example 1: Custom Build Logic

This example shows how to generate a case-specific parameter file before templates are rendered:

```python
from galerna import Galerna
import json

class CustomBuildWrapper(Galerna):
    """
    Example wrapper that generates case-specific fit_params.yaml
    based on variable parameters.
    """
    
    available_launchers = {
        "default": "python run_model.py",
        "slurm": "sbatch run_slurm.sh"
    }
    
    def build_case(self, case_context: dict) -> None:
        """
        Generate case-specific configuration files.
        This is called BEFORE templates are rendered.
        """
        case_dir = case_context["case_dir"]
        
        # Example: create a JSON config file with case parameters
        config = {
            "version": case_context.get("version", "1.0"),
            "param1": case_context.get("var1"),
            "param2": case_context.get("var2"),
        }
        
        config_path = os.path.join(case_dir, "case_config.json")
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        
        self.logger.info(f"Generated {config_path}")

# Usage:
wrapper = CustomBuildWrapper(
    templates_dir="templates/my_model",
    variable_parameters={"var1": [1, 2, 3], "var2": [10, 20]},
    output_dir="results",
    mode="all_combinations"
)

wrapper.build_cases()
wrapper.run_cases()
```

### Example 2: Post-processing Results

This realistic example, adapted from `examples/trasgu/custom_wrapper.py`, shows how to extract results from each case and aggregate them:

```python
from galerna import Galerna
import os
from typing import List, Any

class PostprocessWrapper(Galerna):
    """
    Wrapper that runs a model, then extracts results from case directories.
    Useful for parsing output files and aggregating metrics.
    """
    
    available_launchers = {
        "default": "trasgu_time_fit fit_params.yaml 1>time_fit.log 2>time_fit.err"
    }
    
    def postprocess_case(self, case_context: dict, **kwargs) -> Any:
        """
        Extract results from a single case.
        Called after the case has been run.
        
        Returns
        -------
        Any
            The extracted result (can be a dict, scalar, or any Python object)
        """
        case_dir = case_context.get("case_dir")
        if not case_dir:
            return None
        
        # Example: read the last line from an output file
        output_file = os.path.join(case_dir, "model_output.log")
        
        if not os.path.isfile(output_file):
            self.logger.warning(f"Output file not found: {output_file}")
            return None
        
        try:
            with open(output_file, "r") as f:
                lines = f.readlines()
                # Extract the last line (often contains summary/error info)
                if lines:
                    result = lines[-1].strip()
                    self.logger.debug(f"Extracted from {output_file}: {result}")
                    return result
            return None
        except Exception as e:
            self.logger.error(f"Error reading {output_file}: {e}")
            return None
    
    def postprocess_cases(
        self,
        cases: List[int] = None,
        clean_after: bool = False,
        overwrite: bool = False,
        **kwargs,
    ) -> List[Any]:
        """
        Aggregate results from all or selected cases.
        
        Parameters
        ----------
        cases : List[int], optional
            Case indices to postprocess. If None, processes all.
        clean_after : bool, optional
            Clean case directories after postprocessing. Default False.
        overwrite : bool, optional
            Overwrite existing results. Default False.
        **kwargs
            Additional arguments passed to postprocess_case.
        
        Returns
        -------
        List[Any]
            Results from all processed cases.
        """
        if cases is not None:
            contexts_to_process = [self.cases_context[i] for i in cases]
        else:
            contexts_to_process = self.cases_context
        
        self.logger.info(f"Postprocessing {len(contexts_to_process)} cases...")
        results = []
        
        for context in contexts_to_process:
            result = self.postprocess_case(case_context=context, **kwargs)
            results.append(result)
        
        return results

# Usage:
wrapper = PostprocessWrapper(
    templates_dir="templates/trasgu",
    variable_parameters={"version": ["v1", "v2"], "np": [2, 4, 8]},
    output_dir="results",
    mode="all_combinations"
)

# Complete workflow: build → run → postprocess
wrapper.build_cases()
wrapper.run_cases(num_workers=4)  # Run in parallel
results = wrapper.postprocess_cases()

print("Results from all cases:")
for case_num, result in enumerate(results):
    print(f"  Case {case_num}: {result}")
```

### Complete End-to-End Workflow

Here's how to combine all steps (build, run, postprocess) in a single workflow:

```python
from galerna import Galerna

# 1. Define wrapper class with custom behavior
class MyWrapper(Galerna):
    available_launchers = {
        "default": "bash run.sh",
        "local": "python model.py"
    }
    
    def build_case(self, case_context: dict) -> None:
        # Custom build logic here
        pass
    
    def postprocess_case(self, case_context: dict, **kwargs) -> dict:
        # Extract metrics/results here
        return {"case_num": case_context["case_num"], "status": "completed"}

# 2. Instantiate with parameters
wrapper = MyWrapper(
    templates_dir="my_templates",
    variable_parameters={
        "param_a": [1, 2],
        "param_b": [10, 20, 30]
    },
    output_dir="my_results",
    mode="all_combinations"
)

# 3. Inspect what will be generated
context_df = wrapper.get_context()
print("Cases to generate:")
print(context_df)

# 4. Build cases (create directories and render templates)
wrapper.build_cases()

# 5. Run all cases (in parallel with 4 workers)
wrapper.run_cases(num_workers=4)

# 6. Postprocess to extract results
results = wrapper.postprocess_cases()

# 7. Optionally, run specific cases later
wrapper.run_cases(cases=[0, 2])
results_subset = wrapper.postprocess_cases(cases=[0, 2])

# 8. Inspect results
for i, result in enumerate(results):
    print(f"Case {i}: {result}")
```

## Key Features

- **Jinja2 Templating**: Easily inject parameters into model input files and execution commands (launchers).
- **Flexible selective building**: Build only the cases you need with `wrapper.build_cases(cases=[0, 5])`.
- **Custom directory naming**: Support for Jinja2 string templates (e.g., `"{var1}_{case_num}"`) or functions.
- **Easy context access**: Use `wrapper.get_context()` to see all case parameters and their absolute directory paths.
- **Template validation**: Automatic check for `templates_dir` existence during initialization.
- **Launcher Support**: Seamless integration with Slurm or local shell scripts via standard aliases or Jinja-rendered commands.
