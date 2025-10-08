from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

import cv2
from datetime import datetime, timezone

from PIL import Image, PngImagePlugin, __version__
from PIL.TiffImagePlugin import ImageFileDirectory_v2

import tifffile

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
                
    
  
    # PNG data conversion code using PIL   
    def save_png_with_metadata(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)
        
        png_compression = "9"
        png_lib = "pil"
        current_year = str(datetime.now().year)
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
            # utc_datetime = datetime.fromtimestamp(image.timestamp / 1000000, tz=timezone.utc)
            
            tag_270 =  'A plant phenotype experiment image. Image taken by JAI camera protobuffer as a raw Bayer image and converted to standardised RGB using OpenCV cvtColor()'
            tag_274 =  "ORIENTATION.TOPLEFT" # ORIENTATION should be an integer value
            tag_305 =   f'phenomate-core version: {phenomate_version} using Python library PNG writer: {png_lib}, version {__version__}'
            tag_306 =   f'{utc_now}'
            user = "Phenomate user" # 315 Creator of the image
            tag_315 =   f'{user}' 
            tag_33432 = f'Copyright {current_year} Australian Plant Phenomics Network. All rights reserved' 
            tag_65500 =  f'{{ "System_timestamp" : "timestamp from when the image was added to the protocol buffer", "JAI_collection_timestamp" : "JAI counter value when the image was taken" }} '
            tag_65501 += f'{self.system_timestamps[index]}'
            tag_65502 += f'{image.timestamp}'
            tag_65500 += f' "timestamp_description": }} }}'
            
            # Create a PngInfo object to hold metadata
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text("Timestamp_Info", tag_65500)
            metadata.add_text("System_timestamp", tag_65501)
            metadata.add_text("JAI_collection_timestamp", tag_65502)
            metadata.add_text("Description", tag_270)
            metadata.add_text("Orientation", tag_274)
            metadata.add_text("Software", tag_305)
            metadata.add_text("Current_Time", tag_306)
            metadata.add_text("Author", tag_315)
            metadata.add_text("Copyright", tag_33432)
            

            out_image = Image.fromarray(rgb_image)
            png_compression = 0 if png_compression == "none" else int(png_compression)
            image_path_name_ext = fpath / self.get_output_name(image.timestamp, "png",  f"{png_lib}")
            out_image.save(image_path_name_ext, format="PNG", pnginfo=metadata, compress_level=png_compression)
            
            
            # # OpenCV dos not support writing metadata to files
            # image_path_nocompression  = fpath / self.get_output_name(image.timestamp, "png", "nocomp")
            # # Saving as PNG with maximum quality (lossless compression)
            # cv2.imwrite(image_path_nocompression, rgb_image, [cv2.IMWRITE_PNG_COMPRESSION, 0])  # 0 is no compression, 9 is max compression (also lossless)

        
        # End timer
        end_time = time.time()
        # Print elapsed time
        print(f"Execution time (optimizepng_{png_lib} compression): {end_time - start_time:.4f} seconds")  # print statements end as a WARNING in logger output
        shared_logger.info(f"Execution time (optimizepng_{png_lib} compression tiff): {end_time - start_time:.4f} seconds")
        
        
    # if bigtiff=True, 64 bit tag TIFF tifffile else 32 bit 
    def save(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)
        
        current_year = str(datetime.now().year)
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
            # shared_logger.info(f"Converted timestamp (no compression): image.timestamp: {image.timestamp}  {utc_datetime}")
            
            # See site-packages\tifffile\tifffile.py line 16110
            # (4869, 'AndorTemperature'),
            # (4876, 'AndorExposureTime'),
            # (4878, 'AndorKineticCycleTime'),
            # (4879, 'AndorAccumulations'),
            # (4881, 'AndorAcquisitionCycleTime'),
            # (4882, 'AndorReadoutTime'),
            # (4884, 'AndorPhotonCounting'),
            # (4885, 'AndorEmDacLevel'),
            # (4890, 'AndorFrames'),
            # (4896, 'AndorHorizontalFlip'),
            # (4897, 'AndorVerticalFlip'),
            # (4898, 'AndorClockwise'),
            # (4899, 'AndorCounterClockwise'),
            # (4904, 'AndorVerticalClockVoltage'),
            # (4905, 'AndorVerticalShiftSpeed'),
            # (4907, 'AndorPreAmpSetting'),
            # (4908, 'AndorCameraSerial'),
            # (4911, 'AndorActualTemperature'),
            # (4912, 'AndorBaselineClamp'),
            # (4913, 'AndorPrescans'),
            # (4914, 'AndorModel'),
            # (4915, 'AndorChipSizeX'),
            # (4916, 'AndorChipSizeY'),
            # (4944, 'AndorBaselineOffset'),
            # (4966, 'AndorSoftwareVersion'),

            # | Tag Name               | Tag ID (Hex) | Description                                 |
            # |------------------------|--------------|---------------------------------------------|
            # | `GPSLatitudeRef`       | `0x0001`     | North or South latitude indicator (`N`/`S`) |
            # | `GPSLatitude`          | `0x0002`     | Latitude in degrees, minutes, seconds       |
            # | `GPSLongitudeRef`      | `0x0003`     | East or West longitude indicator (`E`/`W`)  |
            # | `GPSLongitude`         | `0x0004`     | Longitude in degrees, minutes, seconds      |
            # | `GPSAltitudeRef`       | `0x0005`     | Altitude reference (0 = above sea level)    |
            # | `GPSAltitude`          | `0x0006`     | Altitude in meters                          |
            # | `GPSTimeStamp`         | `0x0007`     | Time of GPS fix                             |
            # | `GPSDateStamp`         | `0x001D`     | Date of GPS fix                             |

            # {
              # "GPSLatitudeRef": "N",
              # "GPSLatitude": [34, 3, 30.12],
              # "GPSLongitudeRef": "E",
              # "GPSLongitude": [118, 14, 55.32]
            # }

            # Convert the reshaped image data to a PIL Image object
            # out_image = Image.fromarray(rgb_image)
            
            # (65001, 'Q', 1, image.timestamp, True),  # Example 64-bit tag
            # (65002, 'Q', 1, self.system_timestamps[index], True),  
            # Define a 64-bit custom tag
            # Format: (tag_number, dtype, count, value, writeonce)
            # dtype  = 'Q' for unsigned 64-bit integer
            # writeonce = True means it will be written only once
            
            tag_270 =  '"A plant phenotype experiment image. Image is taken by JAI camera protobuffer object raw Bayer image to standardised RGB"'
            tag_269 =  f'"title":"Phenomate JAI output",  "software": "phenomate-core {phenomate_version}", '
            # 
            tag_274 =  tifffile.ORIENTATION.TOPLEFT # ORIENTATION should be an integer value
            # tag_305 =   f'phenomate-core {phenomate_version}'
            tag_306 =   f'{utc_now}'
            # mf = 10000000   # muliplication factor for timestamp 
            tag_33432 = f'"Copyright {current_year} Australian Plant Phenomics Network. All rights reserved"' 
            tag_65000 = f'{{ "timestamp_description": "system_timestamp"" : "The system timestamp that the image was added to the protocol buffer", "jai_collection_timestamp": "The JAI camera counter value when the image was taken" }}'             
            tag_65001 = f'{{ "system_timestamp": "{self.system_timestamps[index]}" }}'
            tag_65002 = f'{{ "jai_collection_timestamp": "{image.timestamp}" }} '
           
            extratags = [
                (269, 's', len(tag_269) + 1, tag_269, True),  # 269 DocumentName
                # (270, 's', len(tag_270) + 1, tag_270, True), # Use the description parameter in the tifffile.imwrite() method
                (274, 'I', 1               , tag_274, True),  # 274 Image orientation
                # (305, 's', len(tag_305) + 1, tag_305, True), # 305 software version - tifffile adds its own name here.
                (306, 's', len(tag_306) + 1, tag_306, True),  # 306 Creation time
                # (315, 's', 1, f'{}', True),  # 315 Creator of the image
                (33432, 's', len(tag_33432) + 1, tag_33432, True),  # 33432 Copyright information
                (65000, 's', len(tag_65000) + 1, tag_65000, True),
                # (65001, 'Q', 1, image.timestamp, True),  # For 64 bit tags are enabled by bigtiff=True
                (65001, 's', len(tag_65001) + 1, tag_65001, True),
                (65002, 's', len(tag_65002) + 1, tag_65002, True),
                # (65003, 'd', 1, self.system_timestamps[index], True), # For 64 bit tags are enabled by bigtiff=True
            ]
            
            image_path_name_ext = fpath / self.get_output_name(index = image.timestamp, ext = "tiff", details = "none_notbigtiff")
            shared_logger.info(f"Saving file with tifffile library: {image_path_name_ext}  {utc_datetime}")
            # Write BigTIFF with ZSTD compression and custom tag
            tifffile.imwrite(
                f'{image_path_name_ext}',
                rgb_image,
                bigtiff=False,
                compression='none',
                description = tag_270,
                extratags=extratags,
            )

        # End timer
        end_time = time.time()
        # Print elapsed time
        print(f"Execution time (tifffile no compression not bigtiff): {end_time - start_time:.4f} seconds")  # print statements end as a WARNING in logger output
        shared_logger.info(f"Execution time (tifffile no compression not bigtiff): {end_time - start_time:.4f} seconds")
        
        
    # The 32 bit TIFF PIL writer code
    def save_32bit_tiff(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)
        png_lib = "pil"
        tiff_compression = "9"
        tiff_lib = "pil"
        current_year = str(datetime.now().year)
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
            # utc_datetime = datetime.fromtimestamp(image.timestamp / 1000000, tz=timezone.utc)
            
            tag_270 =  'A plant phenotype experiment image. Image taken by JAI camera protobuffer as a raw Bayer image and converted to standardised RGB using OpenCV cvtColor() and save as Tiff using tifffile library'
            tag_274 =  tifffile.ORIENTATION.TOPLEFT # ORIENTATION should be an integer value
            tag_305 =   f'phenomate-core version: {phenomate_version} using Python library PNG writer: {png_lib}, version {__version__}'
            tag_306 =   f'{utc_now}'
            user = "Phenomate user" # 315 Creator of the image
            tag_315 =   f'{user}' 
            tag_33432 = f'Copyright {current_year} Australian Plant Phenomics Network. All rights reserved' 
            tag_65000 = f'{{ "timestamp_description" : "system_timestamp is the time that the image was added to the protocol buffer; jai_collection_timestamp is the JAI camera counter value when the image was taken" }}'             
            tag_65001 = f'{{ "system_timestamp" : "{self.system_timestamps[index]}" }}'
            tag_65002 = f'{{ "jai_collection_timestamp" : "{image.timestamp}" }}'
            
            metadata = {
                269: tag_269,
                270: tag_270,
                274: tag_274,
                305: tag_305,
                306: tag_306,
                315: tag_315,
                33432: tag_33432,
                65000: tag_65000,
                65001: tag_65001,
                65002: tag_65002,
            }
            
            # Convert the reshaped image data to a PIL Image object
            
            out_image = Image.fromarray(rgb_image)
            image_path_name_ext = fpath / self.get_output_name(image.timestamp, "tiff",  f"{tiff_compression}_{tiff_lib}")
            out_image.save(image_path_name_ext, format="TIFF", tiffinfo=metadata, compression= None if tiff_compression == "none" else tiff_compression)  # tiff_adobe_deflate tiff_jpeg
            
           
            
            # # OpenCV dos not support writing metadata to files
            # image_path_nocompression  = fpath / self.get_output_name(image.timestamp, "png", "nocomp")
            # # Saving as PNG with maximum quality (lossless compression)
            # cv2.imwrite(image_path_nocompression, rgb_image, [cv2.IMWRITE_PNG_COMPRESSION, 0])  # 0 is no compression, 9 is max compression (also lossless)

        
        # End timer
        end_time = time.time()
        # Print elapsed time
        print(f"Execution time (optimizepng_{tiff_lib} compression): {end_time - start_time:.4f} seconds")  # print statements end as a WARNING in logger output
        shared_logger.info(f"Execution time (optimizepng_{tiff_lib} compression tiff): {end_time - start_time:.4f} seconds")
        
        
