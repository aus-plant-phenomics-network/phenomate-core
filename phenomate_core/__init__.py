from phenomate_core.preprocessing.base import BasePreprocessor
from phenomate_core.preprocessing.hyperspec.process import HyperspecPreprocessor
from phenomate_core.preprocessing.imu.process import ImuPreprocessor
from phenomate_core.preprocessing.jai.process import JaiPreprocessor
from phenomate_core.preprocessing.lidar2d.process import Lidar2DPreprocessor
from phenomate_core.preprocessing.oak_d.process import (
    OakCalibrationPreprocessor,
    OakFramePreprocessor,
    OakImuPacketsPreprocessor,
)

__all__ = (
    "BasePreprocessor",
    "HyperspecPreprocessor",
    "JaiPreprocessor",
    "OakCalibrationPreprocessor",
    "OakFramePreprocessor",
    "OakImuPacketsPreprocessor",
)

from phenomate_core.get_version import get_task_logger
shared_logger = get_task_logger(__name__)

def get_preprocessor(sensor: str, details: str = "") -> type[BasePreprocessor]:
    shared_logger.info(f"phenomate_core: get_preprocessor() called with sensor: {sensor}, details: {details}")
    match sensor.lower():
        case sensor if "jai" in sensor:
            return JaiPreprocessor
        case sensor if "hyper" in sensor:
            return HyperspecPreprocessor
        case sensor if "white" in sensor:
            return HyperspecPreprocessor
        case sensor if "dark" in sensor:
            return HyperspecPreprocessor
        case sensor if "oak" in sensor:
            if "calibration" in details:
                return OakCalibrationPreprocessor
            if "imu" in details:
                return OakImuPacketsPreprocessor
            return OakFramePreprocessor
        case sensor if "imu" in sensor:
            return ImuPreprocessor
        case sensor if "lidar" in sensor:
            return Lidar2DPreprocessor

    raise ValueError(f"Unsupported sensor type: {sensor}")
