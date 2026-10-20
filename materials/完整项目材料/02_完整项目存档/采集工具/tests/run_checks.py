"""一条命令运行合成验收并保存可核验结果；不联网。"""
import io
import json
import platform
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observer.core import now, source_hash


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    report = dict(at=now(), python=platform.python_version(), source_hash=source_hash(),
                  fixture_type="SYNTHETIC_OFFLINE_ONLY_NOT_REAL_COMMENTS", tests_run=result.testsRun,
                  failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped), passed=result.wasSuccessful(),
                  output=stream.getvalue(), real_network="另见试跑_20261017/smoke.json；离线通过不表示真实接口分页通过")
    (ROOT / "验收结果.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(stream.getvalue())
    print("验收结果：", ROOT / "验收结果.json")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
