# Execution Guide: `run` and `run_bulk`

This document explains the execution mechanisms available in Galerna for running your computational cases. Galerna is designed to be completely decoupled: the configuration of case parameters (physics/math) is separate from how the cases are actually executed (HPC clusters vs. local execution).

Galerna provides two main execution patterns:
1. **Case-by-case Execution (`run_cases`)**: Runs individual cases iteratively or in parallel.
2. **Bulk Execution (`run_cases_bulk`)**: Submits a single master job to a cluster (like a SLURM array) that governs all cases.

---

## 1. Case-by-case Execution (`run_cases`)

When you run cases individually, Galerna will enter each generated case directory and execute a specified command. 

### Ways to define the execution command

You can define the launcher in your `config.yaml` using one of two parameters:

#### Option A: `launcher` (Using Dictionary Aliases)
If your Python wrapper class (e.g., `MyWrapper(Galerna)`) has an `available_launchers` dictionary, you can simply call an alias.
```yaml
# config.yaml
launcher: slurm_unican
```

#### Option B: `custom_launcher` (Jinja2 Dynamic Commands)
You can write an arbitrary Bash command directly in the YAML file and use Jinja2 to dynamically inject parameters from your case into the command. 
```yaml
# config.yaml (Overrides 'launcher')
custom_launcher: "mpirun -np {{np}} my_model.exe --version {{version}}"
```

### How to trigger it
**Via CLI:**
```bash
galerna run --config config.yaml
```
*(You can also use `--cases 0,2-5` to run specific cases)*

**Via Python Script:**
```python
# Run all cases sequentially
wrapper.run_cases()

# Run specific cases in parallel
wrapper.run_cases(cases=[0, 1], num_workers=4)

# Run in background (non-blocking)
wrapper.run_cases_in_background(cases=[0, 1])
```

---

## 2. Bulk Execution (`run_cases_bulk`)

When working in an HPC environment (like SLURM or PBS), it is inefficient to submit 1,000 individual `sbatch` jobs. Bulk execution allows you to run a single "manager script" in the main `output_dir` that handles the execution array.

### Ways to define the bulk command

Similar to individual runs, bulk execution relies on two parameters:

#### Option A: `launcher_bulk` (Dictionary Aliases)
```yaml
# config.yaml
launcher_bulk: slurm_array
```

#### Option B: `custom_launcher_bulk` (Jinja2 Dynamic Commands)
This command will be rendered using your `fixed_parameters` (since bulk runs do not iterate over individual case parameters).
```yaml
# config.yaml
custom_launcher_bulk: "sbatch master_array.sh --env {{cluster_env}} --total-tasks 500"
```

### How to trigger it
*(Currently, bulk execution is usually triggered via Python script)*

**Via Python Script:**
```python
# Executes the command defined in custom_launcher_bulk (or launcher_bulk)
wrapper.run_cases_bulk()

# You can also manually override the execution path or command
wrapper.run_cases_bulk(
    launcher="custom_alias",
    path_to_execute="/my/custom/path"
)
```

---

## Summary of Configurations in YAML

A full configuration explicitly utilizing these execution parameters looks like this:

```yaml
templates_dir: templates
output_dir: results
mode: all_combinations
cases_name_format: "case-{{version}}_{{np}}"

variable_parameters:
  np: [1, 2, 4]
fixed_parameters:
  version: "v4"

# -- INDIVIDUAL EXECUTION --
# Used by: wrapper.run_cases() or 'galerna run'
# Replaces dictionary aliases completely.
custom_launcher: "mpirun -np {{np}} model.exe"  

# -- BULK EXECUTION --
# Used by: wrapper.run_cases_bulk()
# Evaluates Jinja using fixed_parameters.
custom_launcher_bulk: "sbatch slurm_array_submission.sh"
```
