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
    match sensor.lower():
        case "jai":
            return JaiPreprocessor
        case "hyperspec" | "hyper-spec" | "hyperspectral" | "hyper-spectral":
            return HyperspecPreprocessor
        case "oak":
            if "calibration" in details:
                return OakCalibrationPreprocessor
            if "imu" in details:
                return OakImuPacketsPreprocessor
            return OakFramePreprocessor
    raise ValueError(f"Unsupported sensor type: {sensor}")
