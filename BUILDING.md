# BUILDING

This project: **natural** Version: **0.1.0**

## Local environment setup

This project uses a standard Python virtual environment. You can set everything up automatically using the build script:

```bash
# Creates the venv and installs all dependencies
./build.sh install
```

Or run the steps manually:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .[dev]
```

## Running Tests

Once your environment is active, you can run the test suite:

```bash
./build.sh test
```
