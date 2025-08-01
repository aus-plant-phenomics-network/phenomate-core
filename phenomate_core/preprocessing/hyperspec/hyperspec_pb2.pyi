"""
@generated by mypy-protobuf.  Do not edit manually!
isort:skip_file
"""

import builtins
import google.protobuf.descriptor
import google.protobuf.message
import typing

DESCRIPTOR: google.protobuf.descriptor.FileDescriptor

@typing.final
class HyperSpecImage(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    IMAGE_DATA_FIELD_NUMBER: builtins.int
    WIDTH_FIELD_NUMBER: builtins.int
    HEIGHT_FIELD_NUMBER: builtins.int
    FRAME_RATE_FIELD_NUMBER: builtins.int
    BLOCKID_FIELD_NUMBER: builtins.int
    BANDWIDTH_FIELD_NUMBER: builtins.int
    TIMESTAMP_FIELD_NUMBER: builtins.int
    image_data: builtins.bytes
    """Raw image data as bytes"""
    width: builtins.int
    """Width of the image"""
    height: builtins.int
    """Height of the image"""
    frame_rate: builtins.float
    """Frame rate"""
    blockid: builtins.int
    """Block ID"""
    bandwidth: builtins.int
    """Bandwidth"""
    timestamp: builtins.int
    """timestamp of image"""
    def __init__(
        self,
        *,
        image_data: builtins.bytes = ...,
        width: builtins.int = ...,
        height: builtins.int = ...,
        frame_rate: builtins.float = ...,
        blockid: builtins.int = ...,
        bandwidth: builtins.int = ...,
        timestamp: builtins.int = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing.Literal["bandwidth", b"bandwidth", "blockid", b"blockid", "frame_rate", b"frame_rate", "height", b"height", "image_data", b"image_data", "timestamp", b"timestamp", "width", b"width"]) -> None: ...

global___HyperSpecImage = HyperSpecImage
