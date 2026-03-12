import logging
import os
import shutil
from typing import Optional


def get_simple_logger(
    name: str, level: str = "INFO", log_file: Optional[str] = None, console: bool = True
) -> logging.Logger:
    """
    Creates a simple logger that outputs to console and optionally to a file.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding handlers if they already exist
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
            
    return logger


def write_array_in_file(array, filename: str) -> None:
    """
    Write a numpy-like array to a file.
    """
    with open(filename, "w") as f:
        if hasattr(array, "ndim") and array.ndim == 2:
            for row in array:
                f.write(" ".join(map(str, row)) + "\n")
        else:
            for item in array:
                f.write(f"{item}\n")


def copy_files(src: str, dst: str) -> None:
    """
    Copy file(s) from source to destination.
    """
    if os.path.isdir(src):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
