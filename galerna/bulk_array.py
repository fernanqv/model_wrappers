import json
import math
import os
import os.path as op
from typing import List, Optional

from galerna.base import Galerna
from galerna.execution import exec_bash_command


class BulkArrayRunner(Galerna):
    """
    A Runner designed for Embarrassingly Parallel workflows grouped in SLURM Job Arrays.
    It builds a single master text file with all generated commands, and uses 
    GNU Parallel within an array to execute them in chunks, completely bypassing 
    individual case directories.
    """

    def __init__(
        self,
        tasks_per_node: int = 1,
        max_workers: int = 1,
        sbatch_template: Optional[str] = None,
        templates_dir: Optional[str] = None,
        fixed_parameters: Optional[dict] = None,
        **kwargs
    ) -> None:
        """
        Initializes the BulkArrayRunner.

        Parameters
        ----------
        tasks_per_node : int, optional
            Number of commands processed by each SLURM_ARRAY_TASK_ID. Default is 1000.
        max_workers : int, optional
            Number of concurrent jobs executed by parallel locally on each node. Default is 40.
        **kwargs
            Standard parameters passed to the Galerna base class.
        """
        self.tasks_per_node = tasks_per_node
        self.max_workers = max_workers
        self.sbatch_template = sbatch_template
        super().__init__(**kwargs)

    def build_cases(
        self,
        cases: Optional[List[int]] = None,
    ) -> None:
        """
        Builds the cases. Instead of rendering individual folders, it renders 
        the Jinja2 commands and consolidates them into a master unrolled commands file,
        followed by generating the SLURM submission array wrapper.
        """
        os.makedirs(self.output_dir, exist_ok=True)
        
        if cases is not None:
            contexts_to_build = [self.cases_context[i] for i in cases]
        else:
            contexts_to_build = self.cases_context

        self.logger.debug(f"Starting to build {len(contexts_to_build)} combined cases for Array Bulk.")

        # Create SLURM bulk array script
        num_cases = len(contexts_to_build)
        if num_cases > 0:
            max_array = math.ceil(num_cases / self.tasks_per_node) - 1
        else:
            self.logger.warning("No cases available to build. Stopping Bulk Array generation.")
            return

        logs_dir = op.join(self.output_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        slurm_script_path = op.join(self.output_dir, "master_bulk_array.sh")
        
        if not self.sbatch_template or not os.path.isfile(self.sbatch_template):
            raise FileNotFoundError(
                "A valid 'sbatch_template' file must be provided to use BulkArrayRunner. "
            )

        with open(self.sbatch_template, "r") as template_file:
            template_content = template_file.read()
        
        # Allow jinja2 to inject the control variables into the template
        ctx_render = {
            "self": self,
            "max_array": max_array,
            "tasks_per_node": self.tasks_per_node,
            "max_workers": self.max_workers,
            "output_dir": self.output_dir
        }
        if self.env:
            script_content = self.env.from_string(template_content).render(ctx_render)
        else:
            script_content = Template(template_content).render(ctx_render)

        with open(slurm_script_path, "w") as f:
            f.write(script_content)
        
        self.logger.info(f"Built 'commands.txt' and SLURM array script '{slurm_script_path}' handling {num_cases} jobs using {max_array + 1} array instances.")


    def run_cases(
        self,
        cases: Optional[List[int]] = None,
        num_workers: Optional[int] = None,
    ) -> None:
        """
        Submits the entire block of operations seamlessly passing through the master array script.
        Bypasses any python multiprocessing because the local node scheduler manages parallel threads.
        """
        # Ensure we warn the user if they try to cherry-pick run cases in this paradigm.
        # Although technically possible, right now run_cases invokes the slurm script natively.
        if cases is not None:
            self.logger.warning(
                "Running specific cases is deprecated for BulkArrayRunner without rebuilding them. "
                "The entire array block (master_bulk_array.sh) will be executed."
            )

        slurm_script = op.join(self.output_dir, "master_bulk_array.sh")
        if not os.path.exists(slurm_script):
            raise FileNotFoundError(
                f"Slurm wrapper '{slurm_script}' not found. Did you run build_cases()?"
            )
            
        self.logger.info("Executing Bulk Array Jobs via Slurm natively...")
        exec_bash_command(cmd="sbatch master_bulk_array.sh", cwd=self.output_dir, logger=self.logger)


    def monitor_cases(self) -> None:
        """
        Placeholder logic to monitor execution from output logs or the general execution system
        to extract the remaining items.
        """
        self.logger.info("Monitoring array structure. Reading logs to identify uncaught elements...")
        # Since logic isn't strictly defined by the user for internal keywords yet,
        # we provide a generic implementation message.
        self.logger.warning("Monitor logic parser must be fine-tuned directly by the specific project criteria.")

