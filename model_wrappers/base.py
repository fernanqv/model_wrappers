import copy
import itertools
import logging
import os
import os.path as op
import subprocess
from typing import Any, Callable, Dict, List, Optional, Union

from jinja2 import Environment, FileSystemLoader

from .utils import copy_files, get_simple_logger, write_array_in_file


class ModelWrapper:
    """
    Base class for numerical models wrappers.
    Autonomous implementation without external core dependencies.

    Attributes
    ----------
    templates_dir : str
        The directory where the templates are searched.
    variable_parameters : dict
        The parameters to be used for all cases.
    fixed_parameters : dict
        The fixed parameters for the cases.
    output_dir : str
        The directory where the output cases are saved.
    """

    available_launchers = {}

    def __init__(
        self,
        templates_dir: Optional[str],
        variable_parameters: dict,
        fixed_parameters: dict,
        output_dir: str,
        templates_name: Union[List[str], str] = "all",
        cases_name_format: Union[str, Callable] = "{case_num:04}",
        mode: str = "one_by_one",
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        log_console: Optional[bool] = None,
    ) -> None:
        """
        Initializes the ModelWrapper.

        Parameters
        ----------
        templates_dir : str, optional
            The directory where the templates are searched.
        variable_parameters : dict
            The parameters to be used for all cases.
        fixed_parameters : dict
            The fixed parameters for the cases.
        output_dir : str
            The directory where the output cases are saved.
        templates_name : Union[List[str], str], optional
            The names of the templates to use. Default is "all".
        cases_name_format : Union[str, Callable], optional
            The format for naming case directories. Default is "{case_num:04}".
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
        self.variable_parameters = variable_parameters
        self.fixed_parameters = fixed_parameters
        self.output_dir = output_dir
        self.cases_name_format = cases_name_format
        self.mode = mode

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

    def _generate_cases_context(self) -> None:
        """Generates the base cases context combinations and calculates directories."""
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
                name = self.cases_name_format.format(**context)
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

    def run_cases(self, launcher: str) -> None:
        """
        Runs all loaded cases using the provided launcher.
        Supports variable expansion in the launcher string (e.g., {case_dir}).

        Parameters
        ----------
        launcher : str
            The launcher command.
        """
        self.logger.debug(f"Running cases with launcher: {launcher}")
        for context in self.cases_context:
            case_dir = context["case_dir"]
            # Support basic formatting if the launcher has placeholders
            try:
                cmd = launcher.format(**context)
            except (KeyError, IndexError):
                cmd = launcher
            
            self.logger.debug(f"Executing command: {cmd} (cwd: {case_dir})")
            try:
                subprocess.run(cmd, shell=True, cwd=case_dir, check=True)
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Command failed in case {context.get('case_num')}: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error executing case {context.get('case_num')}: {e}")
