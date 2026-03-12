# Model Wrappers

**This project is a minimal fork of [BlueMath_tk](https://github.com/GeoOcean/BlueMath_tk).**

Minimal infrastructure for managing and running numerical model cases. This project provides a base `ModelWrapper` class to handle templating, parameter management, and parallel execution of numerical models.

## Installation

This package requires Python 3.11+ and `jinja2`.

```bash
pip install -e .
```

## Usage

The main workflow involves creating a custom wrapper class that inherits from `ModelWrapper`, defining your parameters, and then building and running the cases.

### Example: Holland Model

Here is how to use the wrapper for a Holland model, based on the `examples/example_holland.py` script.

```python
from model_wrappers import ModelWrapper
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
class HollandWrapper(ModelWrapper):
    pass

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

# 7. Run cases using a launcher command (optional)
launcher_cmd = "sbatch /path/to/your/launcher.sh"
wrapper.run_cases(launcher=launcher_cmd)
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

**Option A: String Template (Recommended)**
Use standard Python format strings. Any variable parameter name or `case_num` can be used.
```python
wrapper = HollandWrapper(
    ...,
    cases_name_format="case_{var1:04}_{var2:04}"
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

## Key Features

- **Jinja2 Templating**: Easily inject parameters into model input files.
- **Flexible selective building**: Build only the cases you need with `wrapper.build_cases(cases=[0, 5])`.
- **Custom directory naming**: Support for string templates (e.g., `"{var1}_{case_num}"`) or functions.
- **Easy context access**: Use `wrapper.get_context()` to see all case parameters and their absolute directory paths.
- **Template validation**: Automatic check for `templates_dir` existence during initialization.
- **Launcher Support**: Seamless integration with Slurm or local shell scripts.
