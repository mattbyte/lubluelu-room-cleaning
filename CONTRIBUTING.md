# Contributing

Use Python 3.14.2+ on Linux, or open this repository in its development container. Ask before installing host tools or dependencies in managed workspaces.

```sh
pip install -r requirements_dev.txt
ruff check .
ruff format --check .
pytest
```

The test harness pins Home Assistant 2026.10.4. CI runs pytest, Ruff, hassfest, and HACS validation. To validate the minimum HA version, install `homeassistant==2026.10.0` after installing the test requirements and rerun pytest.

The `.devcontainer` builds an isolated Python environment. From the repository root:

```sh
docker build -f .devcontainer/Dockerfile -t lubluelu-room-cleaning-dev .
docker run --rm -v "$PWD:/workspaces/lubluelu-room-cleaning" lubluelu-room-cleaning-dev pytest
```

Tests create simulated Tuya Local entity-registry entries and mock only the transport service. The native `vacuum.clean_area` service remains real in its integration test, including HA area-to-segment mapping.

Do not add credentials, local keys, recipient URLs, real device identifiers, or unreviewed source diagnostics to fixtures or issues. Use synthetic entities. Hardware tests require explicit operator approval; setup, learning, and diagnostics must never initiate a physical command.

Maintain the one-write invariant: a room request generates one `0x14` setter and calls `text.set_value` once. Do not add start/mode writes or automatic retries. Keep source integration internals out of this companion.

## Release

1. Update `manifest.json` and release notes.
2. Run validation and review the diff for secrets and unintended files.
3. Push main and require all GitHub Actions jobs to pass.
4. Tag the tested commit and publish a GitHub release describing validation and hardware limitations.
5. Verify the release and HACS custom-repository metadata. Default HACS catalog submission is a separate task.
