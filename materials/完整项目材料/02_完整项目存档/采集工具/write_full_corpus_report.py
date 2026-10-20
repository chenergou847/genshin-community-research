"""兼容旧入口：仅生成2026-10-20修订报告，不再覆盖为旧初稿。

原脚本与初稿备份见交接包/04_报告修订_20261019/历史原稿。
正文来源为新修订模板、连续引文摘录与已冻结分析JSON。
支持 --check；不联网、不重新编码、不写CSV／标签／原始档。
"""
from pathlib import Path
import runpy

if __name__ == "__main__":
    revision = Path(__file__).resolve().parents[2] / "04_报告修订_20261019" / "生成修订报告.py"
    if not revision.is_file():
        raise SystemExit("缺少修订报告来源，请从完整交接包运行；不回退生成旧初稿。")
    runpy.run_path(str(revision), run_name="__main__")
