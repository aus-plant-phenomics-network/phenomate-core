from phenomate_core.preprocessing.base import BasePreprocessor
from phenomate_core.preprocessing.hyperspec.process import HyperspecPreprocessor
from phenomate_core.preprocessing.imu.process import ImuPreprocessor
from phenomate_core.preprocessing.jai.process import JaiPreprocessor
from phenomate_core.preprocessing.lidar2d.process import Lidar2DPreprocessor
from phenomate_core.preprocessing.lidar3douster.process import Ouster3dPreprocessor 
from phenomate_core.preprocessing.rs3basestation.process import RS3Preprocessor
from phenomate_core.preprocessing.canbus.process import CanbusPreprocessor
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
    "Ouster3dPreprocessor",
    "RS3Preprocessor",
    "CanbusPreprocessor",
)

from phenomate_core.get_version import get_task_logger
shared_logger = get_task_logger(__name__)

def get_preprocessor(sensor: str, details: str = "") -> type[BasePreprocessor]:
    """
    Selects the processing dependant on the keyword that is present in the data file's filename.
    
    N.B. The order of the case statements is important - in particular for the 2d / 3d lidar.
    
    The 'sensor' value is extracted from the filename of the data file, using the appm / appn-project-manager code
    as specified with the template.yaml input file.
    
    N.B. This code is run in the Phenomate\backend\activity\tasks.py preprocess_task() function as a Celery task.
  
    """
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
        case sensor if "ouster" in sensor:
            return Ouster3dPreprocessor
        case sensor if "lidar" in sensor:
            return Lidar2DPreprocessor
        case sensor if "rs3" in sensor:
            return RS3Preprocessor
        case sensor if "canbus" in sensor:
            return CanbusPreprocessor
            
    raise ValueError(f"Unsupported sensor type: {sensor}")
