import argparse
import yaml
import importlib.util
import os
import sys
from typing import Type, List
from galerna.base import Galerna

def parse_cases(cases_str: str) -> List[int]:
    cases = set()
    for part in cases_str.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            start_str, end_str = part.split('-', 1)
            start = int(start_str)
            end = int(end_str)
            cases.update(range(start, end + 1))
        else:
            cases.add(int(part))
    return sorted(list(cases))

def load_custom_wrapper(file_path: str, class_name: str = "CustomGalerna") -> Type[Galerna]:
    """
    Dynamically loads a Galerna subclass from a .py file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Custom wrapper file not found: {file_path}")
    
    spec = importlib.util.spec_from_file_location("custom_wrapper", file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {file_path}")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules["custom_wrapper"] = module
    spec.loader.exec_module(module)
    
    # Try to find a subclass of Galerna if class_name is default
    if class_name == "CustomGalerna":
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, Galerna) and 
                attr is not Galerna):
                return attr
    
    try:
        return getattr(module, class_name)
    except AttributeError:
        raise AttributeError(f"Module {file_path} has no class {class_name}")

def main():
    parser = argparse.ArgumentParser(description="CLI for building and running model wrappers.")
    parser.add_argument("action", choices=["build", "run", "postprocess", "all"], help="Action to perform.")
    parser.add_argument("--config", required=True, help="Path to the YAML configuration file.")
    parser.add_argument("--cases", type=str, help="Comma-separated list of case indices or ranges (e.g., '1,2,5-7') to process.")
    
    args = parser.parse_args()
    
    cases_list = None
    if args.cases is not None:
        try:
            cases_list = parse_cases(args.cases)
        except Exception as e:
            parser.error(f"Invalid format for --cases '{args.cases}': {e}")
    
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
    
    # Extract wrapper configuration
    wrapper_code_path = config.get("wrapper_code")
    wrapper_class_name = config.get("wrapper_class", "CustomGalerna")
    
    if wrapper_code_path:
        print(f"Loading custom wrapper from {wrapper_code_path}...")
        WrapperClass = load_custom_wrapper(wrapper_code_path, wrapper_class_name)
    else:
        WrapperClass = Galerna
        
    # Instantiate the wrapper
    # Remove CLI-specific keys from config to pass as kwargs
    wrapper_params = config.copy()
    for key in ["wrapper_code", "wrapper_class"]:
        wrapper_params.pop(key, None)
        
    wrapper = WrapperClass(**wrapper_params)
    
    if args.action in ["build", "all"]:
        print("Building cases...")
        wrapper.build_cases(cases=cases_list)
        
    if args.action in ["run", "all"]:
        print("Running cases...")
        wrapper.run_cases(cases=cases_list)

    if args.action in ["postprocess", "all"]:
        print("Postprocessing cases...")
        wrapper.postprocess_cases(cases=cases_list)

if __name__ == "__main__":
    main()
