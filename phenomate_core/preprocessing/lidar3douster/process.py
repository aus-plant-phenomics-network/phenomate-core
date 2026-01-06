from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any
import shutil

from phenomate_core.preprocessing.base import BasePreprocessor

# shared_logger = logging.getLogger("celery")
from phenomate_core.get_version import get_task_logger
shared_logger = get_task_logger(__name__)

class Ouster3dPreprocessor(BasePreprocessor[Path]):
    """
    Code based upon Resonate IMU writer: resonatesystems-rs24005-appn-instrument-interfaces-29_09_2005/Instruments/IMU
    
    """
    
    def __init__(self, path: str | Path, in_ext: str = "bin", **kwargs: Any):
        super().__init__(path, in_ext)   # pass parameters up to Base


    def extract(self, **kwargs: Any) -> None:
        """
        This method reads the '.origin' file extended version of the .bin file selected and
        reads the source directory (the directory where the .bin file was selected in the
        Phenomate GUI) and looks for files of the same name and timestamp to select and stores
        this as a list of filenames in the self.images list, to be processed in the save() method.
        """

        dir_part = self.path.parent  # this is another Path type
        file_part = self.path.name  # this is a str

        # Read the path that was written to the self.path+'.origin' file        
        origin_path = self.open_origin_file()  
        # Select the matching files from the path by the timestamp of the self.path file
        path_objects = self.matched_file_list(origin_path, file_part)
        
        for file_path in path_objects:
            if file_path.suffix == ".json":
                self.extra_files.append(file_path)
                
        shared_logger.info(f"Ouster3dPreprocessor data transfer: number of related files:  {len(self.extra_files)}")
        # self.images = path_objects

    def copy_extra_files(self, fpath: Path) -> None:
        """
        Extra files that are associated with the Ouster .pcap data can be copied to the destination directory.
        
        :fpath Path: is the directory in which to save the files
        
        This method impicitly uses the extra_files list that should be populated in the extract() method using
        open_origin_file() and matched_file_list() (see: ImuPreprocessor.extract())
        
        
        """
        for file_path in self.extra_files:
            try:
                # For the Ouster there should be 2 files, 1 json file and one PCAP files
                if file_path.suffix == ".json":
                    file_path_name_ext = fpath / self.get_output_name(
                        index=None, ext="json", details=None
                    )
                
                shutil.copy(file_path, file_path_name_ext)
                shared_logger.info(f"Ouster3dPreprocessor.copy_extra_files(): Ouster data transfer: Copied file: {file_path_name_ext}")

            except FileNotFoundError as e:
                shared_logger.error(f"Ouster3dPreprocessor: data transfer: File not found: {file_path} — {e}")
            except PermissionError as e:
                shared_logger.error(f"Ouster3dPreprocessor: data transfer: Permission denied: {file_path} — {e}")
            except OSError as e:
                shared_logger.error(f"Ouster3dPreprocessor: data transfer: OS error while accessing {file_path}: {e}")
            except Exception as e:
                shared_logger.exception(f"Ouster3dPreprocessor: data transfer: Unexpected error while reading {file_path}: {e}")
                raise
                
    def matched_file_list(self, origin_path: Path, file_part : str) -> list[Path]:

        """
        Return a list of files from the source directory that match the timstamp of the :path: file.
        """
        # Set of all files in the directory
        files_in_dir = self.list_files_in_directory(origin_path.parent)
        shared_logger.debug(f"Ouster3dPreprocessor: files_in_dir:  {files_in_dir}")
        
        # Set the timestamp regular expression
        filestamp = r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_\d+"  # defined in the Resonate processing when they save the files.
        # Match the filename timestamps to the input filename
        matched = self.match_timestamp(file_part, files_in_dir, filestamp)
        shared_logger.debug(f"Ouster3dPreprocessor: Matched files: {matched}")
        # Add back the directory
        matched_with_dir = [origin_path.parent / f for f in matched]
        # Save the list of matched filenames to extra_files list to be used
        # in the save() method. Conver t he strings to Path objects        
        path_objects = [Path(p) for p in matched_with_dir]
        return path_objects
        
            
    def save(
        self,
        path: Path | str,
        **kwargs: Any,
    ) -> None:
        """
        Save the data files from the IMU
        The bin file is the original data from the Phenomate IMU system
        The two CSV files are the raw positioning data and the GPS referenced data (GNSS data)
        """
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)

        # current_year = str(datetime.now(timezone.utc).year)
        # phenomate_version = get_version()
        start_time = time.time()

        self.copy_extra_files(fpath)

        # End timer
        end_time = time.time()
        # Print elapsed time
        shared_logger.info(f"Ouster3dPreprocessor: Write time: {end_time - start_time:.4f} seconds")
