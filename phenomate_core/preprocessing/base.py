import abc
import os
import re
import logging
from pathlib import Path
from typing import Any, Generic, TypeVar
import shutil
from datetime import datetime

import numpy as np
from numpy.typing import NDArray

T = TypeVar("T")

import logging
shared_logger = logging.getLogger("celery")

class BasePreprocessor(Generic[T], abc.ABC):
    def __init__(self, path: str | Path, in_ext: str = "bin", **kwargs: Any) -> None:
        self._in_ext = self.process_ext(in_ext)
        self._base_name = self.validate_file_path(path)
        self.images: list[T] = []
        self.extra_files: list[Path] = []
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
        
    def open_origin_file(self) -> Path :
        """
        Opens the :.origin: file that is saved to the output directory and that contains
        the path to the source directory, from which the :self.path: file originated
        from.       
        """
        # Read the path that was written to the .origin file
        # N.B. self.path is where the .ibn file has already been copied to.
        origin_line = ""
        origin_file = str(self.path) + ".origin" 

        # read the first line of the .origin file which stores the path of the
        # origin of 
        with Path.open(origin_file, encoding="utf-8") as f:
            origin_line = f.readline()
            origin_line = origin_line.strip()

        origin_path = Path(origin_line)
        shared_logger.debug(f"BasePreprocessor: Contents of .origin file:  {origin_path}")
        return origin_path


    @abc.abstractmethod
    def matched_file_list(self, origin_path: Path, file_part : str) -> list[Path]: 
        """
        Return a list of files from the source directory that match the timstamp of the :path: file.
        
        This method should be overridden to define the behavior
                of 'matched_file_list' in the derived class
        """
        ...
                
    @abc.abstractmethod
    def copy_extra_files(self, fpath: Path) -> None:
        """
        Extra files that are associated with the .bin proto buffer data can be copied to the destination directory.
        
        :fpath Path: is the directory in which to save the files
        
        This method impicitly uses the extra_files list that should be populated in the extract() method using
        open_origin_file() and matched_file_list() (see: ImuPreprocessor.extract())
        
        
        This method should be overridden to define the behavior
                of 'copy_extra_files' in the derived class

        """
        ...
       

    def return_closest_in_time(self, json_files : list, file_part_converted : str):
        """
        Returns the string from the list that is closest in time as the file_part_converted 
        string using the embedded timestamp data in the filenames.
        
        Returns: The string that has the closest timestamp
        
        Expects input timestamp format of: YYYY-MM-DD_HH-MM-SS_ddddddd
        
        """

        # Convert json list to tuples (datetime, filename)
        json_times = [(self.extract_datetime(f), f) for f in json_files]

        # Sort JSON files by time
        json_times.sort(key=lambda x: x[0])

        file_part_time = self.extract_datetime(file_part_converted)
        older_json = None
        for jt, jf in json_times:
            if jt < file_part_time:
                older_json = jf
            else:
                break
                
        return older_json
        
                    
    def extract_datetime(self, filename):
        """
        Expects input timestamp format of: YYYY-MM-DD_HH-MM-SS_ddddddd
        """
        date_str = filename.split("_")[0] + "_" + filename.split("_")[1] + "." + filename.split("_")[2]
        return datetime.strptime(date_str, "%Y-%m-%d_%H-%M-%S.%f")    
        
    
    def extract_timestamp(self, filename: str, filestamp: str):
        # Match the pattern: YYYY-MM-DD_HH-MM-SS_milliseconds
        match = re.match(filestamp, filename)
        return match.group(0) if match else None

    def match_timestamp(
        self,
        target_filename: str,
        list_of_filenames: list[str],
        filestamp: str = r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_\d+",
    ) -> list[str]:
        target_timestamp = self.extract_timestamp(target_filename, filestamp)
        if not target_timestamp:
            return []

        # Return all filenames that contain the same timestamp
        return [f for f in list_of_filenames if target_timestamp in f]

    @staticmethod
    def list_files_in_directory(directory: Path) -> list[str]:
        # List all files in the directory
        try:
            return [f for f in os.listdir(directory) if Path.is_file(directory / f)]
        except FileNotFoundError:
            print(f"Directory not found: {directory}")
            return []
        except PermissionError:
            print(f"Permission denied to access: {directory}")
            return []
