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
    extracts the two types of entry within that file and adds the amiga_timestamp of when the data was added to the CSV.
    
    The IMU being used is an ACEINNA INS401 GNSS/RTK see: https://www.aceinna.com/inertial-systems/INS401
    User manual: 7430-4006-02_B_D8_INS401_UserManual.pdf
    
    1. High time resolution raw data: amiga_timestamp,fgps_week,gps_millis,ax,ay,az,gx,gy,gz
       
    There is a JSON-LD CSVW description for this data in file:  imu_raw_observations.csv-metadata.json and imu_observations.csv-metadata.json 
       
    **Table 11 from INS401 user guide: Raw IMU Data**
    Message ID     : 0x0a01 (2561) 
    Message Length : 30 bytes
    Message rate   : 100 Hz
    | **Field**       | **Offset (Byte)** | **Type** | **Unit**   | **Description**             |
    |-----------------|-------------------|----------|------------|-----------------------------|
    | `gps_week`      | 0                 | `uint16` | –          | GPS week                    |
    | `gps_millisecs` | 2                 | `uint32` | ms         | GPS time of week            |
    | `accel_x`       | 6                 | `float`  | m/s²       | Acceleration on X axis      |
    | `accel_y`       | 10                | `float`  | m/s²       | Acceleration on Y axis      |
    | `accel_z`       | 14                | `float`  | m/s²       | Acceleration on Z axis      |
    | `gyro_x`        | 18                | `float`  | deg/s      | Angular rate on X axis      |
    | `gyro_y`        | 22                | `float`  | deg/s      | Angular rate on Y axis      |
    | `gyro_z`        | 26                | `float`  | deg/s      | Angular rate on Z axis      |

  
    2. Lower time resolution GNS processed data: amiga_timestamp,gps_week,gps_millisecs,position_type,
                                                 latitude,longitude,height,latitude_std,
                                                 longitude_std,height_std,numberOfSVs,numberOfSVs_in_solution,
                                                 hdop,diffage,north_vel,east_vel,up_vel,north_vel_std,
                                                 east_vel_std,up_vel_std
    
    There is a JSON-LD CSVW description for this data in file:  gnss_observations.csv-metadata.json    
    
    **Table 4 from INS401 user guide: GNSS Solution Packet** from the INS401 User Manual
    Message ID     : 0x0a02 (2562) 
    Message Length : 77 bytes
    Message rate   : 1 Hz
    | **Field**               | **Offset (Byte)** | **Type**   | **Unit** | **Description**                                                                 |
    |-------------------------|-------------------|------------|----------|---------------------------------------------------------------------------------|
    | `gps_week`              | 0                 | `uint16`   | –        | GPS week                                                                       |
    | `gps_millisecs`         | 2                 | `uint32`   | ms       | GPS time of week                                                               |
    | `position_type`         | 6                 | `uint8`    | –        | Positioning type:<br>0: INVALID<br>1: SPP<br>==2: RTD<br>3: INS_PROPAGATED<br>4: RTK_FIXED<br>5: RTK_FLOAT |
    | `latitude`              | 7                 | `double`   | deg      | Geodetic latitude                                                              |
    | `longitude`             | 15                | `double`   | deg      | Geodetic longitude                                                             |
    | `height`                | 23                | `double`   | m        | Height above ellipsoid                                                         |
    | `latitude_std`          | 31                | `float`    | m        | Latitudinal position accuracy                                                  |
    | `longitude_std`         | 35                | `float`    | m        | Longitudinal position accuracy                                                 |
    | `height_std`            | 39                | `float`    | m        | Vertical position accuracy                                                     |
    | `numberOfSVs`           | 43                | `uint8`    | –        | Number of satellites                                                           |
    | `numberOfSVs_in_solution` | 44              | `uint8`    | –        | Number of satellites used in solution                                          |
    | `Hdop`                  | 45                | `float`    | –        | Horizontal Dilution of Precision                                               |
    | `Diffage`               | 49                | `float`    | s        | Age of differential GNSS correction                                            |
    | `north_vel`             | 53                | `float`    | m/s      | North velocity                                                                 |
    | `east_vel`              | 57                | `float`    | m/s      | East velocity                                                                  |
    | `up_vel`                | 61                | `float`    | m/s      | Up velocity                                                                    |
    | `north_vel_std`         | 65                | `float`    | m/s      | North velocity accuracy                                                        |
    | `east_vel_std`          | 69                | `float`    | m/s      | East velocity accuracy                                                         |
    | `up_vel_std`            | 73                | `float`    | m/s      | Up velocity accuracy                                                           |



    3. This data is not currently output
    Here is **Table 5: INS Solution Packet** from the INS401 User Manual, formatted in Markdown:
    
    There is a JSON-LD CSVW description for this data in file:  ins_100hz_observations.csv-metadata.json
    
    **Table 5 from INS401 user guide7: INS Solution Packet**
    Message ID     : 0x0a03 (2563) 
    Message Length :110 bytes
    Message rate   : 100 Hz
    
    Requirements for the data output:
    - There is no significant steering action of the vehicle (Z-gyro rate <+/-5 dps)
    - Speed > 10km/h
    - 3s is needed if RTK solution is available
    | **Field**               | **Offset (Byte)** | **Type**   | **Unit** | **Description**                                                                 |
    |------------------------|-------------------|------------|----------|---------------------------------------------------------------------------------|
    | `gps_week`             | 0                 | `uint16`   | –        | GPS week                                                                       |
    | `gps_millisecs`        | 2                 | `uint32`   | ms       | GPS time of week                                                               |
    | `ins_status`           | 6                 | `uint8`    | –        | INS status:<br>0: INVALID<br>1: INS_ALIGNING<br>2: INS_HIGH_VARIANCE<br>3: INS_SOLUTION_GOOD<br>4: INS_SOLUTION_FREE<br>5: INS_ALIGNMENT_COMPLETE |
    | `ins_position_type`    | 7                 | `uint8`    | –        | INS position type:<br>0: INVALID<br>1: SPP/INS<br>2: RTD/INS<br>3: INS_PROPAGATE<br>4: RTK_FIXED/INS<br>5: RTK_FLOAT/INS |
    | `latitude`             | 8                 | `double`   | deg      | Geodetic latitude                                                              |
    | `longitude`            | 16                | `double`   | deg      | Geodetic longitude                                                             |
    | `height`               | 24                | `double`   | m        | Height above ellipsoid                                                         |
    | `north_velocity`       | 32                | `float`    | m/s      | North velocity in navigation ENU frame                                         |
    | `east_velocity`        | 36                | `float`    | m/s      | East velocity in navigation ENU frame                                          |
    | `up_velocity`          | 40                | `float`    | m/s      | Up velocity in navigation ENU frame                                            |
    | `longitudinal_velocity`| 44                | `float`    | m/s      | Forward velocity in vehicle frame                                              |
    | `lateral_velocity`     | 48                | `float`    | m/s      | Lateral velocity in vehicle frame                                              |
    | `roll`                 | 52                | `float`    | deg      | Vehicle roll                                                                   |
    | `pitch`                | 56                | `float`    | deg      | Vehicle pitch                                                                  |
    | `heading`              | 60                | `float`    | deg      | Vehicle heading                                                                |
    | `latitude_std`         | 64                | `float`    | m        | Latitudinal position accuracy                                                  |
    | `longitude_std`        | 68                | `float`    | m        | Longitudinal position accuracy                                                 |
    | `height_std`           | 72                | `float`    | m        | Vertical position accuracy                                                     |
    | `north_velocity_std`   | 76                | `float`    | m/s      | North velocity accuracy                                                        |
    | `east_velocity_std`    | 80                | `float`    | m/s      | East velocity accuracy                                                         |
    | `up_velocity_std`      | 84                | `float`    | m/s      | Up velocity accuracy                                                           |
    | `long_vel_std`         | 88                | `float`    | m/s      | Longitudinal velocity accuracy                                                 |
    | `lat_vel_std`          | 92                | `float`    | m/s      | Lateral velocity accuracy                                                      |
    | `roll_std`             | 96                | `float`    | deg      | Vehicle roll accuracy                                                          |
    | `pitch_std`            | 100               | `float`    | deg      | Vehicle pitch accuracy                                                         |
    | `heading_std`          | 104               | `float`    | deg      | Vehicle heading accuracy                                                       |
    | `continent_id`         | 108               | `int16`    | –        | Continent ID:<br>-2: NONE<br>-1: ERROR<br>0: UNKNOWN<br>1: ASIA<br>2: EUROPE<br>3: OCEANIA<br>4: AFRICA<br>5: NORTH AMERICA<br>6: SOUTH AMERICA<br>7: ANTARCTICA |


    """
    
    def extract(self, **kwargs: Any) -> None:
        """
        This method reads the '.origin' file extended version of the .bin file selected and reads the source directory (the directory where the .bin file was selected in the Phenomate GUI) and looks for files of the same name and timestamp to select and stores this as a list of filenames in the self.images list, to be processed in the save() method.
        
        """
        dir_part = self.path.parent  # this is another Path type
        file_part = self.path.name   # this is a str

        shared_logger.info(f'Directory: {dir_part}')
        shared_logger.info(f'Filename:  {file_part}')

        # Read the path that was written to the .origin file
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
                    output_file = file_path.name # this is a string  
                    # As the output filename isderived from the input .bin file, we need to add back the
                    # the GNSS part to the GNSS CSV filename
                    if output_file.lower().find("_gnss.csv") >= 0 :
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
        
        
        
