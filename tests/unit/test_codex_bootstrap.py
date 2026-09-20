"""Stage-independent package/engine contracts, fixed release examples from SPEC."""

import pytest

from harness_maker.codex_bootstrap import engine_requirement, update_status


@pytest.mark.parametrize("version", ["0.58.0", "0.58.0+codex.local-20260920"])
def test_s1_cachebuster_is_not_a_python_release(version: str) -> None:
    assert engine_requirement({"name": "harness-maker", "version": version}) == (
        "harness-maker==0.58.0"
    )


@pytest.mark.parametrize(
    "version", ["", "latest", "0.58", "0.58.0; touch x", "0.58.0+other", "0.58.0rc1"]
)
def test_s2_unsupported_release_is_rejected(version: str) -> None:
    with pytest.raises(ValueError, match="unsupported release"):
        engine_requirement({"name": "harness-maker", "version": version})


def test_s2_wrong_package_is_rejected() -> None:
    with pytest.raises(ValueError, match="package name"):
        engine_requirement({"name": "other", "version": "0.58.0"})


@pytest.mark.parametrize(
    ("plugin", "engine", "project", "expected"),
    [
        (None, None, None, "pending"),
        ("0.58.0", None, None, "partial"),
        ("0.58.0", "0.58.0", None, "partial"),
        ("0.58.0", None, "0.58.0", "partial"),
        ("0.58.0", "0.57.0", "0.58.0", "partial"),
        ("0.58.0", "0.58.0", "0.57.0", "partial"),
        ("0.58.0", "0.58.0", "0.58.0", "complete"),
        ("0.57.0", "0.57.0", "0.57.0", "pending"),
    ],
)
def test_s3_completion_requires_all_three_layers(
    plugin: str | None, engine: str | None, project: str | None, expected: str
) -> None:
    result = update_status("0.58.0", plugin=plugin, engine=engine, project=project)
    assert result.state == expected
    assert result.pending == tuple(
        name
        for name, value in [("plugin", plugin), ("engine", engine), ("project", project)]
        if value != "0.58.0"
    )


def test_s3_local_plugin_identity_is_distinct_from_engine_version() -> None:
    result = update_status(
        "0.58.0+codex.new", plugin="0.58.0+codex.old", engine="0.58.0", project="0.58.0"
    )
    assert result.state == "partial"
    assert result.pending == ("plugin",)
