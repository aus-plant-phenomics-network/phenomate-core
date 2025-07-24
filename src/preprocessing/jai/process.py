from __future__ import annotations

from pathlib import Path
import struct

from typing import TYPE_CHECKING, Any
import numpy as np 
import jai_pb2
from dataclasses import dataclass
from PIL import Image 

if TYPE_CHECKING: 
    from numpy.typing import NDArray

@dataclass 
class JaiData: 
    image_data: NDArray[np.uint8]
    width: int 
    height: int 
    frame_rate: float 
    blockid: int 
    bandwidth: int 
    timestamp: int 
    system_timestamp: int     

class JaiPreprocessor: 
    def __init__(self, path: Path)->None: 
        if not path.exists(): 
            raise FileNotFoundError(f"{str(path)}")
        if not path.is_file(): 
            raise ValueError(f"Expects {path} to be a jai file")
        self.path = path 
        self.name = path.name 
        self.images: list[JaiData] = [] 

    def extract(self, **kwargs: dict[Any, Any])->None:
        with self.path.open("rb") as file:
            while True:
                # Read the length of the next serialized message
                serialized_timestamp = file.read(8)
                if not serialized_timestamp:
                    break
                systemtimestamp = struct.unpack("d", serialized_timestamp)[0]

                length_bytes = file.read(4)
                if not length_bytes:
                    break
                length = int.from_bytes(length_bytes, byteorder="little")

                # Read the serialized message
                serialized_image = file.read(length)

                # Parse the protobuf message
                image_protobuf_obj = jai_pb2.JAIImage()
                image_protobuf_obj.ParseFromString(serialized_image)

                # # Convert the image data back to numpy.ndarray
                image_data = np.frombuffer(image_protobuf_obj.image_data, dtype=np.uint8)

                self.images.append(
                    JaiData(
                        image_data=image_data,
                        width=image_protobuf_obj.width,
                        height=image_protobuf_obj.height,
                        frame_rate=image_protobuf_obj.frame_rate, 
                        blockid = image_protobuf_obj.blockid, 
                        bandwidth= image_protobuf_obj.bandwidth,
                        timestamp= image_protobuf_obj.timestamp, 
                        system_timestamp=systemtimestamp
                    )
                )
    
    def save(self, path: Path|str, width: int | None = None, height: int|None = None, **kwargs: dict[Any, Any])->None: 
        file_path = Path(path) 
        file_path.mkdir(parents=True, exists_ok=True)
        for (index,image) in enumerate(self.images):
            iwidth = width if width is not None else image.width
            iheight = height if height is not None else image.height 
            reshaped_image: NDArray[np.uint8] = image.image_data.reshape((iheight, iwidth))

            # Convert the reshaped image data to a PIL Image object
            image = Image.fromarray(reshaped_image.astype(np.uint8))
            file_name = f"{self.name}.output_{index}.jpeg"
            image_path = file_path / file_name 
            image.save(image_path, "JPEG")