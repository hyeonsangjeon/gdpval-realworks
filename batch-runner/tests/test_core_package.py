import os
import subprocess
import sys


def test_core_package_does_not_eagerly_import_dataset_stack():
    code = """
import sys
import core
import core.grader_preflight
assert 'prepare_dataset' not in sys.modules
assert 'datasets' not in sys.modules
assert 'GDPValDataLoader' in core.__all__
assert 'DomainFilter' in core.__all__
assert 'core.grader_preflight' in sys.modules
assert 'prepare_dataset' not in sys.modules
assert 'datasets' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "PYTHONPATH": os.getcwd()},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_core_package_unknown_export_raises_attribute_error():
    import core

    try:
        core.not_a_real_export
    except AttributeError as exc:
        assert "not_a_real_export" in str(exc)
    else:
        raise AssertionError("unknown core export did not raise AttributeError")
