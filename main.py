import argparse
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from core.pipeline import run_pipeline


def parse_args():
    parser = argparse.ArgumentParser(description="QPA-Cycler")
    parser.add_argument(
        "--config",
        default="config",
        help="配置文件路径，可带或不带 .json 后缀，例如 config 或 config.json"
    )
    parser.add_argument(
        "--no-docx",
        action="store_true",
        help="不导出 docx 报告"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    config_map = os.path.splitext(args.config)[0]  # 兼容 config / config.json
    run_pipeline(config_map=config_map)