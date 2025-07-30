from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from PIL import Image

from phenomate_core.preprocessing.base import BasePreprocessor
from phenomate_core.preprocessing.jai import jai_pb2


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

    def save(
        self,
        path: Path | str,
        width: int | None = None,
        height: int | None = None,
        **kwargs: Any,
    ) -> None:
        fpath = Path(path)
        fpath.mkdir(parents=True, exist_ok=True)
        for index, image in enumerate(self.images):
            # Determine width and height
            iwidth = width if width is not None else image.width
            iheight = height if height is not None else image.height
            reshaped_image = self.bytes_to_numpy(image.image_data).reshape((iheight, iwidth))
            # Convert the reshaped image data to a PIL Image object
            out_image = Image.fromarray(reshaped_image)
            image_path = fpath / self.get_output_name(index, "jpeg")
            out_image.save(image_path)
