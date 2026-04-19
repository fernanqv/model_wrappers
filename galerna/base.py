import copy
import io
import itertools
import logging
import os
import os.path as op
import queue
import subprocess
import sys
import threading
from typing import Any, Callable, Dict, List, Optional, Union

from jinja2 import Environment, FileSystemLoader

from .execution import exec_bash_command, parallel_execute
from .utils import copy_files, get_simple_logger, write_array_in_file


class Galerna:
    """
    Base class for numerical models wrappers.
    Autonomous implementation without external core dependencies.

    Attributes
    ----------
    templates_dir : str
        The directory where the templates are searched.
    variable_parameters : dict or str
        The parameters to be used for all cases, or a path to a YAML file containing them.
    fixed_parameters : dict
        The fixed parameters for the cases.
    output_dir : str
        The directory where the output cases are saved.
    """

    available_launchers = {}

    def __init__(
        self,
        templates_dir: Optional[str] = None,
        variable_parameters: Union[dict, str] = None,
        fixed_parameters: Optional[dict] = None,
        output_dir: str = "output",
        templates_name: Union[List[str], str] = "all",
        cases_name_format: Union[str, Callable] = '{{ "%04d" | format(case_num) }}',
        mode: str = "one_by_one",
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        log_console: Optional[bool] = None,
        num_workers: int = 1,
        launcher: str = "default",
        custom_launcher: Optional[str] = None,
        launcher_bulk: str = "bulk_default",
        custom_launcher_bulk: Optional[str] = None,
    ) -> None:
        """
        Initializes the Galerna instance.

        Parameters
        ----------
        templates_dir : str, optional
            The directory where the templates are searched. Default is None.
        variable_parameters : dict or str, optional
            The parameters to be used for all cases, or a path to a YAML file containing them. Default is empty dict.
        fixed_parameters : dict, optional
            The fixed parameters for the cases. Default is empty dict.
        output_dir : str, optional
            The directory where the output cases are saved. Default is 'output'.
        templates_name : Union[List[str], str], optional
            The names of the templates to use. Default is "all".
        cases_name_format : Union[str, Callable], optional
            The format for naming case directories (Jinja2 format). Default is '{{ "%04d" | format(case_num) }}'.
        mode : str, optional
            The mode to load the cases. Can be "all_combinations" or "one_by_one".
            Default is "one_by_one".
        log_level : str, optional
            The logging level (e.g., "DEBUG", "INFO", "WARNING"). Default is "INFO".
        log_file : str, optional
            Path to a file where logs should be written. If None, only console output is used.
        log_console : bool, optional
            Whether to output logs to the console. 
            If None, it defaults to True if log_file is None, and False otherwise.
        num_workers : int, optional
            The number of workers to use for parallel execution. Default is 1.
        launcher : str, optional
            Alias for the launcher command to be picked from available_launchers. Default is "default".
        custom_launcher : str, optional
            Arbitrary bash command string rendered with Jinja2 per case. Overrides launcher.
        launcher_bulk : str, optional
            Alias for bulk launcher from available_launchers. Default is "bulk_default".
        custom_launcher_bulk : str, optional
            Arbitrary bulk bash command rendered with Jinja2. Overrides launcher_bulk.
        """
        if log_console is None:
            log_console = log_file is None

        self._logger = get_simple_logger(
            name=self.__class__.__name__, 
            level=log_level, 
            log_file=log_file,
            console=log_console
        )
        
        self.templates_dir = templates_dir
        if variable_parameters is None:
            self.variable_parameters = {}
        elif isinstance(variable_parameters, str):
            import yaml
            if not os.path.isfile(variable_parameters):
                raise FileNotFoundError(f"variable_parameters file not found: {variable_parameters}")
            with open(variable_parameters, "r") as f:
                self.variable_parameters = yaml.safe_load(f) or {}
        else:
            self.variable_parameters = variable_parameters

        self.fixed_parameters = fixed_parameters or {}
        self.output_dir = output_dir
        self.cases_name_format = cases_name_format
        self.mode = mode
        self.num_workers = num_workers
        self.launcher = launcher
        self.custom_launcher = custom_launcher
        self.launcher_bulk = launcher_bulk
        self.custom_launcher_bulk = custom_launcher_bulk

        if self.templates_dir is not None:
            if not os.path.isdir(self.templates_dir):
                raise FileNotFoundError(f"Template directory not found: {self.templates_dir}")
            self._env = Environment(loader=FileSystemLoader(self.templates_dir))
            if templates_name == "all":
                self.templates_name = self.env.list_templates()
            else:
                self.templates_name = templates_name
        else:
            self._env = None
            self.templates_name = []

        self.cases_context: List[dict] = []
        self._generate_cases_context()

        self._thread: Optional[threading.Thread] = None
        self._status_queue: Optional[queue.Queue] = None


    def _generate_cases_context(self) -> None:
        """Generates the base cases context combinations and calculates directories."""
        # Convert any string "range(x, y)" into a list of integers
        for key, value in self.variable_parameters.items():
            if isinstance(value, str) and value.strip().startswith("range("):
                try:
                    self.variable_parameters[key] = list(eval(value.strip()))
                except Exception as e:
                    self.logger.warning(f"Could not evaluate range for parameter {key}: {e}")

        if self.mode == "all_combinations":
            keys = self.variable_parameters.keys()
            values = self.variable_parameters.values()
            combinations = itertools.product(*values)
            self.cases_context = [dict(zip(keys, c)) for c in combinations]
        elif self.mode == "one_by_one":
            num_cases = len(next(iter(self.variable_parameters.values())))
            self.cases_context = []
            for i in range(num_cases):
                case = {p: v[i] for p, v in self.variable_parameters.items()}
                self.cases_context.append(case)
        else:
            raise ValueError(f"Invalid mode: {self.mode}")

        self.logger.debug(f"Generated {len(self.cases_context)} cases in mode '{self.mode}'.")

        for i, context in enumerate(self.cases_context):
            context["case_num"] = i
            context.update(self.fixed_parameters)
            
            # Calculate case directory
            if isinstance(self.cases_name_format, str):
                if self.env:
                    name = self.env.from_string(self.cases_name_format).render(context)
                else:
                    from jinja2 import Template
                    name = Template(self.cases_name_format).render(context)
            else:
                name = self.cases_name_format(context)
            context["case_dir"] = op.abspath(op.join(self.output_dir, name))

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = get_simple_logger(name=self.__class__.__name__)
        return self._logger

    @logger.setter
    def logger(self, value: logging.Logger) -> None:
        self._logger = value

    @property
    def env(self) -> Environment:
        return self._env

    @property
    def cases_dirs(self) -> List[str]:
        """Returns a list of all case directories."""
        return [ctx.get("case_dir") for ctx in self.cases_context] if self.cases_context else []


    def build_case(self, case_context: dict) -> None:
        """
        Custom logic to build a specific case. 
        This method should be overridden by subclasses.

        Parameters
        ----------
        case_context : dict
            The context (parameters) for this specific case.
        """
        pass

    def get_context(self) -> Union[List[dict], Any]:
        """
        Returns the cases context.
        If pandas is installed, it returns a DataFrame.
        Otherwise, it returns a list of dictionaries.

        Returns
        -------
        Union[List[dict], pd.DataFrame]
            The cases context.
        """
        try:
            import pandas as pd
            return pd.DataFrame(self.cases_context)
        except ImportError:
            return self.cases_context

    def build_case_and_render_files(self, case_context: dict) -> None:
        """
        Creates the case directory, calls build_case, and renders templates.

        Parameters
        ----------
        case_context : dict
            The context (parameters) for this specific case.
        """
        case_dir = case_context["case_dir"]
        self.logger.debug(f"Building case {case_context.get('case_num')} in {case_dir}")
        os.makedirs(case_dir, exist_ok=True)
        self.build_case(case_context)
        for t_name in self.templates_name:
            try:
                template = self.env.get_template(t_name)
                rendered = template.render(case_context)
                with open(op.join(case_dir, t_name), "w") as f:
                    f.write(rendered)
            except Exception:
                copy_files(op.join(self.templates_dir, t_name), op.join(case_dir, t_name))

    def build_cases(
        self,
        cases: Optional[List[int]] = None,
    ) -> None:
        """
        Builds the selected cases by creating directories, calling build_case,
        and rendering template files.

        Parameters
        ----------
        cases : List[int], optional
            A list of indices of the cases to build.
            If None, all loaded cases are built.
        """
        
        if cases is not None:
            contexts_to_build = [self.cases_context[i] for i in cases]
        else:
            contexts_to_build = self.cases_context

        self.logger.debug(f"Starting to build {len(contexts_to_build)} cases.")
        for context in contexts_to_build:
            self.build_case_and_render_files(context)

    def run_case(
        self,
        case_num: int,
        output_log_file: str = "wrapper_out.log",
        error_log_file: str = "wrapper_error.log",
    ) -> None:
        """
        Run the case based on the launcher derived from the case context or defaults.

        Parameters
        ----------
        case_num : int
            The case number to run.
        output_log_file : str, optional
            The name of the output log file. Default is "wrapper_out.log".
        error_log_file : str, optional
            The name of the error log file. Default is "wrapper_error.log".
        """

        context = self.cases_context[case_num]
        
        if getattr(self, "custom_launcher", None):
            launcher_str = self.custom_launcher
        else:
            if self.launcher not in self.available_launchers:
                raise ValueError(
                    f"Launcher alias '{self.launcher}' not found in available_launchers. "
                    "If you want to use an arbitrary command, use 'custom_launcher'."
                )
            launcher_str = self.available_launchers[self.launcher]

        if self.env:
            launcher_cmd = self.env.from_string(launcher_str).render(context)
        else:
            from jinja2 import Template
            launcher_cmd = Template(launcher_str).render(context)
            
        case_dir = self.cases_dirs[case_num]

        # Run the case in the case directory
        self.logger.info(f"Running case {case_num} in {case_dir} with launcher={launcher_cmd}.")
        output_log_file = op.join(case_dir, output_log_file)

        exec_bash_command(
            cmd=launcher_cmd,
            cwd=case_dir,
            log_output=True,
            logger=self.logger,
        )

    def run_cases(
        self,
        cases: List[int] = None,
        num_workers: int = None,
    ) -> None:
        """
        Run the cases.
        Cases to run can be specified.
        Parallel execution is optional by modifying the num_workers parameter.

        Parameters
        ----------
        cases : List[int], optional
            The list with the cases to run. Default is None.
        num_workers : int, optional
            The number of parallel workers. Default is None.
        """

        if self.cases_context is None or self.cases_dirs is None:
            raise ValueError(
                "Cases context or cases directories are not set. Please run load_cases() first."
            )

        if num_workers is None:
            num_workers = self.num_workers

        if cases is not None:
            self.logger.warning(
                f"Cases to run was specified, so just {cases} will be run."
            )
            cases_list = cases
        else:
            cases_list = list(range(len(self.cases_dirs)))

        if num_workers > 1:
            self.logger.debug(
                f"Running cases in parallel. Number of workers: {num_workers}."
            )
            _results = parallel_execute(
                func=self.run_case,
                items=cases_list,
                num_workers=num_workers,
                logger=self.logger,
            )
        else:
            self.logger.debug(f"Running cases sequentially.")
            for case_num in cases_list:
                try:
                    self.run_case(
                        case_num=case_num,
                    )
                except Exception as exc:
                    self.logger.error(
                        f"Job for case {case_num} generated an exception: {exc}."
                    )

        self.logger.info("All cases executed.")

    def _run_cases_with_status(
        self,
        cases: List[int],
        num_workers: int,
        status_queue: queue.Queue,
    ) -> None:
        """
        Run the cases and update the status queue.

        Parameters
        ----------
        cases : List[int]
            The list with the cases to run.
        num_workers : int
            The number of parallel workers.
        status_queue : Queue
            The queue to update the status.
        """

        try:
            self.run_cases(cases, num_workers)
            status_queue.put("Completed")
        except Exception as e:
            status_queue.put(f"Error: {e}")

    def run_cases_in_background(
        self,
        cases: List[int] = None,
        num_workers: int = None,
        detached: bool = False,
    ) -> None:
        """
        Run the cases in the background.
        Cases to run can be specified.
        Parallel execution is optional by modifying the num_workers parameter.

        Parameters
        ----------
        cases : List[int], optional
            The list with the cases to run. Default is None.
        num_workers : int, optional
            The number of parallel workers. Default is None.
        detached : bool, optional
            If True, runs the process completely detached from the parent.
            If False, runs in a background thread of the parent process. Default is False.
        """

        if num_workers is None:
            num_workers = self.num_workers

        if detached:
            from .execution import run_detached
            self.logger.info("Running cases in a fully detached background process.")
            run_detached(self.run_cases, cases, num_workers)
        else:
            if not hasattr(self, "status_queue") or self.status_queue is None:
                self.status_queue = queue.Queue()
            self.thread = threading.Thread(
                target=self._run_cases_with_status,
                args=(cases, num_workers, self.status_queue),
            )
            self.thread.start()

    def get_thread_status(self) -> str:
        """
        Get the status of the background thread.

        Returns
        -------
        str
            The status of the background thread.
        """

        if self.thread is None:
            return "Not started"
        elif self.thread.is_alive():
            return "Running"
        else:
            return self.status_queue.get()

    def run_cases_bulk(
        self,
        launcher: str = None,
        path_to_execute: str = None,
    ) -> None:
        """
        Run the cases in bulk optionally based on the launcher specified.
        This is thought to be used in a cluster environment, as it is a bulk execution of the cases.
        By default, the command is executed in the output directory, where the cases are saved,
        and where the example sbatch file is saved.

        Parameters
        ----------
        launcher : str
            The launcher to run the cases.
        path_to_execute : str, optional
            The path to execute the command. Default is None.

        Examples
        --------
        # This will execute the specified launcher in the output directory.
        >>> wrapper.run_cases_bulk(launcher="sbatch sbatch_example.sh")
        # This will execute the specified launcher in the specified path.
        >>> wrapper.run_cases_bulk(launcher="my_launcher.sh", path_to_execute="/my/path/to/execute")
        """

        if launcher is not None:
             launcher_str = self.available_launchers.get(launcher, launcher) 
        elif getattr(self, "custom_launcher_bulk", None):
             launcher_str = self.custom_launcher_bulk
        else:
             if getattr(self, "launcher_bulk", None) in self.available_launchers:
                 launcher_str = self.available_launchers[self.launcher_bulk]
             elif "default" in self.available_launchers:
                 launcher_str = self.available_launchers["default"]
             else:
                 raise ValueError(
                     "Could not find a valid bulk launcher alias. Define 'launcher_bulk' or 'custom_launcher_bulk'."
                 )

        if self.env:
            launcher_cmd = self.env.from_string(launcher_str).render(self.fixed_parameters)
        else:
            from jinja2 import Template
            launcher_cmd = Template(launcher_str).render(self.fixed_parameters)
                
        if path_to_execute is None:
            path_to_execute = self.output_dir

        self.logger.info(f"Running cases with launcher={launcher_cmd} in {path_to_execute}")
        exec_bash_command(cmd=launcher_cmd, cwd=path_to_execute, logger=self.logger)


    def postprocess_case(self, **kwargs) -> None:
        """
        Postprocess the model output.
        """

        raise NotImplementedError("The method postprocess_case must be implemented.")

    def postprocess_cases(
        self,
        cases: List[int] = None,
        clean_after: bool = False,
        overwrite: bool = False,
        **kwargs,
    ) -> None:
        """
        Postprocess the model output.
        All extra keyword arguments will be passed to the postprocess_case method.

        Parameters
        ----------
        cases : List[int], optional
            The list with the cases to postprocess. Default is None.
        clean_after : bool, optional
            Clean the cases directories after postprocessing. Default is False.
        overwrite : bool, optional
            Overwrite the postprocessed file if it exists. Default is False.
        **kwargs
            Additional keyword arguments to be passed to the postprocess_case method.

        """

        if cases is not None:
            contexts_to_build = [self.cases_context[i] for i in cases]
        else:
            contexts_to_build = self.cases_context

        self.logger.debug(f"Starting to build {len(contexts_to_build)} cases.")

        postprocessed_files = []
        for context in contexts_to_build:
            postprocessed_file = self.postprocess_case(context, overwrite=overwrite, clean_after=clean_after, **kwargs)
            postprocessed_files.append(postprocessed_file)
        return postprocessed_files

