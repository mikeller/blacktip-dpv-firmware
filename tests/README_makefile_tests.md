These tests parse the project's Makefile to validate the key configuration and targets.

Framework note:
- If pytest is detected (via config or imports), tests are written with pytest.
- Otherwise, unittest (stdlib) is used.

To run with pytest:

```bash
export MAKEFILE_PATH="${MAKEFILE_PATH:-Makefile}"
pytest -q tests/test_makefile.py
```

To run with unittest:

```bash
export MAKEFILE_PATH="${MAKEFILE_PATH:-Makefile}"
python -m unittest tests/test_makefile.py -v
```