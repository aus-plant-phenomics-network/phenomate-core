"""This script decodes the binary files generated
by the Oak-D Camera
There are mainly three types of binary files generated by the Oak-D Camera:
1. Hyperspectral images
2. IMU data
3. Calibration data

"""

from __future__ import annotations

import csv
import struct
from pathlib import Path
from typing import Any

import cv2
from turbojpeg import TurboJPEG

from phenomate_core.preprocessing.base import BasePreprocessor
from phenomate_core.preprocessing.oak_d import oak_pb2

# Initialize TurboJPEG
image_decoder = TurboJPEG()  # type: ignore[no-untyped-call]


class OakFramePreprocessor(BasePreprocessor[bytes]):
    def __init__(self, path: str | Path, in_ext: str = "bin") -> None:
        super().__init__(path, in_ext)
        self.metadata: list[oak_pb2.OakImageMeta] = []

    def extract(self, **kwargs: Any) -> None:
        with self.path.open("rb") as f:
            while True:
                # Read the length of serialized meta
                # first 8 bytes of the file are
                # the length of the meta data
                serialized_timestamp = f.read(8)
                if not serialized_timestamp:
                    break
                system_timestamp = struct.unpack("d", serialized_timestamp)[0]
                self.system_timestamps.append(system_timestamp)

                length_bytes = f.read(4)
                if not length_bytes:
                    break
                length = int.from_bytes(length_bytes, byteorder="little")

                # Reading the serialized meta
                serialized_meta = f.read(length)
                meta = oak_pb2.OakImageMeta()
                meta.ParseFromString(serialized_meta)
                self.metadata.append(meta)

                # Read the length of the next serialized image data
                length_bytes = f.read(4)
                if not length_bytes:
                    break
                length = int.from_bytes(length_bytes, byteorder="little")

                # Read the serialized image data
                image_data = f.read(length)

                self.images.append(image_data)

    def save_image_metadata_to_csv(self, path: Path) -> None:
        """This function saves the image metadata to a CSV file."""
        # Define the CSV header
        header = [
            "amiga_system_timestamp",
            "instance_num",
            "sequence_num",
            "timestamp",
            "timestamp_device",
            "exposure_time",
            "iso_value",
            "lens_pos",
            "profile",
            "cbr_preferred_bitrate_kbps",
            "vbr_or_mjpeg_quality",
            "frames_per_keyframe",
            "RateControlMode",
        ]
        file_path = path / self.get_output_name(None, "csv")
        # Open the CSV file for writing
        with file_path.open(mode="w", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=header)

            # Write the header
            writer.writeheader()

            # Write the metadata
            for meta, timestamp in zip(self.metadata, self.system_timestamps, strict=False):
                row = {
                    "amiga_system_timestamp": timestamp,
                    "instance_num": meta.instance_num,
                    "sequence_num": meta.sequence_num,
                    "timestamp": meta.timestamp,
                    "timestamp_device": meta.timestamp_device,
                    "exposure_time": meta.settings.exposure_time,
                    "iso_value": meta.settings.iso_value,
                    "lens_pos": meta.settings.lens_pos,
                    "profile": meta.encoder_options.profile,
                    "cbr_preferred_bitrate_kbps": meta.encoder_options.cbr_preferred_bitrate_kbps,
                    "vbr_or_mjpeg_quality": meta.encoder_options.vbr_or_mjpeg_quality,
                    "frames_per_keyframe": meta.encoder_options.frames_per_keyframe,
                    "RateControlMode": meta.encoder_options.rate_control_mode,
                }
                writer.writerow(row)

    def save_image_as_jpeg(self, path: Path) -> None:
        """This function decodes the image data and saves it as a JPEG file."""
        for index, (image_data, meta_data, amiga_timestamp) in enumerate(
            zip(self.images, self.metadata, self.system_timestamps, strict=False)
        ):
            # Decode the image data
            img = image_decoder.decode(image_data)  # type: ignore[no-untyped-call]
            # Extract metadata
            instance_num = meta_data.instance_num
            sequence_num = meta_data.sequence_num
            timestamp = meta_data.timestamp
            timestamp_device = meta_data.timestamp_device
            exposure_time = meta_data.settings.exposure_time
            iso_value = meta_data.settings.iso_value
            lens_pos = meta_data.settings.lens_pos

            # Prepare metadata text
            metadata_text = (
                f"Amiga Timestamp: {amiga_timestamp}\n"
                f"Instance Num: {instance_num}\n"
                f"Sequence Num: {sequence_num}\n"
                f"Timestamp: {timestamp}\n"
                f"Timestamp Device: {timestamp_device}\n"
                f"Exposure Time: {exposure_time}\n"
                f"ISO Value: {iso_value}\n"
                f"Lens Pos: {lens_pos}\n"
            )

            # Define text properties
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            font_color = (0, 0, 255)
            thickness = 1
            line_type = cv2.LINE_AA
            y0, dy = 30, 20

            # Writing metadata text to image
            for i, line in enumerate(metadata_text.split("\n")):
                y = y0 + i * dy
                cv2.putText(img, line, (10, y), font, font_scale, font_color, thickness, line_type)

            # Save the image as a JPEG file
            output_path = path / self.get_output_name(index, "jpeg")
            cv2.imwrite(str(output_path), img)

    def save(self, path: Path | str, **kwargs: Any) -> None:
        file_path = Path(path)
        file_path.mkdir(parents=True, exist_ok=True)
        self.save_image_metadata_to_csv(file_path)
        self.save_image_as_jpeg(file_path)


