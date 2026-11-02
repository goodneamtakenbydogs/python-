"""在仓库以外的新环境安装给定 wheel，验证模块与真实命令入口。"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def run(arguments, *, cwd, environment, expected=0):
    result = subprocess.run(arguments, cwd=cwd, env=environment, capture_output=True,
                            text=True, encoding="utf-8", check=False, timeout=60,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode != expected:
        raise RuntimeError(f"isolated command failed: code={result.returncode}\n{result.stderr}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="验证一个本地 wheel，而非验证源码导入")
    parser.add_argument("wheel", help="wheel 路径或恰好匹配一个文件的模式")
    args = parser.parse_args(argv)
    matches = [Path(path).resolve() for path in glob.glob(args.wheel)]
    if len(matches) != 1 or matches[0].suffix != ".whl":
        parser.error("wheel must match exactly one .whl file")
    uv = shutil.which("uv")
    if uv is None:
        parser.error("uv must be available for creating the clean environment")
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "STUDY_RESULTS_MAX_RECORDS"):
        environment.pop(key, None)
    environment.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    with TemporaryDirectory(prefix="study-results-wheel-") as directory:
        root = Path(directory)
        isolated = root / "environment"
        run([uv, "venv", "--python", sys.executable, str(isolated)], cwd=root, environment=environment)
        python = isolated / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        entry = isolated / ("Scripts/study-results.exe" if os.name == "nt" else "bin/study-results")
        run([uv, "pip", "install", "--python", str(python), "--no-deps", str(matches[0])],
            cwd=root, environment=environment)
        check_import = (
            "from pathlib import Path; from importlib.metadata import version; import study_results; "
            f"assert Path(study_results.__file__).resolve().is_relative_to(Path({str(isolated)!r}).resolve()), "
            "'installed module is outside the resolved clean environment'; "
            "assert study_results.__version__ == version('study-results-demo')"
        )
        run([str(python), "-c", check_import], cwd=root, environment=environment)
        source = root / "sample input.jsonl"
        source.write_text('{"case_id":"C-demo","status":"passed","duration":0.5}\n', encoding="utf-8")
        before = source.read_bytes()
        for prefix in ([str(entry)], [str(python), "-m", "study_results"]):
            result = run([*prefix, str(source), "--run-id", "wheel-check"], cwd=root, environment=environment)
            report = json.loads(result.stdout)
            assert report["input_total"] == 1 and report["counts"] == {"passed": 1, "failed": 0, "skipped": 0}
            assert report["run_id"] == "wheel-check"
        assert source.read_bytes() == before
        run([str(entry), "--help"], cwd=root, environment=environment)
        version = run([str(entry), "--version"], cwd=root, environment=environment)
        assert "0.1.0" in version.stdout
        source.write_text("", encoding="utf-8")
        empty = run([str(entry), str(source)], cwd=root, environment=environment)
        assert json.loads(empty.stdout)["selected_total"] == 0
        source.write_text("bad JSON\n", encoding="utf-8")
        failed = run([str(entry), str(source)], cwd=root, environment=environment, expected=3)
        assert failed.stdout == "" and json.loads(failed.stderr)["category"] == "input"
    print("Wheel installed and verified outside the checkout in a new environment")


if __name__ == "__main__":
    main()
