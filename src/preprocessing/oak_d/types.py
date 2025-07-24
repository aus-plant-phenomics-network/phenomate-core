from __future__ import annotations
from dataclasses import dataclass
import enum
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING: 
    import numpy as np 
    from numpy.typing import NDArray

@dataclass 
class CameraSettings: 
    auto_exposure: bool 
    exposure_time: int 
    iso_value: int 
    lens_pos: int 

class EncoderProfile(enum.Enum): 
    H264_BASELINE = 0 
    H264_HIGH = 1 
    H264_MAIN = 2 
    H265_MAIN = 3 
    MJPEG = 4 

class RateControlMode(enum.Enum): 
    CBR = 0 
    VBR = 0 

@dataclass 
class EncoderOptions: 
    profile: EncoderProfile 
    rate_control_mode: RateControlMode 
    cbr_preferred_bitrate_kbps: int 
    vbr_or_mjpeg_quality: int 
    frames_per_keyframe: int 

class PixelFormat(enum.Enum): 
    UNKNOWN = 0 
    YUV420 = 1 
    RAW8 = 2 
    Encoded = 3 

@dataclass
class Resolution: 
    width: int 
    height: int 

@dataclass 
class OakImageMeta: 
    category: int 
    instance_num: int 
    sequence_num: int 
    timestamp: float 
    timestamp_device: float 
    timestamp_recv: float 
    settings: CameraSettings
    encoder_options: EncoderOptions 
    resolution: Resolution 
    pixel_format: PixelFormat 

@dataclass 
class OakFrame: 
    image_data: NDArray[np.uint8]
    meta: OakImageMeta 

@dataclass 
class OakGyro: 
    gyro: Vec3F32 
    sequence_num: int 
    accuracy: str 
    timestamp: float 
    timestamp_device: float 
    timestamp_recv: float 

@dataclass 
class OakAccelero: 
    accelero: Vec3F32 
    sequence_num: int 
    accuracy: str 
    timestamp: float 
    timestamp_device: float 
    timestamp_recv: float 

@dataclass 
class OakImuPacket: 
    gyro_packet: OakGyro 
    accelero_packet: OakAccelero 

@dataclass 
class OakImuPackets: 
    packets: Sequence[OakImuPacket]

@dataclass 
class OakTrackedFeaturePacket: 
    xy: Vec2F32 
    id: int 
    age: int 
    harrisScore: float 
    trackingError: float 

@dataclass 
class OakTrackedFeaturePackets: 
    packets: Sequence[OakTrackedFeaturePacket]
    sequence_num: int 
    timestamp: float 
    timestamp_device: float 
    timestamp_recv: float 

@dataclass 
class OakDeviceInfo: 
    name: str 
    mxid: str 
    ip: str 

@dataclass 
class OakSyncFrame: 
    left: OakFrame
    right: OakFrame
    rgb: OakFrame
    disparity: OakFrame 
    nn: OakNNData 
    imu_packets: OakImuPackets
    sequence_num: int 
    device_info: OakDeviceInfo 

@dataclass 
class OakNNData: 
    meta: OakImageMeta 
    num_channels: int 
    height: int 
    width: int 
    data: NDArray[np.uint8]

@dataclass 
class Pair: 
    key: str 
    value: str 

@dataclass 
class Metadata: 
    pairs: Sequence[Pair]

@dataclass 
class OakDataSample: 
    frame: OakSyncFrame 
    metadata: Metadata              

@dataclass 
class RotationMatrix: 
    rotation_matrix: Sequence[float] 

@dataclass 
class Extrinsics: 
    rotation_matrix: Sequence[float]
    spec_translation: Vec3F32 
    camera_socket: int 
    translation: Vec3F32 

@dataclass 
class CameraData: 
    camera_number: int 
    camera_type: int 
    distortion_coeff: Sequence[float]
    extrinsics: Extrinsics
    height: int 
    intrinsic_matrix: Sequence[float]
    len_position: int 
    spec_hfov_def: float 
    width: float 

@dataclass
class SteroRectificationData: 
    left_camera_socket: int 
    rectified_rotation_left: Sequence[float]
    rectified_rotation_right: Sequence[float]
    right_camera_socket: int 

@dataclass 
class OakCalibration: 
    batch_name: str 
    batch_time: int 
    board_conf: str 
    board_custom: str 
    board_name: str 
    board_options: int 
    board_rev: str 
    camera_data: Sequence[CameraData]
    hardware_conf: str 
    imu_extrinsics: Extrinsics
    miscellaneous_data: Sequence[str]
    product_name: str 
    stereo_rectification_data: SteroRectificationData 
    version: int 

@dataclass 
class Vec2F32:
  x: float
  y: float 

@dataclass 
class Vec3F32:
  x: float
  y: float
  z: float  