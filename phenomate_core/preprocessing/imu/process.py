from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from phenomate_core.preprocessing.base import BasePreprocessor

shared_logger = logging.getLogger("celery")


class ImuPreprocessor(BasePreprocessor[Path]):
    """
    Code based upon Resonate IMU writer: resonatesystems-rs24005-appn-instrument-interfaces-29_09_2005/Instruments/IMU
    - The Pheomate system currently collects the raw IMU data as a .bin file (which notably is not a protobuffer 
    defined file) and then extracts the two types of entry, depending on the decoded message id and adds the 
    amiga_timestamp of when the data was added to the CSV. Message id 2561 is saved to the same filename as the `.bin`
    data, but with a `.csv` extension, and message id 2562 is saved with a `_GNSS.csv` extension.

    The IMU being used is an ACEINNA INS401 GNSS/RTK see: https://www.aceinna.com/inertial-systems/INS401
    User manual: 7430-4006-02_B_D8_INS401_UserManual.pdf
    
    There are three message ids and the data they contain are listed in the next 3 tables.

    1. High time resolution raw data: amiga_timestamp,fgps_week,gps_millis,ax,ay,az,gx,gy,gz

    There is a JSON-LD CSVW description for this data in file:  imu_raw_observations.csv-metadata.json and imu_observations.csv-metadata.json

    **Table 11 from INS401 user guide: Raw IMU Data**
    Message ID     : 0x0a01 (2561)
    Message Length : 30 bytes
    Message rate   : 1000 Hz
    | **Field**       | **Offset (Byte)** | **Type** | **Unit**   | **Description**             |
    |-----------------|-------------------|----------|------------|-----------------------------|
    | `gps_week`      | 0                 | `uint16` |            | GPS week                    |
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
    | `gps_week`              | 0                 | `uint16`   |          | GPS week                                                                       |
    | `gps_millisecs`         | 2                 | `uint32`   | ms       | GPS time of week                                                               |
    | `position_type`         | 6                 | `uint8`    |          | Positioning type: 0: INVALID 1: SPP ==2: RTD 3: INS_PROPAGATED 4: RTK_FIXED 5: RTK_FLOAT |
    | `latitude`              | 7                 | `double`   | deg      | Geodetic latitude                                                              |
    | `longitude`             | 15                | `double`   | deg      | Geodetic longitude                                                             |
    | `height`                | 23                | `double`   | m        | Height above ellipsoid                                                         |
    | `latitude_std`          | 31                | `float`    | m        | Latitudinal position accuracy                                                  |
    | `longitude_std`         | 35                | `float`    | m        | Longitudinal position accuracy                                                 |
    | `height_std`            | 39                | `float`    | m        | Vertical position accuracy                                                     |
    | `numberOfSVs`           | 43                | `uint8`    |          | Number of satellites                                                           |
    | `numberOfSVs_in_solution` | 44              | `uint8`    |          | Number of satellites used in solution                                          |
    | `Hdop`                  | 45                | `float`    |          | Horizontal Dilution of Precision                                               |
    | `Diffage`               | 49                | `float`    | s        | Age of differential GNSS correction                                            |
    | `north_vel`             | 53                | `float`    | m/s      | North velocity                                                                 |
    | `east_vel`              | 57                | `float`    | m/s      | East velocity                                                                  |
    | `up_vel`                | 61                | `float`    | m/s      | Up velocity                                                                    |
    | `north_vel_std`         | 65                | `float`    | m/s      | North velocity accuracy                                                        |
    | `east_vel_std`          | 69                | `float`    | m/s      | East velocity accuracy                                                         |
    | `up_vel_std`            | 73                | `float`    | m/s      | Up velocity accuracy                                                           |



    3. This data is not currently output
    Table 5 from the INS401 User Manual, formatted in Markdown.

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
    | `gps_week`             | 0                 | `uint16`   |          | GPS week                                                                       |
    | `gps_millisecs`        | 2                 | `uint32`   | ms       | GPS time of week                                                               |
    | `ins_status`           | 6                 | `uint8`    |          | INS status: 0: INVALID 1: INS_ALIGNING 2: INS_HIGH_VARIANCE 3: INS_SOLUTION_GOOD 4: INS_SOLUTION_FREE 5: INS_ALIGNMENT_COMPLETE |
    | `ins_position_type`    | 7                 | `uint8`    |          | INS position type: 0: INVALID 1: SPP/INS 2: RTD/INS 3: INS_PROPAGATE 4: RTK_FIXED/INS 5: RTK_FLOAT/INS |
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
    | `continent_id`         | 108               | `int16`    |          | Continent ID: -2: NONE -1: ERROR 0: UNKNOWN 1: ASIA 2: EUROPE 3: OCEANIA 4: AFRICA 5: NORTH AMERICA 6: SOUTH AMERICA 7: ANTARCTICA |


    """

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
        
        self.extra_files = path_objects
        shared_logger.info(f"IMU data transfer: number of related files:  {len(self.extra_files)}")
        # self.images = path_objects

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
        shared_logger.info(f"Write time (IMU data): {end_time - start_time:.4f} seconds")
