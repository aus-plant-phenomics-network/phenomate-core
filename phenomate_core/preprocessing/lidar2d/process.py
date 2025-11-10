from __future__ import annotations

import os
import sys

import struct
from pathlib import Path
from typing import Any

from datetime import datetime, timezone
import time
import csv

import numpy as np
import ctypes
import datatable as dt
import datatable.math as mt

from phenomate_core.preprocessing.base import BasePreprocessor
from phenomate_core.preprocessing.lidar2d import lidar_pb2
from  phenomate_core.preprocessing.lidar2d.sick_scan_api import ctypesCharArrayToString
from  phenomate_core.preprocessing.lidar2d.reading_proto_buff import from_proto

dt.options.nthreads = 1 

# from phenomate_core.get_logging import shared_logger
import logging
shared_logger = logging.getLogger('celery')
from phenomate_core.get_version import get_version


import psutil 

def check_memory_usage(notes: str):
    memory = psutil.virtual_memory()
    shared_logger.info(f"{notes}: Available Memory: {memory.available / (1024 ** 3):.4f} GB; Used Memory: {memory.used / (1024 ** 3):.4f} GB; Memory Usage: {memory.percent}%")




class Lidar2DPreprocessor(BasePreprocessor[lidar_pb2.SickScanPointCloudMsg]):
    """
    lidar_pb2.SickScanPointCloudMsg is the self.images list type
    
    Procedure edited from the Resonate resonatesystems-rs24005-appn-instrument-interfaces git (Bitbucket) 
    project process_lidar_binaryfiles.py file.
    
    3 input files are tested for speed of data conversion, writing to CSV, memory footprint and final data size.
    Times and sizes are linear with input data size.
    
    | Input bin / MB | messages       | elapsed time / s  |  <--- this is the time range from the 1st and last timestamp
    |----------------|----------------|-------------------|
    |      49.8      |   3670         |     6.115         |
    |      121       |   8938         |     14.89         |
    |      488       |   36000        |     60.0          |
     
    Original using Python lists
    | Input bin / MB | output CSV / MB | MemDiff / GB  | Processing Time / sec | CSV write / sec |
    |----------------|-----------------|---------------|-----------------------|-----------------|
    |      49.8      |   209           |       0.66    |   13.19               |     11.07       |     
    |      121       |   509           |       1.29    |   33.18               |     28.64       |  
    |      488       |   2051          |       5.34    |   125.59              |     112.97      | 
                                                        
    Numpy pre-allocated                                 
    | Input bin / MB | output CSV / MB | MemDiff / GB  | Processing Time / sec | CSV write / sec |
    |----------------|-----------------|---------------|-----------------------|-----------------|
    |      49.8      |   212           |       0.245   |   6.10                |     6.67        |     
    |      121       |   517           |       0.469   |   14.04               |     14.41       |  
    |      488       |   2084          |       1.755   |   54.57               |     57.65       |
                                       
    Numpy pre-allocated convert to 
    datatable            
    | Input bin / MB | output CSV / MB | MemDiff / GB  | Processing Time / sec | CSV write / sec |CSV write (4 threads) / sec |
    |----------------|-----------------|---------------|-----------------------|-----------------|----------------------------|
    |      49.8      |   204           |      0.208    |       6.50            |     1.016       |                            |
    |      121       |   497           |      0.391    |       16.6            |     2.316       |                            |
    |      488       |   2001          |      1.777    |       55.33           |     8.546       |                            |
    |      49.8      |   204           |      0.208    |       7.49            |                 |         0.350              |
    |      121       |   497           |      0.400    |       15.08           |                 |         0.774              |  
    |      488       |   2001          |      1.688    |       56.76           |                 |         3.236              |
    
    Numpy pre-allocated pivoted row per
    message - convert to datatable 
    (6 decimal places)          
    | Input bin / MB | output CSV / MB | MemDiff / GB  | Processing Time / sec | CSV write / sec |
    |----------------|-----------------|---------------|-----------------------|-----------------|
    |      49.8      |   85.3          |      0.106    |       8.03            |     0.475       |
    |      121       |   207           |      0.391    |       15.50           |     1.03        |
    |      488       |   837           |      1.281    |       54.17           |     5.86        |
    
    Numpy pre-allocated, ctype buffer, 
    pivoted row per message - convert 
    to datatable (6 decimal places)    
    | Input bin / MB | output CSV / MB | MemDiff / GB  | Processing Time / sec | CSV write / sec |
    |----------------|-----------------|---------------|-----------------------|-----------------|
    |      49.8      |   85.3          |      0.186    |       0.163           |     0.591       |
    |      121       |   207           |      0.383    |       0.368           |     1.74        |
    |      488       |   837           |      1.310    |       1.421           |     6.388       |
    """
    
    def __init__(self,  path: str | Path, in_ext: str = "bin"):
        super().__init__(path, in_ext)  # Call the parent class constructor
        self.total_messages = 0     # Add subclass-specific data
        self.msg_timestamp = []
        self.msg_height = 0
        self.msg_width = 0
        self.msg_num_fields = 0
        self.msg_data_size = 0
        self.msg_data_buffer = 0
        self.total_points_x = []
        self.total_points_y = []
        self.total_points_z = []
        self.total_timestamps = [] # For Amiga timestamps # use : self.system_timestamps
        self.total_lidar_timestamps = [] # For SickScan LIDAR timestamp
        self.total_points_intensity = []
        self.filtered_data = False
        self.total_xyzi = None
        self.row_offset = 0
        self.total_z_sum = 0.0
        
    def extract(self, **kwargs: Any) -> None:
        check_memory_usage('extract 1')
        with self.path.open("rb") as file:
            
            while True:
                # Read the length of the next serialized message
                serialized_timestamp = file.read(8)
                if not serialized_timestamp:
                    break
                system_timestamp = struct.unpack("d", serialized_timestamp)[0]

                length_bytes = file.read(4)
                if not length_bytes:
                    break
                message_length = int.from_bytes(length_bytes, byteorder="little")

                # Read the serialized message
                serialized_lidar_msg = file.read(message_length)

                # Parse the protobuf message
                protbuf_msg = lidar_pb2.SickScanPointCloudMsg()
                
                try:
                    protbuf_msg.ParseFromString(serialized_lidar_msg)
                    self.msg_timestamp.append(protbuf_msg.header.timestamp_sec + protbuf_msg.header.timestamp_nsec / 1e9)
                    self.system_timestamps.append(system_timestamp)
                    # Update to extracted image list
                    self.images.append(protbuf_msg)
                    self.total_messages += 1
                    
                except Exception as ex:
                    print(f"Error processing message: {ex}")
                    continue
                
                
                # shared_logger.info(f"Converted timestamp: system_timestamp:{system_timestamp}")
                
        # check_memory_usage('extract 2')
            
    def save(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
        This save() extracts the x,y,z,i data for each timestamp, create a row for each timestamp consisting of
        interleaved x,y,z,i values - e.g. 
        <amiga_timestamp>,<instrument_ts>, x0,y0,z0,i0, x1,y1,z1,i1,... xN,yN,zN,iN
        where N = 
        and saves the data to CSV using the datatable table to_csv() method, which can be run wih 
        multiple threads for improved performance (currently set to: dt.options.nthreads = 1 )
        """
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)
        
        # Some extra metadata which is not currently used
        current_year = str(datetime.now().year)
        phenomate_version = get_version()        
        user = "Phenomate user"
        
        
        start_time = time.time()
        for index, sickscan_lidar_protobuf_obj in enumerate(self.images):
            
            processed_msg = from_proto(sickscan_lidar_protobuf_obj)

            xyzi_res = self.py_sick_scan_cartesian_point_cloud_msg_to_xy_numpy(
                                processed_msg, index
                )
            points_xyzi = xyzi_res.reshape(( xyzi_res.shape[0] * 4))
            Nreps = xyzi_res.shape[0]
            
            # On reading the first data result, compute the shape 
            # of the final data
            if index == 0:
                try:
                    shared_logger.info(f"LIDAR SickScan Processing: Allocating numpy array of shape: ({self.total_messages}, {2 + (xyzi_res.shape[0] * 4)})")
                    self.total_xyzi= np.zeros((self.total_messages, 2 + (xyzi_res.shape[0] * 4)))
                except MemoryError as ex:
                    shared_logger.error(f"LIDAR SickScan Processing: Error allocating total_xyzi array message: {ex}")
                
            
            if xyzi_res is not None:
                # sum of the Z column, used to check for required 
                # formating when saving to csv - if 0.0 then do not 
                # add extra digits past the decimal
                self.total_z_sum += np.sum(xyzi_res[:, 2])  
                # Add the row of data t the numpy array
                self.total_xyzi[index, 2:] = points_xyzi               
                self.total_xyzi[index, 0:2] = np.array([self.system_timestamps[index],self.msg_timestamp[index]])
  
        end_time = time.time()
        # Print elapsed time
        total_points = self.total_xyzi.shape[0]
        shared_logger.info(f"LIDAR SickScan Processing: Total messages: {self.total_messages} ; Total xyz points: {total_points} ; Points per message: {total_points / self.total_messages}")
        shared_logger.info(f"LIDAR SickScan Processing: Preprocessing time : {end_time - start_time:.4f} seconds")
        check_memory_usage('save 4')
        
        
        start_time = time.time() 
        self.filtered_data = False
        csv_path_name_ext = fpath / self.get_output_name(index = None, ext = "csv", details = "dtpivot_ctype")
        
        
        header_base = [ "X", "Y", "Z", "Intensity"]
        # Nreps is typically 841 for the current 2D Lidar
        header_rep = [f"{col}{i}" for i in range(Nreps) for col in header_base]
        header = ["Amiga_timestamp", "Lidar_timestamp"] + header_rep

        # Convert to datatable Frame
        total_xyzi_data_dt = dt.Frame(self.total_xyzi, names=header)
        
        # Round the x,y,z data to reduce the CSV data size
        for col_name in total_xyzi_data_dt.names:
            total_xyzi_data_dt[col_name] = mt.round(total_xyzi_data_dt[col_name], ndigits=6)

        total_xyzi_data_dt["Amiga_timestamp"] = mt.round(total_xyzi_data_dt["Amiga_timestamp"], ndigits=10)
        total_xyzi_data_dt["Lidar_timestamp"] = mt.round(total_xyzi_data_dt["Lidar_timestamp"], ndigits=10)
        
        dt.options.progress.enabled = False
        total_xyzi_data_dt.to_csv(str(csv_path_name_ext), verbose=False)
            
        end_time = time.time()
        
        shared_logger.info(f"LIDAR SickScan Processing: CSV write time : {end_time - start_time:.4f} seconds")
        check_memory_usage('save 5')  
    
    def matched_file_list(self, origin_path: Path, file_part : str) -> list[Path]:
        """
        Not yet required in this derived class
        """
        shared_logger.info("LIDAR SickScan.copy_extra_files() not implemented")
        return []
                
    def copy_extra_files(self, fpath: Path) -> None:
        """
        Not yet required in this derived class
        """
        shared_logger.info("LIDAR SickScan.copy_extra_files() not implemented")
    
    def save_datatable(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
        This save() extracts the x,y,z,i data using and saves as csv using datatable
        e.g.
        Amiga_timestamp,Lidar_timestamp,X,Y,Z,Intensity
        1755152988.142256,1755152988.1121805,1.2043993,-0.8433294,0.0,249.0
        1755152988.142256,1755152988.1121805,1.213824,-0.8473013,0.0,244.0
        1755152988.142256,1755152988.1121805,1.213331,-0.8443362,0.0,253.0
        """
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)
        current_year = str(datetime.now().year)
        phenomate_version = get_version()
        
        # check_memory_usage('extract 3')
        
        user = "Phenomate user" # Creator of the image
        start_time = time.time()
        for index, sickscan_lidar_protobuf_obj in enumerate(self.images):
            
            processed_msg = from_proto(sickscan_lidar_protobuf_obj)

            xyzi_res = self.py_sick_scan_cartesian_point_cloud_msg_to_xy_numpy(
                                processed_msg, index
                )

            # On reading the first data result, compute the shape 
            # of the final data
            if index == 0:
                try:
                    numrows = xyzi_res.shape[0] * self.total_messages
                    shared_logger.info(f"LIDAR SickScan Processing: Allocating numpy array of shape: ({numrows},6)")
                    self.total_xyzi= np.zeros((numrows, 6))
                except MemoryError as ex:
                    shared_logger.error(f"LIDAR SickScan Processing: Error allocating total_xyzi array message: {ex}")
                
            # sum of the Z column, used to check for required 
            # formating when saving to csv - if 0.0 then do not 
            # add extra digits past the decimal
            if xyzi_res is not None:
                self.total_z_sum += np.sum(xyzi_res[:, 2])  

                row_end = self.row_offset + xyzi_res.shape[0]
                # Add the x,y,z,i data
                self.total_xyzi[self.row_offset:row_end, 2:6] = xyzi_res 
                # add the timstamps (repeats the values for each x,y,z,i added from the xyzi_res)
                self.total_xyzi[self.row_offset:row_end, 0:2] = np.array([self.system_timestamps[index],self.msg_timestamp[index]])
                # update the position to the next empty row
                self.row_offset += xyzi_res.shape[0]
        
        end_time = time.time()
        # Print elapsed time
        total_points = self.total_xyzi.shape[0]
        shared_logger.info(f"LIDAR SickScan Processing: Total messages: {self.total_messages} ; Total xyz points: {total_points} ; Points per message: {total_points / self.total_messages}")
        shared_logger.info(f"LIDAR SickScan Processing: Preprocessing time : {end_time - start_time:.4f} seconds")
        check_memory_usage('save 4.0')
        
        
        start_time = time.time() 
        self.filtered_data = False
        csv_path_name_ext = fpath / self.get_output_name(index = None, ext = "csv", details = "datatable_ctypeptr")
        
        header = ["Amiga_timestamp", "Lidar_timestamp", "X", "Y", "Z", "Intensity"]
        # Convert to datatable Frame
        total_xyzi_data_dt = dt.Frame(self.total_xyzi, names=header)
        
        total_xyzi_data_dt["Amiga_timestamp"] = mt.round(total_xyzi_data_dt["Amiga_timestamp"], ndigits=9)
        total_xyzi_data_dt["Lidar_timestamp"] = mt.round(total_xyzi_data_dt["Lidar_timestamp"], ndigits=9)
        total_xyzi_data_dt["X"] = mt.round(total_xyzi_data_dt["X"], ndigits=7)
        total_xyzi_data_dt["Y"] = mt.round(total_xyzi_data_dt["Y"], ndigits=7)
        total_xyzi_data_dt["Z"] = mt.round(total_xyzi_data_dt["Z"], ndigits=7)
        
        dt.options.progress.enabled = False
        if self.total_z_sum == 0.0:
            fmt = ('%.9f', '%.9f',  '%.7f' , '%.7f', '%.1f', '%d')
        else:
            fmt = ('%.9f', '%.9f',  '%.7f' , '%.7f', '%.7f', '%d')
        total_xyzi_data_dt.to_csv(str(csv_path_name_ext), verbose=False)
            
        end_time = time.time()
        # shared_logger.info(f"Saving LIDAR data: {image_path_name_ext}  {utc_datetime}")
        shared_logger.info(f"LIDAR SickScan Processing: CSV write time : {end_time - start_time:.4f} seconds")
        check_memory_usage('save 5')  
    
    
    
    def save_numpy(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
        This save() extracts the x,y,z,i data using a 2D Numpy array
        
        Numpy.savetxt() is a little slow
        """
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)
        current_year = str(datetime.now().year)
        phenomate_version = get_version()
        
        check_memory_usage('save 0')
        
        user = "Phenomate user" # Creator of the image
        start_time = time.time()
        for index, sickscan_lidar_protobuf_obj in enumerate(self.images):
            
            processed_msg = from_proto(sickscan_lidar_protobuf_obj)

            result = self.py_sick_scan_cartesian_point_cloud_msg_to_xy_numpy(
                                processed_msg, index
                )

            if index == 0:
                try:
                    numrows = result.shape[0] * self.total_messages
                    shared_logger.info(f"LIDAR SickScan Processing: Allocating numpy array of shape: ({numrows},6)")
                    self.total_xyzi= np.zeros((numrows, 6))
                except MemoryError as ex:
                    shared_logger.error(f"LIDAR SickScan Processing: Error allocating total_xyzi array message: {ex}")
                
            
            if result is not None:
                self.total_z_sum += np.sum(result[:, 2])  # sum of the Z column, used to check for required formating when saving to csv
                
                # self.total_xyzi = np.vstack((self.total_xyzi, result))
                row_end = self.row_offset + result.shape[0]
                self.total_xyzi[self.row_offset:row_end, 2:6] = result                
                self.total_xyzi[self.row_offset:row_end, 0:2] = np.array([self.system_timestamps[index],self.msg_timestamp[index]])
                # self.total_xyzi[self.row_offset:row_end, 1] = self.msg_timestamp[index]
                
                self.row_offset += result.shape[0]
        
        end_time = time.time()
        # Print elapsed time
        total_points = len(self.total_points_x)
        shared_logger.info(f"LIDAR SickScan Processing: Total messages: {self.total_messages} ; Total xyz points: {total_points} ; Points per message: {total_points / self.total_messages}")
        shared_logger.info(f"LIDAR SickScan Processing: Preprocessing time : {end_time - start_time:.4f} seconds")
        check_memory_usage('save 1')
        
        
        start_time = time.time() 
        self.filtered_data = False
        csv_path_name_ext = fpath / self.get_output_name(index = None, ext = "csv", details = "numpy")
        
        header = ["Amiga_timestamp", "Lidar_timestamp", "X", "Y", "Z", "Intensity"]
        if self.total_z_sum == 0.0:
            fmt = ('%.9f', '%.9f',  '%.7f' , '%.7f', '%.1f', '%d')
        else:
            fmt = ('%.9f', '%.9f',  '%.7f' , '%.7f', '%.7f', '%d')
        np.savetxt(csv_path_name_ext, self.total_xyzi, delimiter=",", header= ",".join(header), comments='', fmt=fmt)
            
        end_time = time.time()
        # shared_logger.info(f"Saving LIDAR data: {image_path_name_ext}  {utc_datetime}")
        shared_logger.info(f"LIDAR SickScan Processing: CSV write time ): {end_time - start_time:.4f} seconds")
        check_memory_usage('save 2')   
    
    
    def py_sick_scan_cartesian_point_cloud_msg_to_xy_numpy(
        self, pointcloud_msg, index=0, start_time=None
    ):
        """
        This method converts the pointcloud_msg to x,y coordinates.
        
        Taken from the Resonate resonatesystems-rs24005-appn-instrument-interfaces git (Bitbucket) 
        project process_lidar_binaryfiles.py file.
        """

        num_fields = pointcloud_msg.fields.size
        msg_fields_buffer = pointcloud_msg.fields.buffer

        # Initialize offsets to None or some default value
        field_offset_x = -1
        field_offset_y = -1
        field_offset_z = -1
        field_offset_intensity = -1

        for n in range(num_fields):
            field_name = ctypesCharArrayToString(msg_fields_buffer[n].name)
            field_offset = msg_fields_buffer[n].offset
            if field_name == "x":
                field_offset_x = msg_fields_buffer[n].offset
            elif field_name == "y":
                field_offset_y = msg_fields_buffer[n].offset
            elif field_name == "z":
                field_offset_z = msg_fields_buffer[n].offset
            elif field_name == "intensity":
                field_offset_intensity = msg_fields_buffer[n].offset

        if (
            field_offset_x is None
            or field_offset_y is None
            or (field_offset_z is None)
        ):
            raise ValueError("LIDAR SickScan Processing: Offsets not assigned correctly.")

        # row_step = width * 16   (16 == 4 x fp32 value - x, y, z, intensity)
        # This is the length in bytes of the full message array
        cloud_data_buffer_len = pointcloud_msg.row_step * pointcloud_msg.height 


        if ( not (
            pointcloud_msg.data.size == cloud_data_buffer_len
            and num_fields == 4
            and field_offset_x == 0
            and field_offset_y == 4
            and field_offset_z == 8
            and field_offset_intensity == 12             
            )
        ):
            raise ValueError("LIDAR SickScan Processing: Data offsets not as expected.")

        total_floats = pointcloud_msg.width * pointcloud_msg.height * 4
        
        # if index < 1:
            # shared_logger.info(f"pointcloud_msg.width     : {pointcloud_msg.width}")
            # shared_logger.info(f"pointcloud_msg.height    : {pointcloud_msg.height}")
            # shared_logger.info(f"total_floats             : {total_floats}")
            # shared_logger.info(f"pointcloud_msg.row_step  : {pointcloud_msg.row_step} bytes")
            # shared_logger.info(f"Type of data.buffer      : {type(pointcloud_msg.data.buffer)}")
            # shared_logger.info(f"Type of data.buffer[{index}]: {type(pointcloud_msg.data.buffer[index])}")
            # shared_logger.info(f" num_fields {num_fields} ;  field_offset_x {field_offset_x} ; field_offset_y {field_offset_y} ; field_offset_z {field_offset_z} ; field_offset_intensity {field_offset_intensity} ;  width {pointcloud_msg.width} ; height {pointcloud_msg.height};  row_step {pointcloud_msg.row_step} ; point_step {pointcloud_msg.point_step}")
        
        try:
            buffer = ctypes.cast(pointcloud_msg.data.buffer, ctypes.POINTER(ctypes.c_float * total_floats)).contents

            points_xyzi_1d =  np.frombuffer(
                            buffer,
                            dtype=np.float32,
                            count=total_floats,
                            offset=0,
                        )
        except Exception as e:
            shared_logger.error(f"LIDAR SickScan Processing: Error reading buffer for message {index}: {e}")
                    
        # map the read in data to a 2D array            
        points_xyzi = points_xyzi_1d.reshape(( pointcloud_msg.width * pointcloud_msg.height, 4))
        
        return points_xyzi
        
        
    def save_original(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
             
        """
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)
        current_year = str(datetime.now().year)
        phenomate_version = get_version()
        
        check_memory_usage('extract 3')
        
        user = "Phenomate user" # Creator of the image
        start_time = time.time()
        for index, sickscan_lidar_protobuf_obj in enumerate(self.images):
            
            processed_msg = from_proto(sickscan_lidar_protobuf_obj)
            # systemtimestamp = self.system_timestamps[index]
            # self.total_messages += 1
            
            # print(f"Amiga Timestamp (converted): {systemtimestamp}")
            # self.msg_timestamp = msg.header.timestamp_sec + msg.header.timestamp_nsec / 1e9 
            # self.msg_data_size = msg.data.size
            # self.msg_data_buffer = msg.data.buffer
            # self.msg_height = msg.height
            # self.msg_width = msg.width
            # npoints =  self.msg_height * self.msg_width
            # self.msg_num_fields = msg.fields.size

            result = self.py_sick_scan_cartesian_point_cloud_msg_to_xy(
                            processed_msg
            )
            if result is not None:
                x_points, y_points, z_points, intensity_points = result
                self.total_points_x.extend(x_points)
                self.total_points_y.extend(y_points)
                self.total_points_z.extend(z_points)
                self.total_points_intensity.extend(intensity_points)
                
                if index == 1:
                    shared_logger.info(f"The type of x is {(x_points.shape)}")

                self.total_timestamps.extend(
                    [
                        self.system_timestamps[index]
                    ] * len(x_points)
                )
                self.total_lidar_timestamps.extend(
                    [
                        self.msg_timestamp[index]
                    ] * len(x_points)
                )
        
        end_time = time.time()
        # Print elapsed time
        total_points = len(self.total_points_x)
        shared_logger.info(f"SickScan total messages: {self.total_messages} ; Total xyz points: {total_points} ; Points per message: {total_points / self.total_messages}")
        shared_logger.info(f"Processing time sickscan_lidar_protobuf): {end_time - start_time:.4f} seconds")
        check_memory_usage('extract 4')
        
        
        start_time = time.time() 
        self.filtered_data = False
        csv_path_name_ext = fpath / self.get_output_name(index = None, ext = "csv", details = "testing")
        header = ["Amiga_timestamp", "Lidar_timestamp", "X", "Y", "Z", "Intensity"]
        with open(
            csv_path_name_ext, "w", encoding="utf-8", newline=""
        ) as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(header)  # Write the header row

            if self.filtered_data:
                for system_time, lidar_time, x, y in zip(
                    self.total_timestamps,
                    self.total_lidar_timestamps,
                    self.total_points_x,
                    self.total_points_y,
                ):
                    writer.writerow([system_time, lidar_time, x, y])
            else:
                for system_time, lidar_time, x, y, z, intensity in zip(
                    self.total_timestamps,
                    self.total_lidar_timestamps,
                    self.total_points_x,
                    self.total_points_y,
                    self.total_points_z,
                    self.total_points_intensity,
                ):
                    writer.writerow(
                        [system_time, lidar_time, x, y, z, intensity]
                    )
            
        end_time = time.time()
        # shared_logger.info(f"Saving LIDAR data: {image_path_name_ext}  {utc_datetime}")
        shared_logger.info(f"Write time CSV sickscan_lidar_protobuf): {end_time - start_time:.4f} seconds")
        check_memory_usage('extract 5')    
            
        
    def py_sick_scan_cartesian_point_cloud_msg_to_xy_original(
        self, pointcloud_msg, start_time=None
    ):
        """
        This method converts the pointcloud_msg to x,y coordinates.
        
        Taken from the Resonate resonatesystems-rs24005-appn-instrument-interfaces git (Bitbucket) 
        project process_lidar_binaryfiles.py file.
        """

        num_fields = pointcloud_msg.fields.size
        msg_fields_buffer = pointcloud_msg.fields.buffer

        # print(f"Num of fields {num_fields}")
        # print(f"msg fields buffer is {msg_fields_buffer}")

        # Initialize offsets to None or some default value
        field_offset_x = -1
        field_offset_y = -1
        field_offset_z = -1
        field_offset_intensity = -1

        for n in range(num_fields):
            field_name = ctypesCharArrayToString(msg_fields_buffer[n].name)
            field_offset = msg_fields_buffer[n].offset
            if field_name == "x":
                field_offset_x = msg_fields_buffer[n].offset
            elif field_name == "y":
                field_offset_y = msg_fields_buffer[n].offset
            elif field_name == "z":
                field_offset_z = msg_fields_buffer[n].offset
            elif field_name == "intensity":
                field_offset_intensity = msg_fields_buffer[n].offset

        if (
            field_offset_x is None
            or field_offset_y is None
            or (not self.filtered_data and field_offset_z is None)
        ):
            raise ValueError("Offsets not assigned correctly.")



        cloud_data_buffer_len = pointcloud_msg.row_step * pointcloud_msg.height

        assert (
            pointcloud_msg.data.size == cloud_data_buffer_len
            and field_offset_x >= 0
            and field_offset_y >= 0
            and field_offset_intensity >= 0
            and (self.filtered_data or field_offset_z >= 0)
        )
        cloud_data_buffer = bytearray(cloud_data_buffer_len)

        for n in range(cloud_data_buffer_len):
            cloud_data_buffer[n] = pointcloud_msg.data.buffer[n]

        points_x = np.zeros(
            pointcloud_msg.width * pointcloud_msg.height, dtype=np.float32
        )
        points_y = np.zeros(
            pointcloud_msg.width * pointcloud_msg.height, dtype=np.float32
        )
        points_intensity = np.zeros(
            pointcloud_msg.width * pointcloud_msg.height, dtype=np.float32
        )
        points_z = None
        if not self.filtered_data:
            points_z = np.zeros(
                pointcloud_msg.width * pointcloud_msg.height, dtype=np.float32
            )
        point_idx = 0

        for row_idx in range(pointcloud_msg.height):
            for col_idx in range(pointcloud_msg.width):
                pointcloud_offset = (
                    row_idx * pointcloud_msg.row_step
                    + col_idx * pointcloud_msg.point_step
                )

                try:
                    points_x[point_idx] = np.frombuffer(
                        cloud_data_buffer,
                        dtype=np.float32,
                        count=1,
                        offset=pointcloud_offset + field_offset_x,
                    )[0]
                    points_y[point_idx] = np.frombuffer(
                        cloud_data_buffer,
                        dtype=np.float32,
                        count=1,
                        offset=pointcloud_offset + field_offset_y,
                    )[0]
                    if points_z is not None:
                        points_z[point_idx] = np.frombuffer(
                            cloud_data_buffer,
                            dtype=np.float32,
                            count=1,
                            offset=pointcloud_offset + field_offset_z,
                        )[0]
                    points_intensity[point_idx] = np.frombuffer(
                        cloud_data_buffer,
                        dtype=np.float32,
                        count=1,
                        offset=pointcloud_offset + field_offset_intensity,
                    )[0]
                except Exception as e:
                    print(f"Error reading buffer at point index {point_idx}: {e}")

                point_idx += 1

        if points_z is not None:
            return points_x, points_y, points_z, points_intensity
        else:
            return points_x, points_y, points_intensity
        
        
    
