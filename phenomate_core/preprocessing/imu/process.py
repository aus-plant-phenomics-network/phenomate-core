from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from datetime import datetime, timezone

import time

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

        files_in_dir = self.list_files_in_directory(dir_part)
        shared_logger.info(f'Files in directory: {files_in_dir}')

        filestamp = r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_\d+"  # defined in the Resonate processing when they save the files.
        matched = self.match_timestamp(file_part, files_in_dir, filestamp)
        shared_logger.info(f'Matched files: {matched}')
        
        self.images = matched
    
        shared_logger.info("Found the following files with a matched timestamp:")
        shared_logger.info(self.images)
                
  
     
    # Set bigtiff=True, for 64 bit TIFF  tags
    def save(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Save the data using the tifffile package.
        N.B. Only the Comression='none' output files are read natively by Windows      
            
        """
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)
        
        current_year = str(datetime.now().year)
        phenomate_version = get_version()
        start_time = time.time()
          
        for file_path in file_paths:
            if file_path.endswith('.bin'):
                shutil.copy(file_path, os.path.join(bin_destination, os.path.basename(file_path)))
            elif file_path.endswith('.csv'):
                try:
                    df = pd.read_csv(file_path)
                    if 'gps_millisecs' in df.columns:
                        df_sorted = df.sort_values(by='gps_millisecs')
                        sorted_dataframes[file_path] = df_sorted
                    else:
                        print(f"'gps_millisecs' column not found in {file_path}")
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

                df_sorted.to_csv(output_path, index=False)

            

        # End timer
        end_time = time.time()
        # Print elapsed time
        print(f"Write time (tifffile {compression_l} not bigtiff): {end_time - start_time:.4f} seconds")  # print statements end as a WARNING in logger output
        shared_logger.info(f"Write time (tifffile {compression_l} not bigtiff): {end_time - start_time:.4f} seconds")
        
        
        
