# Truf Network (TN) SDK - Python

Under development. Uses C bindings to load the TN SDK (Go) library under the hood.

## Requirements
- Go
- Python

## Development

It is recommended to use a virtual environment to develop the SDK.
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### Recompile the C bindings

To recompile the C bindings, run the following command:
```bash
make
```

### Test

1. Build the TN Node container image by running the `task compose` command on `node` repository.
2. Stop the TN Node container if it is running, but do not remove the image as it is needed.
3. Before running the tests, make sure the TN Node is not running. The tests will start a TN Node in the background and stop it after the tests are finished.
4. Then, run the tests with the following command:
```bash
python -m pytest tests/<test_file>.py
```

### Development and Testing Summary

To summarize, here are the steps to develop and test the SDK:
```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# Recompile the C bindings
make

# Run the tests
python -m pytest tests/test_tnclient.py
python -m pytest tests/test_procedure.py
python -m pytest tests/test_sequential_inserts.py
```