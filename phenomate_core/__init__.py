from phenomate_core.preprocessing.base import BasePreprocessor
from phenomate_core.preprocessing.hyperspec.process import HyperspecPreprocessor
from phenomate_core.preprocessing.jai.process import JaiPreprocessor
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


def get_preprocessor(sensor: str, details: str = "") -> type[BasePreprocessor]:
    print(f"get_preprocessor called with sensor: {sensor}, details: {details}")
    match sensor.lower():
        case sensor if "jai" in sensor:
            return JaiPreprocessor
        case sensor if "hyper" in sensor:
            return HyperspecPreprocessor
        case sensor if "oak" in sensor:
            if "calibration" in details:
                return OakCalibrationPreprocessor
            if "imu" in details:
                return OakImuPacketsPreprocessor
            return OakFramePreprocessor
    raise ValueError(f"Unsupported sensor type: {sensor}")