class OakImuPacketsPreprocessor(BasePreprocessor[oak_pb2.OakImuPacket]):
    def extract(self, **kwargs: Any) -> None:
        with self.path.open("rb") as f:
            while True:
                serialized_timestamp = f.read(8)
                if not serialized_timestamp:
                    break
                system_timestamp = struct.unpack("d", serialized_timestamp)[0]
                self.system_timestamps.append(system_timestamp)

                # Read the length of the next serialized message
                length_bytes = f.read(4)
                if not length_bytes:
                    break
                length = int.from_bytes(length_bytes, byteorder="little")

                serialized_data = f.read(length)
                if not serialized_data:
                    break

                # Deserialize the message
                imu_msg = oak_pb2.OakImuPackets()
                imu_msg.ParseFromString(serialized_data)

                # Extract the OakGyro and OakAccelero data
                for packet in imu_msg.packets:
                    self.images.append(packet)

    def save(self, path: Path | str, **kwargs: Any) -> None:
        file_path = Path(path) / self.get_output_name(None, "csv", "imu")
        with file_path.open(mode="w", newline="") as file:
            writer = csv.writer(file)

            # Write the header
            writer.writerow(
                [
                    "gyro_x",
                    "gyro_y",
                    "gyro_z",
                    "gyro_sequence_num",
                    "gyro_accuracy",
                    "gyro_timestamp",
                    "gyro_timestamp_device",
                    "gyro_timestamp_recv",
                    "accelero_x",
                    "accelero_y",
                    "accelero_z",
                    "accelero_sequence_num",
                    "accelero_accuracy",
                    "accelero_timestamp",
                    "accelero_timestamp_device",
                    "accelero_timestamp_recv",
                    "system_timestamp",
                ]
            )
            # Write the data
            for image, system_timestamp in zip(self.images, self.system_timestamps, strict=False):
                writer.writerow(
                    [
                        image.gyro_packet.gyro.x,
                        image.gyro_packet.gyro.y,
                        image.gyro_packet.gyro.z,
                        image.gyro_packet.sequence_num,
                        image.gyro_packet.accuracy,
                        image.gyro_packet.timestamp,
                        image.gyro_packet.timestamp_device,
                        image.gyro_packet.timestamp_recv,
                        image.accelero_packet.accelero.x,
                        image.accelero_packet.accelero.y,
                        image.accelero_packet.accelero.z,
                        image.accelero_packet.sequence_num,
                        image.accelero_packet.accuracy,
                        image.accelero_packet.timestamp,
                        image.accelero_packet.timestamp_device,
                        image.accelero_packet.timestamp_recv,
                        system_timestamp,
                    ]
                )


class OakCalibrationPreprocessor(BasePreprocessor[oak_pb2.OakCalibration]):
    def extract(self, **kwargs: Any) -> None:
        with self.path.open("rb") as f:
            while True:
                # Read the length of the next serialized message
                length_bytes = f.read(4)
                if not length_bytes:
                    break
                length = int.from_bytes(length_bytes, byteorder="little")

                # Read the serialized message
                serialized_data = f.read(length)
                if not serialized_data:
                    break

                # Deserialize the message
                cal_msg = oak_pb2.OakCalibration()
                cal_msg.ParseFromString(serialized_data)
                self.images.append(cal_msg)

    def save(self, path: str | Path, **kwargs: Any) -> None:
        file_path = Path(path) / self.get_output_name(None, "txt", "calibration")
        with file_path.open(mode="a") as file:
            for image in enumerate(self.images):
                file.write(str(image) + "\n")
