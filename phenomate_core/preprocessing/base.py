import abc
import os
import re
import logging
from pathlib import Path
from typing import Any, Generic, TypeVar
import shutil

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

    def matched_file_list(self, origin_path: Path, file_part : str) -> list[Path]:
        """
        Return a list of files from the source directory that match the timstamp of the :path: file.
           
        :param origin_path: The path to the source directoy
        :type origin_path: Path
        :param file_part: The name of the selected data file, with a timestamp in the name
        :type file_part: str
        
           
        """
        # Set of all files in the directory
        files_in_dir = self.list_files_in_directory(origin_path.parent)
        shared_logger.debug(f"BasePreprocessor: files_in_dir:  {files_in_dir}")
        # Set the timestamp regular expression
        filestamp = r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_\d+"  # defined in the Resonate processing when they save the files.
        # Match the filename timestamps to the input filename
        matched = self.match_timestamp(file_part, files_in_dir, filestamp)
        shared_logger.debug(f"BasePreprocessor: Matched files: {matched}")
        # Add back the directory
        matched_with_dir = [origin_path.parent / f for f in matched]
        # Save the list of matched filenames to extra_files list to be used
        # in the save() method. Conver t he strings to Path objects        
        path_objects = [Path(p) for p in matched_with_dir]
        return path_objects
        
    def copy_extra_files(self, fpath: Path) -> None:
        """
        Extra files that are associated with the .bin protobuffer data can be copied to the destination directory.
        
        :fpath Path: is the directory in which to save the files
        
        This method impicitly uses the extra_files list that should be populated in the extract() method using
        open_origin_file() and matched_file_list() (see: ImuPreprocessor.extract())
        
        """
        for file_path in self.extra_files:
            try:
                if type(self).__name__ == 'ImuPreprocessor':
                    # For the IMU there should be 3 files, 1 bin file and two CSV files
                    # and one CSV has GNSS in the filename
                    if file_path.suffix == ".bin":
                        file_path_name_ext = fpath / self.get_output_name(
                            index=None, ext="bin", details=None
                        )
                    elif file_path.suffix.lower() == ".csv":
                        file_path = Path(file_path)
                        output_file = file_path.name  # str
                        # As the output filename isderived from the input .bin file, we need to add back the
                        # the GNSS part to the GNSS CSV filename
                        if output_file.lower().find("_gnss.csv") >= 0:
                            file_path_name_ext = fpath / self.get_output_name(
                                index=None, ext="csv", details="GNSS"
                            )
                        else:
                            file_path_name_ext = fpath / self.get_output_name(
                                index=None, ext="csv", details=None
                            )

                        # TODO: Reorder the raw x.y.z timestamp data into chronological order in this step

                    shutil.copy(file_path, file_path_name_ext)
                    shared_logger.info(f"BasePreprocessor: IMU data transfer: Copied file: {file_path_name_ext}")
                
                elif type(self).__name__ == 'JaiPreprocessor':
                    # For the JAI there should be 2 extra files, both json
                    if file_path.suffix.lower() == ".json":
                        file_path = Path(file_path)
                        output_file = file_path.name  # str
                        file_path_name_ext = fpath / self.get_output_name(
                                index=None, ext="json", details=None
                        ) 
                        shutil.copy(file_path, file_path_name_ext)
                        shared_logger.info(f"BasePreprocessor: JAI data transfer: Copied file: {file_path_name_ext}") 
                    
                else:
                    shared_logger.info(f" BasePreprocessor.copy_extra_files() is not configured for class: {type(self).__name__}")


            except FileNotFoundError as e:
                shared_logger.error(f"BasePreprocessor: data transfer: File not found: {file_path} — {e}")
            except PermissionError as e:
                shared_logger.error(f"BasePreprocessor: data transfer: Permission denied: {file_path} — {e}")
            except OSError as e:
                shared_logger.error(f"BasePreprocessor: data transfer: OS error while accessing {file_path}: {e}")
            except Exception as e:
                shared_logger.exception(f"BasePreprocessor: data transfer: Unexpected error while reading {file_path}: {e}")
                raise

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
