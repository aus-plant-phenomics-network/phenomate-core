from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

import cv2
from datetime import datetime, timezone

from PIL import Image
from PIL.TiffImagePlugin import ImageFileDirectory_v2

from phenomate_core.preprocessing.base import BasePreprocessor
from phenomate_core.preprocessing.jai import jai_pb2

import time


# from phenomate_core.get_logging import shared_logger
import logging
shared_logger = logging.getLogger('celery')
from phenomate_core.get_version import get_version


class JaiPreprocessor(BasePreprocessor[jai_pb2.JAIImage]):
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
                length = int.from_bytes(length_bytes, byteorder="little")

                # Read the serialized message
                serialized_image = file.read(length)

                # Parse the protobuf message
                image_protobuf_obj = jai_pb2.JAIImage()
                image_protobuf_obj.ParseFromString(serialized_image)

                # Update to extracted image list
                self.images.append(image_protobuf_obj)
                self.system_timestamps.append(system_timestamp)
                
                
                # bytes_be = image_protobuf_obj.timestamp / 1000000000
                utc_datetime = datetime.fromtimestamp(image_protobuf_obj.timestamp / 1000000, tz=timezone.utc)
                # # On x86_64 (little-endian system)
                # value_le = int.from_bytes(bytes_be, byteorder='big')  # Must match original byte order
                # # value_le_flt = float.from_bytes(bytes_be, byteorder='big')
                # value_le_flt = struct.unpack('<d', bytes_be)[0]  # Big-endian double
                value_le_flt = 0
                value_le =  image_protobuf_obj.frame_rate
                # utc_datetime = datetime.utcfromtimestamp(system_timestamp)
                # print("Human-readable time:", dt)
                # utc_datetime = datetime.fromtimestamp(system_timestamp / 1000000, tz=timezone.utc)
                shared_logger.info(f"Converted timestamp: system_timestamp:{system_timestamp} image.timestamp: {image_protobuf_obj.timestamp} {value_le_flt} {value_le} {utc_datetime}")
                
    
    """def decode_varint(data):
        result = 0
        shift = 0
        for byte in data:
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
        return result

            
    def extract(self, **kwargs: Any) -> None:
        with self.path.open("rb") as file:
            while True:
                # Read the length prefix (varint)
                length_bytes = []
                while True:
                    byte = f.read(1)
                    if not byte:
                        return messages  # End of file
                    length_bytes.append(byte[0])
                    if byte[0] < 128:
                        break
                length = decode_varint(length_bytes)


                # Read the serialized message
                serialized_image = file.read(length)

                # Parse the protobuf message
                image_protobuf_obj = jai_pb2.JAIImage()
                image_protobuf_obj.ParseFromString(serialized_image)

                # Update to extracted image list
                self.images.append(image_protobuf_obj)
                self.system_timestamps.append(system_timestamp)
                
                utc_datetime = datetime.fromtimestamp(system_timestamp / 1000000, tz=timezone.utc)
                shared_logger.info(f"Converted timestamp: serialized_timestamp:{serialized_timestamp} image.timestamp: {image_protobuf_obj.timestamp} {utc_datetime}")
    """        

    def save(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)
        
        phenomate_version = get_version()
        start_time = time.time()
        for index, image in enumerate(self.images):
            # Determine width and height
            iwidth = width if width is not None else image.width
            iheight = height if height is not None else image.height
            bayer_image = self.bytes_to_numpy(image.image_data).reshape((iheight, iwidth))
            
            # Conversion to use after discussion in #https://github.com/aus-plant-phenomics-network/phenomate-core/issues/2
            # rgb_image = cv2.cvtColor(bayer_image, cv2.COLOR_BayerRGGB2BGR)  # Use this if saving with cv2.imwrite
            rgb_image = cv2.cvtColor(bayer_image, cv2.COLOR_BayerRGGB2RGB)
            
            utc_now = datetime.now(timezone.utc)
            utc_datetime = datetime.fromtimestamp(image.timestamp / 1000000, tz=timezone.utc)
            shared_logger.info(f"Converted timestamp (no compression): image.timestamp: {image.timestamp}  {utc_datetime}")
            
            metadata = {
                270: "Description: Phenomate JAI camera conversion from protobuffer object to standardised output images",
                305: f"phenomate-core {phenomate_version}",
                306: f"{utc_now}",
                65000: "tag 65001 and 65002 are the timestamp from JAI camera",
                # 65001: image.timestamp,
                65002: f"{utc_datetime}",
            }
            
            # Convert the reshaped image data to a PIL Image object
            out_image = Image.fromarray(rgb_image)
            image_path_name_ext = fpath / self.get_output_name(image.timestamp, "tiff",  "none")
            out_image.save(image_path_name_ext, format="TIFF", tiffinfo=metadata, compression=None)  # tiff_adobe_deflate tiff_jpeg
            
            # out_image = Image.fromarray(rgb_image)
            # image_path_name_ext = fpath / self.get_output_name(image.timestamp, "png",  "9compression")
            # out_image.save(image_path_name_ext, format="PNG", compress_level=9)
            
            """
            # Thsi code block requires bigTiff support - which is not the default in PIL
            tiff_tags = ImageFileDirectory_v2()

            # Set the tag with type 'Q' (unsigned 64-bit integer)
            tiff_tags[65000] = image.timestamp 
            tiff_tags.tagtype[65000] = 16  # 16 = TIFF LONG8 (64-bit unsigned int) #  bigtiff=True

            # Save the image with the custom tag
            # image.save("custom_tag.tiff", tiffinfo=tiff_tags)
            out_image = Image.fromarray(rgb_image)
            image_path_name_ext = fpath / self.get_output_name(image.timestamp, "tiff",  "nocompression")
            out_image.save(image_path_name_ext, format="TIFF", tiffinfo=tiff_tags, compression="none")
            """
            
            # # OpenCV dos not support writing metadata to files
            # image_path_nocompression  = fpath / self.get_output_name(image.timestamp, "png", "nocomp")
            # # Saving as PNG with maximum quality (lossless compression)
            # cv2.imwrite(image_path_nocompression, rgb_image, [cv2.IMWRITE_PNG_COMPRESSION, 0])  # 0 is no compression, 9 is max compression (also lossless)

        
        # End timer
        end_time = time.time()
        # Print elapsed time
        print(f"Execution time (no compression): {end_time - start_time:.4f} seconds")  # print statements end as a WARNING in logger output
        shared_logger.info(f"Execution time (no compression tiff): {end_time - start_time:.4f} seconds")
        
        """start_time = time.time()     
        for index, image in enumerate(self.images):
            # Determine width and height
            iwidth = width if width is not None else image.width
            iheight = height if height is not None else image.height
            bayer_image = self.bytes_to_numpy(image.image_data).reshape((iheight, iwidth))
            
            # Conversion to use after discussion in #https://github.com/aus-plant-phenomics-network/phenomate-core/issues/2
            # rgb_image = cv2.cvtColor(bayer_image, cv2.COLOR_BayerRGGB2BGR)  # Use this if saving with cv2.imwrite
            rgb_image = cv2.cvtColor(bayer_image, cv2.COLOR_BayerRGGB2RGB)
            
            utc_now = datetime.now(timezone.utc)
            utc_datetime = datetime.fromtimestamp(image.timestamp / 1000000, tz=timezone.utc)
            shared_logger.info(f"Converted timestamp: {utc_datetime}")
            metadata = {
                270: "Description: Phenomate JAI camera conversion from protobuffer object to standardised output images",
                305: f"phenomate-core {phenomate_version}",
                306: f"{utc_now}",
                65000: "tag 65001 and 65002 are the timestamp from JAI camera",
                65001: image.timestamp,
                65002: f"{utc_datetime}",
            }
            
            # Convert the CV2 image data to a PIL Image object
            out_image = Image.fromarray(rgb_image)
            image_path_name_ext = fpath / self.get_output_name(image.timestamp, "tiff",  "deflatecompression")
            out_image.save(image_path_name_ext, format="TIFF", tiffinfo=metadata, compression="deflate")
            
            # # OpenCV dos not support writing metadata to files
            # image_path_maxcompression = fpath / self.get_output_name(image.timestamp, "png", "maxcomp"))
            # # Saving as PNG with full compression (lossless compression)
            # cv2.imwrite(image_path_maxcompression, rgb_image, [cv2.IMWRITE_PNG_COMPRESSION, 9])  # 0 is lossless, 9 is max compression
            
        # End timer
        end_time = time.time()
        # Print elapsed time
        print(f"Execution time (full compression tiff): {end_time - start_time:.4f} seconds")
        shared_logger.info(f"Execution time (lzw compression tiff): {end_time - start_time:.4f} seconds")
        """
