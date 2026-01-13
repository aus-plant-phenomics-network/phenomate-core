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

```bash
uv pip install protobuf
make compile-pb
```


### Project Updating version numbers
Version numbers follow the standard pattern of: MAJOR.MINOR.PATCH and the project
has been configured to use the Python libray ```bump-my-version``` to help automate the
change of version numbers that are used in the files within the project.
  
The following proceedures outline its use:
  
Make sure mump-my-version is installed
```
uv pip install  bump-my-version
# add to pyproject.toml 
uv add --dev bump-my-version
```
This tool uses the file ```.bumpmyversion.toml``` for configuring what files get modified.  

N.B. If files are added to the project that use an explicit version number, then add the files 
to ```.bumpmyversion.toml``` along with the rules.

Use the tool as follows:
1. make sure the current version in ```.bumpmyversion.toml``` is correct
e.g.
```
current_version = "0.4.0"
```
Set the bumpwhat value and run the ```bump-my-version``` command:
```
# uv run bump-my-version -h

export bumpwhat=major | minor | patch
uv run bump-my-version bump $bumpwhat
```


#### Post bump version tasks
After a version update the package can be published to PyPi:
```bash
rm -fr ./dist
uv build
uv publish # requires a token from PyPi - see .pypirc file
```
  
Now setup the ```Phenomate``` project repository telling it about the new version -
1. Edit ```pyproject.toml``` and change the "phenomate-core>=X.Y.Z" dependency to the latest version.
2. Then run:
```
uv lock
```

N.B. If installing into the Docker application, first comment out the local installation
path in ```pyproject.toml```  

```
#[tool.uv.sources]
# phenomate-core = { path = "../phenomate-core" }
# appm = { path = "../appn-project-manager" }
```
and then rebuild the the docker container:
```
docker compose up -d --force-recreate --build celery_worker
```

If not installing using Docker, just reinstall the new package into the uv virtual environment:
```bash
make install-local-phenomate-core  # this runs uv pip install ${LOCAL_APPM}
```


## Contributing

Contributions are welcome! Please open issues or pull requests for bug fixes, features, or improvements.
