"""This script reads the binary file containing the hyperspectral
images and writes the images to an ENVI file.
Also as the data is packed in Mono12p format,
it unpacks the data to 16-bit unsigned integer format.
"""

from __future__ import annotations

import csv
import struct
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from spectral.io import envi

from phenomate_core.preprocessing.base import BasePreprocessor
from phenomate_core.preprocessing.hyperspec import hyperspec_pb2 as hs_pb2

if TYPE_CHECKING:
    from numpy.typing import NDArray

DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 224


class HyperspecPreprocessor(BasePreprocessor[hs_pb2.HyperSpecImage]):
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
                image_protobuf_obj = hs_pb2.HyperSpecImage()
                image_protobuf_obj.ParseFromString(serialized_image)

                # amiga_timestamp = image_protobuf_obj.timestamp_info

                # # Convert the image data back to numpy.ndarray
                self.images.append(image_protobuf_obj)
                self.system_timestamps.append(system_timestamp)

    @staticmethod
    def unpack_mono12packed_to_16bit(
        packed_data: NDArray[np.uint8], width: int, height: int
    ) -> NDArray[np.uint16]:
        """Unpack Mono12p packed data to 16-bit unsigned integer format."""

        # Reshape packed_data to separate each set of 3 bytes
        packed_data = packed_data.reshape(-1, 3)

        # Unpack the first 12 bits into the first 16-bit value
        first_pixels = (packed_data[:, 0].astype(np.uint16) << 4) | (packed_data[:, 1] >> 4)

        # Unpack the remaining 12 bits into the second 16-bit value
        second_pixels = (packed_data[:, 2].astype(np.uint16) << 4) | (packed_data[:, 1] & 0x0F)

        # Interleave the unpacked data into a single array
        unpacked_data = np.zeros(width * height, dtype=np.uint16)
        unpacked_data[0::2] = first_pixels
        unpacked_data[1::2] = second_pixels

        # Reshape to height, width
        return unpacked_data[: width * height].reshape(height, width)

    def write_to_envi_file(self, path: Path, width: int, height: int) -> None:
        """This function writes the hyperspectral images to an ENVI file."""
        envi_filename = path / self.get_output_name(None, "hdr")

        num_images = len(self.images) - 1  # Number of images
        num_samples = self.images[0].width
        num_bands = self.images[0].height

        md = {
            "lines": num_images,  # Rows
            "samples": num_samples,  # Columns
            "bands": num_bands,  # image's spectral dimensionality
            "data type": 12,  # ENVI data type for 16-bit integer
            "interleave": "bil",
            "byte order": 1,
        }
        envi_image = envi.create_image(envi_filename, md, interleave="bil", ext="raw")  # type: ignore[no-untyped-call]

        envi_memmap = envi_image.open_memmap(interleave="bil", writable=True)

        for index in range(num_images):
            packed_data = self.bytes_to_numpy(self.images[index].image_data)
            unpacked_data = self.unpack_mono12packed_to_16bit(packed_data, width, height)
            envi_memmap[index, :, :] = unpacked_data

    def write_to_csv_file(self, path: Path, **kwargs: Any) -> None:
        """This function writes the information of the hyperspectral images
        to a CSV file.
        """
        headers = [
            "system_timestamp",
            "width",
            "height",
            "frame_rate",
            "blockid",
            "bandwidth",
            "image_timestamp",
        ]
        file_path = path / self.get_output_name(None, "csv")
        with file_path.open("w", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(headers)
            for system_timestamp, image in zip(self.system_timestamps, self.images, strict=False):
                writer.writerow(
                    [
                        system_timestamp,
                        image.width,
                        image.height,
                        image.frame_rate,
                        image.blockid,
                        image.bandwidth,
                        image.timestamp,
                    ]
                )

    def save(
        self,
        path: Path | str,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        **kwargs: Any,
    ) -> None:
        file_path = Path(path)
        file_path.mkdir(parents=True, exist_ok=True)
        self.write_to_csv_file(file_path)
        self.write_to_envi_file(file_path, width, height)
