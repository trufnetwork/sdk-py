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
pip install -e .
```

## Test

1. Before running the tests, make sure you have the TN Node running.
2. Then, run the tests with the following command:
```bash
python -m pytest tests
```