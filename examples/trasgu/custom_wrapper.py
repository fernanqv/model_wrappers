import os
from typing import List, Any
from galerna.base import Galerna

class FitPostprocessWrapper(Galerna):
    """
    Custom class that inherits from Galerna.
    Overrides postprocess_case to read the last line of fit.log
    and postprocess_cases to accumulate and return the results.
    """


    def postprocess_case(self, case_context: dict, **kwargs) -> Any:
        """
        Reads the last line of 'fit.log' from the directory associated with this case.
        """
        case_dir = case_context.get("case_dir")
        if not case_dir:
            return None
            
        fit_log_path = os.path.join(case_dir, "fit.log")
        
        if not os.path.isfile(fit_log_path):
            self.logger.warning(f"File not found: {fit_log_path}")
            return None
            
        try:
            with open(fit_log_path, "r") as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    self.logger.debug(f"Last line read from {fit_log_path}: {last_line}")
                    return last_line
                return None
        except Exception as e:
            self.logger.error(f"Error reading {fit_log_path}: {e}")
            return None

    def postprocess_cases(
        self,
        cases: List[int] = None,
        clean_after: bool = False,
        overwrite: bool = False,
        **kwargs,
    ) -> List[Any]:
        """
        Executes postprocess_case for each case and returns a list
        containing the output of each case.
        """
        if cases is not None:
            contexts_to_build = [self.cases_context[i] for i in cases]
        else:
            contexts_to_build = self.cases_context

        self.logger.info(f"Postprocessing {len(contexts_to_build)} cases...")
        results = []
        
        for context in contexts_to_build:
            # Capture the result of each case
            result = self.postprocess_case(
                case_context=context, 
                overwrite=overwrite, 
                clean_after=clean_after, 
                **kwargs
            )
            results.append(result)
            
        return results
