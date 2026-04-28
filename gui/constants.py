import os

# 项目根目录：假设 gui/ 在项目根目录下
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")
DEFAULT_RUNNER_PATH = os.path.join(PROJECT_ROOT, "main.py")

# 单源覆盖只允许这些全局字段
SOURCE_OVERRIDE_GLOBAL_KEYS = {
    "start_date",
    "end_date",
    "remove_upper_limit",
    "remove_max_value_numbers",
}

RESULT_IMAGE_SPECS = [
    {
        "key": "Light_Plot",
        "title": "光变图",
        "folder": "Light_Plot",
        "result_key": None,
        "must_have": None,
        "must_not_have": ["psresp", "log", "beta", "slope"],
    },
    {
        "key": "LSP",
        "title": "LSP",
        "folder": "LSP",
        "result_key": "LSP",
        "must_have": None,
        "must_not_have": ["psresp", "log", "beta", "slope"],
    },
    {
        "key": "Beta",
        "title": "β斜率",
        "folder": "LSP",
        "result_key": "Beta",
        "must_have": ["psresp", "log"],
        "must_not_have": [],
    },
    {
        "key": "Jurkevich",
        "title": "Jurkevich",
        "folder": "Jurkevich",
        "result_key": "Jurkevich",
        "must_have": None,
        "must_not_have": None,
    },
    {
        "key": "DCF",
        "title": "DCF",
        "folder": "DCF",
        "result_key": "DCF",
        "must_have": None,
        "must_not_have": None,
    },
    {
        "key": "WWZ",
        "title": "WWZ",
        "folder": "WWZ",
        "result_key": "WWZ",
        "must_have": None,
        "must_not_have": None,
    },
]