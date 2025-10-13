from __future__ import annotations

import struct
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import time
import shutil
import os

from phenomate_core.preprocessing.base import BasePreprocessor

# from phenomate_core.get_logging import shared_logger
import logging
shared_logger = logging.getLogger('celery')
from phenomate_core.get_version import get_version


class ImuPreprocessor(BasePreprocessor[Path]):
    """
    Code based upon Resonate IMU writer: resonatesystems-rs24005-appn-instrument-interfaces-29_09_2005/Instruments/IMU
    - The Pehomate system currently collects the raw IMU data as a .bin file (not a protobuffer defined file) and then 
    extracts the two types of entry within that file:
    1. High time resolution raw data: amiga_timestamp,fgps_week,gps_millis,ax,ay,az,gx,gy,gz
    2. Lower time resolution GNS processed data: amiga_timestamp,gps_week,gps_millisecs,position_type,
                                                 latitude,longitude,height,latitude_std,
                                                 longitude_std,height_std,numberOfSVs,numberOfSVs_in_solution,
                                                 hdop,diffage,north_vel,east_vel,up_vel,north_vel_std,
                                                 east_vel_std,up_vel_std
    """
    
    def extract(self, **kwargs: Any) -> None:

        dir_part = self.path.parent  # this is another Path type
        file_part = self.path.name   # this is a str

        shared_logger.info(f'Directory: {dir_part}')
        shared_logger.info(f'Filename:  {file_part}')

        origin_line = ''
        origin_file = str(self.path) + '.origin'
        with open(origin_file, "r", encoding="utf-8") as f:
            origin_line = f.readline()
            origin_line = origin_line.strip()
        
        origin_path = Path(origin_line)
        shared_logger.info(f'Filename:  {origin_path}')
        files_in_dir = self.list_files_in_directory(origin_path.parent)
        shared_logger.info(f'Files in directory: {files_in_dir}')
        
        
        filestamp = r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_\d+"  # defined in the Resonate processing when they save the files.
        matched = self.match_timestamp(file_part, files_in_dir, filestamp)
        shared_logger.info(f'Matched files: {matched}')
        
        matched_with_dir = [os.path.join(origin_path.parent, f) for f in matched]
        # Add the list of matched filenames to the classes data to be used
        # in the save() method
        self.images = matched_with_dir
    
        shared_logger.info("Found the following files with a matched timestamp:")
        shared_logger.info(self.images)
                
  
     
    def save(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Save the data files from the IMU
        The bin file is the original data from the Phenomate IMU system
        The two CSV files are the raw positioning data and the GPS referenced data (GNSS data)
        """
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)
        
        current_year = str(datetime.now().year)
        phenomate_version = get_version()
        start_time = time.time()

        # There should be 3 files, 1 bin file and two CSV files 
        # and one CSV has GNSS in the filename
        for file_path in self.images:
            try:
                if file_path.endswith('.bin'):
                    file_path_name_ext = fpath / self.get_output_name(index = None, ext = 'bin', details = None)
                elif file_path.lower().endswith('.csv'):
                    file_path = Path(file_path)
                    output_file = file_path.name   
                    # As the output filename isderived from the input .bin file, we need to add back the
                    # the GNSS part to the GNSS CSV filename
                    if output_file.find("GNSS") != 1:
                        file_path_name_ext = fpath / self.get_output_name(index = None, ext = 'csv', details = "GNSS")
                    else:
                        file_path_name_ext = fpath / self.get_output_name(index = None, ext = 'csv', details = None)
                        
                    #TODO: Reorder the raw x.y.z timestamp data into chronological order in this step
                    shared_logger.info(f"file_path: {file_path}")
                    shared_logger.info(f"file_path_name_ext: {file_path_name_ext}")
                    shutil.copy(file_path, file_path_name_ext)
                    
                shared_logger.info(f"Copied file: {file_path_name_ext}")
                
            except Exception as e:
                shared_logger.error(f"Error reading {file_path}: {e}")

                

        # End timer
        end_time = time.time()
        # Print elapsed time        
        shared_logger.info(f"Write time (IMU data): {end_time - start_time:.4f} seconds")
        
        
        
