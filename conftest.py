# Root conftest: pytest adds this file's directory (the repo root) to sys.path,
# which keeps `import clinical_pre_mortem_agent` working when tests are run with the plain
# `pytest` binary in CI — not just with `python -m pytest` locally.
