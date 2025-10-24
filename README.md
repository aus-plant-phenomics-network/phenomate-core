# phenomate-core
## Overview

**phenomate-core** is a Python package for processing Phenomate sensor binaries into appropriate outputs.
The Phenomate platform collects data from the following sensors

- JAI RGB camera
- IMU - INS401
- Lidar (2D)
- Hyperspectral Camera

And it packs the data (typically) into Protobuffer messages as the sensors collect it. This package unpacks and
and possibly transforms the data from the protobuffer files, ready for further processing.


## Installation

Clone the repository and install dependencies:

```sh
git clone https://github.com/yourusername/phenomate-core.git
cd phenomate-core
make install
```

### Installing libjpeg-turbo - Oak-d

Please see the official [page](https://libjpeg-turbo.org/) for installing `libjpeg-turbo` for your operating system.

### Installing Sickscan - 2D Lidar

The conversion code for the 2D LIDAR has the required Python code as part of this repository. If
the code needs updating then it can be built from the GitHub repository:

```bash
mkdir -p ./sick_scan_ws
cd ./sick_scan_ws

git clone -b master https://github.com/SICKAG/sick_scan_xd.git

mkdir -p ./build
pushd ./build
rm -rf ./*
export ROS_VERSION=0

# specify optimisation level: -DO=0 (compiler flags -g -O0), -DO=1 (for compiler flags -O1) or -DO=2
# Install to local directory uising CMAKE_INSTALL_PREFIX=
cmake -DCMAKE_INSTALL_PREFIX=~/local -DROS_VERSION=0 -DLDMRS=0 -DSCANSEGMENT_XD=0 -G "Unix Makefiles" ../sick_scan_xd
make -j4
make -j4 install  # install locally
popd

# The output Python code can be found in:
# ~/local/include/sick_scan_xd/sick_scan_xd.py
# and can be copied to phenomate-core/phenomate_core/preprocessing/lidar
```

## Usage

Example usage for extracting and saving images:

```python
from phenomate_core import JaiPreprocessor

preproc = JaiPreprocessor(path="path/to/data.bin")
preproc.extract()
preproc.save(path="output_dir")
```

## Development

- Python 3.11+
- Uses [ruff](https://github.com/astral-sh/ruff) and [mypy](http://mypy-lang.org/) for linting and type checking
- Protobuf files should be compiled with `protoc` as needed

```baah
uv pip install protobuf
make compile-pb
```

## Contributing

Contributions are welcome! Please open issues or pull requests for bug fixes, features, or improvements.
