import abc
from pathlib import Path
from typing import TypeVar, Generic, Any

import numpy as np
from numpy.typing import NDArray

import re
import os

T = TypeVar("T")

class BasePreprocessor(Generic[T], abc.ABC):
    def __init__(self, path: str | Path, in_ext: str = "bin", **kwargs: Any) -> None:
        self._in_ext = self.process_ext(in_ext)
        self._base_name = self.validate_file_path(path)
        self.images: list[T] = []
        self.system_timestamps: list[int] = []

    @staticmethod
    def bytes_to_numpy(image: bytes) -> NDArray[np.uint8]:
        return np.frombuffer(image, dtype=np.uint8)

    def validate_file_path(self, path: str | Path) -> str:
        fpath = Path(path)
        if not fpath.exists():
            raise FileNotFoundError(f"File doesn't exist: {fpath!s}")
        if not fpath.is_file():
            raise ValueError(f"Not a file: {fpath!s}")
        self._path = fpath
        name = self.path.name
        if not name.endswith("." + self._in_ext):
            raise ValueError(f"Expects input file with ext: {self._in_ext}. Input: {name}")
        return name[: -len("." + self._in_ext)]

    def process_ext(self, ext: str) -> str:
        return ext[1:] if ext.startswith(".") else ext

    def get_output_name(self, index: int | None, ext: str, details: str | None = None) -> str:
        base = f"{self._base_name}_preproc"
        if index is not None:
            base += f"-{index:020}"
        if details is not None:
            base += f"_{details}"
        return f"{base}.{ext}"

    @abc.abstractmethod
    def extract(self, **kwargs: Any) -> None: ...

    @abc.abstractmethod
    def save(self, path: Path | str, **kwargs: Any) -> None: ...

    @property
    def path(self) -> Path:
        return self._path
        
    
    @staticmethod
    def extract_timestamp(filename: str, filestamp: str):
        # Match the pattern: YYYY-MM-DD_HH-MM-SS_milliseconds
        match = re.match(filestamp, filename)
        return match.group(0) if match else None
        
    @staticmethod
    def match_timestamp(target_filename: str, 
                        list_of_filenames: list[str], 
                        filestamp: str = r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_\d+"
                        ) -> list[str]:
        target_timestamp = extract_timestamp(target_filename, filestamp)
        if not target_timestamp:
            return []

        # Return all filenames that contain the same timestamp
        return [f for f in list_of_filenames if target_timestamp in f]


    @staticmethod
    def list_files_in_directory(directory: Path ) -> list[str]:
        # List all files in the directory
        try:
            files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
            return files
        except FileNotFoundError:
            print(f"Directory not found: {directory}")
            return []
        except PermissionError:
            print(f"Permission denied to access: {directory}")
            return []

