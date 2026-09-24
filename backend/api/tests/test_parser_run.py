import importlib.util
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest


spec = importlib.util.spec_from_file_location(
    "parser_run", Path(__file__).resolve().parents[2] / "parser/run.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize("failed", [None, "parser.py", "robort.py"])
def test_sources_run_independently_and_refresh_catalog(tmp_path, failed):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs["env"]["OUTPUT_FILE"]))
        if Path(command[1]).name == failed:
            raise subprocess.CalledProcessError(1, command)

    with patch.dict(runner.os.environ, {"OUTPUT_FILE": str(tmp_path / "robots.json"),
                                       "ROBORT_OUTPUT_FILE": str(tmp_path / "robort_robots.json")}), \
            patch.object(runner.subprocess, "run", side_effect=run):
        if failed:
            with pytest.raises(RuntimeError):
                runner.run_once()
        else:
            runner.run_once()
    assert (tmp_path / ".catalog-refresh").read_text()
    assert [Path(c[0][1]).name for c in calls if c[0][1] != "-m"] == ["parser.py", "robort.py"]
    imports = [c for c in calls if c[0][1] == "-m"]
    assert len(imports) == (1 if failed else 2)
    for command, output in imports:
        assert command[-1] == output
        assert Path(output).name != {"parser.py": "robots.json", "robort.py": "robort_robots.json"}.get(failed)
