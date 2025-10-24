from __future__ import annotations

import logging
import struct
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import tifffile
from PIL import Image, PngImagePlugin, __version__

from phenomate_core.get_version import get_version
from phenomate_core.preprocessing.base import BasePreprocessor
from phenomate_core.preprocessing.jai import jai_pb2

shared_logger = logging.getLogger("celery")


class JaiPreprocessor(BasePreprocessor[jai_pb2.JAIImage]):
    r"""Average Timing  and compression results (per image for 17 images) extracted from
    protobuffer file and saved with equivalent metadata.
    +-----------+----------------------------------+------------------+-----------------+-------------+------------------------+
    | Library   | Compression Method               | Write Time (s)   | Read Time (s)   | Size (MB)   | Notes                  |
    +===========+==================================+==================+=================+=============+========================+
    | tifffile  | none (not bigtiff)               | 0.0248           | 0.0329          | 35.53       |                        |
    +-----------+----------------------------------+------------------+-----------------+-------------+------------------------+
    | tifffile  | zstd (not bigtiff)               | 0.0689           | 0.0616          | 32.65       | Unreadable on Windows  |
    +-----------+----------------------------------+------------------+-----------------+-------------+------------------------+
    | tifffile  | jpeg2000 (not bigtiff)           | 1.2594           | 1.0774          | 17.71       | Unreadable on Windows  |
    +-----------+----------------------------------+------------------+-----------------+-------------+------------------------+
    | tifffile  | webp (not bigtiff)               | 4.6053           | 0.1284          | 19.65       | Unreadable on Windows  |
    +-----------+----------------------------------+------------------+-----------------+-------------+------------------------+
    | tifffile  | lzma (not bigtiff)               | 3.4209           | 0.4254          | 27.18       | Unreadable on Windows  |
    +-----------+----------------------------------+------------------+-----------------+-------------+------------------------+
    | PIL PNG   | png_pil (compression level 9)    | 2.8894           | 0.4572          | 21.76       |                        |
    +-----------+----------------------------------+------------------+-----------------+-------------+------------------------+
    | PIL PNG   | png_pil (compression level 0)    | 0.6047           | 0.2834          | 35.59       |                        |
    +-----------+----------------------------------+------------------+-----------------+-------------+------------------------+
    | PIL TIFF  | raw                              | 0.0455           | 0.0341          | 35.59       |                        |
    +-----------+----------------------------------+------------------+-----------------+-------------+------------------------+
    | PIL TIFF  | tiff_lzw                         | 0.5706           | 0.1503          | 40.94       |  Increases the size    |
    +-----------+----------------------------------+------------------+-----------------+-------------+------------------------+
    | PIL TIFF  | tiff_deflate                     | 0.9058           | 0.0992          | 32.47       |                        |
    +-----------+----------------------------------+------------------+-----------------+-------------+------------------------+

    As the tifffile library has the fastest read and write speed for uncompressed
    data I am going to use it as the default format. This gives the benefit that
    bigTIFF file support will also be available, which will be useful in the case
    that large stiched images result in >4GB data sizes.


    ToDo: Confirmation of copyright note is needed.
    ToDo: Further metadata should be added (Username / Institution ROR


    Some further Tiff tags of interest:
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
                length = int.from_bytes(length_bytes, byteorder="little")

                # Read the serialized message
                serialized_image = file.read(length)

                # Parse the protobuf message
                image_protobuf_obj = jai_pb2.JAIImage()
                image_protobuf_obj.ParseFromString(serialized_image)

                # Update to extracted image list
                self.images.append(image_protobuf_obj)
                self.system_timestamps.append(system_timestamp)

                shared_logger.info(
                    f"Converted timestamp: system_timestamp:{system_timestamp} image.timestamp: {image_protobuf_obj.timestamp} framerate: {image_protobuf_obj.frame_rate}"
                )

    # Set bigtiff=True, for 64 bit TIFF  tags
    def save(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Save the data using the tifffile package.
        N.B. Only the Compression='none' output files are read natively by Windows
        """
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)

        current_year = str(datetime.now(UTC).year)
        phenomate_version = get_version()
        user = "Phenomate user"  # 315 Creator of the image
        start_time = time.time()
        for index, image in enumerate(self.images):
            # Determine width and height
            iwidth = width if width is not None else image.width
            iheight = height if height is not None else image.height
            bayer_image = self.bytes_to_numpy(image.image_data).reshape((iheight, iwidth))

            # Conversion to use after discussion in #https://github.com/aus-plant-phenomics-network/phenomate-core/issues/2
            # rgb_image = cv2.cvtColor(bayer_image, cv2.COLOR_BayerRGGB2BGR)  # Use this if saving with cv2.imwrite
            rgb_image = cv2.cvtColor(bayer_image, cv2.COLOR_BayerRGGB2RGB)

            # utc_now = datetime.now(UTC)
            tiff_date = datetime.now(UTC).strftime("%Y:%m:%d %H:%M:%S")
            utc_datetime = datetime.fromtimestamp(image.timestamp / 1000000, tz=UTC)
            # shared_logger.info(f"Converted timestamp (no compression): image.timestamp: {image.timestamp}  {utc_datetime}")

            tag_269 = f'"title":"Phenomate JAI output",  "software": "phenomate-core {phenomate_version}", '
            tag_270 = '"A plant phenotype experiment image. Source image is JAI camera protobuffer object raw Bayer image. Output converted using OpenCV.cvtColor() and saved using the tifffile library"'
            tag_274 = tifffile.ORIENTATION.TOPLEFT  # ORIENTATION should be an integer value
            # tag_305 = # tifffile adds its own name here.
            tag_306 = f"{tiff_date}"
            tag_315 = f"{user}"
            tag_33432 = f'"Copyright {current_year} Australian Plant Phenomics Network. All rights reserved"'
            tag_65000 = '{ "timestamp_description": "system_timestamp"" : "The system timestamp that the image was added to the protocol buffer", "jai_collection_timestamp": "The JAI camera counter value when the image was taken" }'
            tag_65001 = f'{{ "system_timestamp": "{self.system_timestamps[index]}" }}'
            tag_65002 = f'{{ "jai_collection_timestamp": "{image.timestamp}" }} '

            extratags = [
                (269, "s", len(tag_269) + 1, tag_269, True),  # 269 DocumentName
                # (270, 's', len(tag_270) + 1, tag_270, True),      # Use the description parameter in the tifffile.imwrite() method
                (274, "I", 1, tag_274, True),  # 274 Image orientation
                # (305, 's', len(tag_305) + 1, tag_305, True),      # 305 software version - tifffile adds its own name here.
                (306, "s", len(tag_306) + 1, tag_306, True),  # 306 Creation time
                (315, "s", len(tag_315) + 1, tag_315, True),  # 315 Creator of the image
                (33432, "s", len(tag_33432) + 1, tag_33432, True),  # 33432 Copyright information
                (65000, "s", len(tag_65000) + 1, tag_65000, True),
                # (65001, 'Q', 1, image.timestamp, True),           # For 64 bit tags are enabled by bigtiff=True
                (65001, "s", len(tag_65001) + 1, tag_65001, True),
                (65002, "s", len(tag_65002) + 1, tag_65002, True),
            ]

            compression_l = "none"  # lossless: lzma  zstd   compressionargs={'lossless': True} not available: bzip2 lz4 ; slow: jpeg2000, webp

            image_path_name_ext = fpath / self.get_output_name(
                index=image.timestamp, ext="tiff", details=f"{compression_l}_tifffile"
            )
            shared_logger.info(
                f"Saving file with tifffile library: {image_path_name_ext}  {utc_datetime}"
            )
            # Write tiff image file

            tifffile.imwrite(
                f"{image_path_name_ext}",
                rgb_image,
                bigtiff=False,
                planarconfig="contig",  # This is the default interleaved rgb format.
                compression=compression_l,
                # compression='jpeg | jpeg2000' , compressionargs={'level': 100},   # JPEG quality level (0 to 100) 0 is lower quality
                # compressionargs={'lossless': True},  # webp quality level
                description=tag_270,
                extratags=extratags,
                photometric="rgb",
            )

        # End timer
        end_time = time.time()
        # Print elapsed time
        shared_logger.info(
            f"Write time (tifffile {compression_l} not bigtiff): {end_time - start_time:.4f} seconds"
        )

    # PNG data conversion code using PIL save_png_with_metadata_with_PIL()
    def save_png_with_metadata_with_PIL(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        """PNG format is lossless and the high compression ratio makes it a good archival
        format, however it is relatively slow, even without compression.
        """
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)

        png_compression = "0"
        png_lib = "pil"
        current_year = str(datetime.now(UTC).year)
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

            utc_now = datetime.now(UTC)

            tag_270 = "A plant phenotype experiment image. Image taken by JAI camera protobuffer as a raw Bayer image and converted to standardised RGB using OpenCV cvtColor()"
            tag_274 = "ORIENTATION.TOPLEFT"  # ORIENTATION should be an integer value
            tag_305 = f"phenomate-core version: {phenomate_version} using Python library PNG writer: {png_lib}, version {__version__}"
            tag_306 = f"{utc_now}"
            user = "Phenomate user"  # 315 Creator of the image
            tag_315 = f"{user}"
            tag_33432 = (
                f"Copyright {current_year} Australian Plant Phenomics Network. All rights reserved."
            )
            tag_65500 = 'timestamp_description: "System_timestamp: timestamp from when the image was added to the protocol buffer", "JAI_collection_timestamp: JAI counter value when the image was taken" } '
            tag_65501 = f"{self.system_timestamps[index]}"
            tag_65502 = f"{image.timestamp}"

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
            image_path_name_ext = fpath / self.get_output_name(
                image.timestamp, "png", f"compress{png_compression}_{png_lib}_"
            )
            out_image.save(
                image_path_name_ext, format="PNG", pnginfo=metadata, compress_level=png_compression
            )

        # End timer
        end_time = time.time()
        # Print elapsed time
        shared_logger.info(
            f"Write time ({png_lib} {png_compression} compression tiff): {end_time - start_time:.4f} seconds"
        )

    # The 32 bit TIFF PIL writer code save_tiff_with_PIL()
    def save_tiff_with_PIL(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Tiff writer with added Tag metadata and custom Tag values 65001, 65002 for image collection timestamps

        # Timing for 17 images :
        # Write time (tiff_lzw pil tiff)    : 9.6995 seconds;  reading (lzw_pil.tiff images)    : 2.5557 seconds; 696MB
        # Write time (raw pil tiff)         : 0.7733 seconds;  reading (raw_pil.tiff images)    : 0.5805 seconds; 605MB
        # Write time (tiff_deflate pil tiff): 15.3987 seconds; reading (deflate_pil.tiff images): 1.6871 seconds; 552MB
        """
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)
        tiff_compression = "tiff_deflate"  # "tiff_deflate" "raw" "jpeg"
        image_lib = "pil"
        current_year = str(datetime.now(UTC).year)
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

            # utc_now = datetime.now(timezone.utc)
            tiff_date = datetime.now(UTC).strftime(
                "%Y:%m:%d %H:%M:%S"
            )  # This is a required format for the tiff date/time tag

            tag_269 = '"Phenomate JAI output"'
            tag_270 = f'"A plant phenotype experiment image. Source image is JAI camera protobuffer object raw Bayer image. Output converted using OpenCV.cvtColor() and saved using the PIL library with compression: {tiff_compression}"'
            tag_274 = tifffile.ORIENTATION.TOPLEFT  # ORIENTATION should be an integer value
            tag_305 = f"phenomate-core version: {phenomate_version} written using Python library PIL version {__version__}"
            tag_306 = f"{tiff_date}"
            user = "Phenomate user"  # 315 Creator of the image
            tag_315 = f"{user}"
            tag_33432 = (
                f"Copyright {current_year} Australian Plant Phenomics Network. All rights reserved"
            )
            tag_65000 = '{ "timestamp_description" : "system_timestamp is the time that the image was added to the protocol buffer; jai_collection_timestamp is the JAI camera counter value when the image was taken" }'
            tag_65001 = f"{self.system_timestamps[index]}"
            tag_65002 = f"{image.timestamp}"

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
            out_image = Image.fromarray(rgb_image).convert("RGB")
            image_path_name_ext = fpath / self.get_output_name(
                image.timestamp, "tiff", f"{tiff_compression}_{image_lib}"
            )
            out_image.save(
                image_path_name_ext,
                format="TIFF",
                tiffinfo=metadata,
                compression=None if tiff_compression == "none" else tiff_compression,
            )  # tiff_adobe_deflate tiff_jpeg

        # End timer
        end_time = time.time()
        # Print elapsed time
        shared_logger.info(
            f"Write time ({tiff_compression} {image_lib} tiff): {end_time - start_time:.4f} seconds"
        )
