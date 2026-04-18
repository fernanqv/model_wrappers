import os
from typing import List, Any
from galerna.base import Galerna
import xarray as xr


class XbeachWrapper(Galerna):
    """
    Custom class that inherits from Galerna.
    Overrides postprocess_case to read the last line of fit.log
    and postprocess_cases to accumulate and return the results.
    """

    available_launchers = {
        "default": "xbeach.exe",
        "sci_unican": "/software/geocean/xbeach/launchXbeach.sh",
        "parallel": "echo {{np}} xbeach.exe"
    }

    def postprocess_case(self, case_context: dict, **kwargs) -> Any:
        """
        Reads the last line of 'fit.log' from the directory associated with this case.
        """
        case_dir = case_context.get("case_dir")
        if not case_dir:
            return None
            
        ncpath = os.path.join(case_dir, "xboutput.nc")
        
        if not os.path.isfile(ncpath):
            self.logger.warning(f"File not found: {ncpath}")
            return None
            
        try:
            ds_db = xr.open_dataset(ncpath)        
            x_db = ds_db['globalx'].values.flatten()        
            return(x_db)
        
        except Exception as e:
                self.logger.error(f"Error reading {ncpath}: {e}")
                return None 

