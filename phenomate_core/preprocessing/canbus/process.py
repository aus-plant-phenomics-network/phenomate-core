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

class CanbusPreprocessor(BasePreprocessor[Path]):
    """
    Just copies over the csv files. Requires a "csv" entry in the template.yml file used by the appm library
    and has special processing in the phenomate/backen/activity/tasks.py remove_task() method so as not to
    delete the file at the end of the processing.
    
    Otherwise, this processor do nothing.
    
    """
    
    def __init__(self, path: str | Path, in_ext: str = "csv", **kwargs: Any):
        super().__init__(path, in_ext)   # pass parameters up to Base


    def extract(self, **kwargs: Any) -> None:
        """
        This does not do anything as the data is copied via the Phenomate preprocess task and needs to be ommited from deletion
        in the Phenomate remove_task() operation.
        """
        dir_part = self.path.parent  # this is another Path type
        file_part = self.path.name  # this is a str
                
        shared_logger.info(f"CanbusPreprocessor extract(): file_part = {file_part}")
        # self.images = path_objects

    def copy_extra_files(self, fpath: Path) -> None:
        """
        Don't copy any extra files with Canbus data.
        """
       
                
    def matched_file_list(self, origin_path: Path, file_part : str) -> list[Path]:

        """
        Return an empty list as there are no associated files to copy over with canbus data.
        """
        return []
        
            
    def save(
        self,
        path: Path | str,
        **kwargs: Any,
    ) -> None:
        """
        We do not have to save the input data for Canbus, as the CSV is copied to the output directory using the 
        
        """
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)

        # current_year = str(datetime.now(timezone.utc).year)
        # phenomate_version = get_version()

        # Print elapsed time
        shared_logger.info(f"CanbusPreprocessor: save(): path = {path}")
