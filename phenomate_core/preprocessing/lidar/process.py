from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from datetime import datetime, timezone
import time

from phenomate_core.preprocessing.base import BasePreprocessor
from phenomate_core.preprocessing.lidar import lidar_pb2


# We can set this as a environment variable SICKSCAN_LIB_PATH?
path_to_sickscan_install = '/home/jbowden/local'

sys.path.append(
    os.path.abspath(
        os.path.join(
             path_to_sickscan_install, '/include/sick_scan_xd'
        )
    )
)
import sick_scan_api
# This file is from the Resonate bitbucket library and requires a path to the compiled 
# SickScan shared library "libsick_scan_xd_shared_lib.so"
from reading_proto_buff import from_proto



# from phenomate_core.get_logging import shared_logger
import logging
shared_logger = logging.getLogger('celery')
from phenomate_core.get_version import get_version


class LidarPreprocessor(BasePreprocessor[lidar_pb2.SickScanPointCloudMsg]):
    """
    lidar_pb2.SickScanPointCloudMsg is the self.images list type
    
    Procedure edited from the Resonate resonatesystems-rs24005-appn-instrument-interfaces git (Bitbucket) 
    project process_lidar_binaryfiles.py file.
        
    """

    def extract(self, **kwargs: Any) -> None:
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
                sickscan_lidar_protobuf_obj = lidar_pb2.SickScanPointCloudMsg()
                sickscan_lidar_protobuf_obj.ParseFromString(serialized_lidar_msg)
                processed_msg = from_proto(sickscan_lidar_protobuf_obj)

                # Update to extracted image list
                self.images.append(sickscan_lidar_protobuf_obj)
                self.system_timestamps.append(system_timestamp)
                
                shared_logger.info(f"Converted timestamp: system_timestamp:{system_timestamp} image.timestamp: {sickscan_lidar_protobuf_obj.timestamp} framerate: {sickscan_lidar_protobuf_obj.frame_rate}")
                
                
   
    def save(
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
        user = "Phenomate user" # Creator of the image
        start_time = time.time()
        for index, image in enumerate(self.images):
            
            image_path_name_ext = fpath / self.get_output_name(index = image.timestamp, ext = "csv", details = f"{}")
            shared_logger.info(f"Saving file with tifffile library: {image_path_name_ext}  {utc_datetime}")
            
        # End timer
        end_time = time.time()
        # Print elapsed time
        shared_logger.info(f"Write time (tifffile {compression_l} not bigtiff): {end_time - start_time:.4f} seconds")
        
        
    def py_sick_scan_cartesian_point_cloud_msg_to_xy(
        self, pointcloud_msg, start_time=None
    ):
        """
        This method converts the pointcloud_msg to x,y coordinates.
        
        Taken from the Resonate resonatesystems-rs24005-appn-instrument-interfaces git (Bitbucket) 
        project process_lidar_binaryfiles.py file.
        """

        num_fields = pointcloud_msg.fields.size
        msg_fields_buffer = pointcloud_msg.fields.buffer

        print(f"Num of fields {num_fields}")
        print(f"msg fields buffer is {msg_fields_buffer}")

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

        if self.filtered_data:
            print(
                f"Field offsets - X: {field_offset_x}, Y: {field_offset_y}, Intensity : {field_offset_intensity}"
            )
        else:
            print(
                f"Field offsets - X: {field_offset_x}, Y: {field_offset_y},"
                f"Z: {field_offset_z}, Intensity : {field_offset_intensity}"
            )

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
        
