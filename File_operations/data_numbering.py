import glob
import os
import re
import time
import uuid
from typing import List, Tuple


# 匹配： 123_xxx.csv
_NUM_PREFIX_RE = re.compile(r"^(\d+)_(.+)$")


def _normalize_file_type(file_type: str) -> str:
    """
    统一文件类型写法：
    - csv
    - .csv
    """
    if file_type is None:
        raise ValueError("file_type 不能为空")
    ft = str(file_type).strip().lstrip(".")
    if not ft:
        raise ValueError("file_type 不能为空")
    return ft


def _list_target_files(directory: str, file_type: str) -> List[str]:
    """
    获取目录下指定后缀的所有文件（只取文件，不取文件夹）
    """
    directory = os.path.abspath(directory or ".")
    file_type = _normalize_file_type(file_type)
    pattern = os.path.join(directory, f"*.{file_type}")
    return [p for p in glob.glob(pattern) if os.path.isfile(p)]


def _split_numbered_and_unnumbered(files: List[str]):
    """
    把文件分成两类：
    - numbered:  123_xxx.csv
    - unnumbered: xxx.csv
    """
    numbered = []
    unnumbered = []

    for file_path in files:
        file_name = os.path.basename(file_path)
        match = _NUM_PREFIX_RE.match(file_name)

        if match:
            num = int(match.group(1))
            original_name = match.group(2)
            numbered.append((num, original_name, file_path))
        else:
            unnumbered.append((file_name, file_path))

    # 已编号文件：按编号升序，必要时按名字兜底
    numbered.sort(key=lambda x: (x[0], x[1].lower(), os.path.basename(x[2]).lower()))
    # 未编号文件：按名字稳定排序，避免每次结果不一致
    unnumbered.sort(key=lambda x: (x[0].lower(), os.path.basename(x[1]).lower()))

    return numbered, unnumbered


def _build_temp_path(src_path: str) -> str:
    """
    生成同目录下唯一临时文件名，用于安全重命名
    """
    directory = os.path.dirname(src_path)
    base = os.path.basename(src_path)
    return os.path.join(directory, f".__tmp__{uuid.uuid4().hex}__{base}")


def _safe_batch_rename(rename_pairs: List[Tuple[str, str]]) -> int:
    """
    安全批量重命名：
    1. 先全部改成临时名
    2. 再从临时名改成最终名

    这样可以避免“目标文件名暂时还被旧文件占用”的冲突问题。
    """
    normalized = []
    for src, dst in rename_pairs:
        src_abs = os.path.abspath(src)
        dst_abs = os.path.abspath(dst)
        if src_abs != dst_abs:
            normalized.append((src_abs, dst_abs))

    if not normalized:
        return 0

    source_set = {src for src, _ in normalized}

    # 预检查：如果目标文件已存在，而且不是本次重命名队列中的文件，就报错
    for src, dst in normalized:
        if os.path.exists(dst) and dst not in source_set:
            raise FileExistsError(f"目标文件已存在: {os.path.basename(dst)}")

    temp_records = []  # (src, tmp, dst)

    # 第1步：全部移动到临时名
    try:
        for src, dst in normalized:
            tmp = _build_temp_path(src)
            os.rename(src, tmp)
            temp_records.append((src, tmp, dst))
    except Exception:
        # 如果第1步中途失败，回滚已经移动到临时名的文件
        for src, tmp, dst in reversed(temp_records):
            if os.path.exists(tmp):
                try:
                    os.rename(tmp, src)
                except Exception:
                    pass
        raise

    # 第2步：从临时名移动到最终名
    completed = []
    try:
        for src, tmp, dst in temp_records:
            os.rename(tmp, dst)
            completed.append((src, tmp, dst))
    except Exception:
        # 回滚：已经落到最终名的，改回原名
        for src, tmp, dst in reversed(completed):
            if os.path.exists(dst):
                try:
                    os.rename(dst, src)
                except Exception:
                    pass

        # 还没来得及处理的临时文件，改回原名
        for src, tmp, dst in temp_records[len(completed):]:
            if os.path.exists(tmp):
                try:
                    os.rename(tmp, src)
                except Exception:
                    pass

        raise

    return len(normalized)


def _make_unique_restored_name(directory: str, original_name: str, reserved_names: set) -> str:
    """
    恢复命名时，如果原名已存在，则追加时间戳避免冲突
    """
    original_name = os.path.basename(original_name)
    base, ext = os.path.splitext(original_name)

    # 先尝试原名
    if original_name not in reserved_names and not os.path.exists(os.path.join(directory, original_name)):
        reserved_names.add(original_name)
        return original_name

    # 再尝试 timestamp 后缀
    timestamp = int(time.time())
    idx = 1
    while True:
        if idx == 1:
            candidate = f"{base}_{timestamp}{ext}"
        else:
            candidate = f"{base}_{timestamp}_{idx}{ext}"

        if candidate not in reserved_names and not os.path.exists(os.path.join(directory, candidate)):
            reserved_names.add(candidate)
            return candidate

        idx += 1


def manage_sequential_file_naming(file_type, directory='.', mode='number', start_num=1,print_log=True):
    """
    管理目录中文件的顺序编号。支持两种模式：
    1) 'number' 模式：修复编号间隙，为未编号文件添加编号，并保持序列连续
    2) 'remove' 模式：移除文件名的数字前缀，同时防止名称冲突

    参数：
    file_type (str): 目标文件扩展名，例如 'csv' / '.csv'
    directory (str): 目标目录
    mode (str): 'number' 或 'remove'
    start_num (int): 起始编号，默认 1

    返回：
    int: 实际重命名的文件数量
    """
    directory = os.path.abspath(directory or ".")
    file_type = _normalize_file_type(file_type)
    files = _list_target_files(directory, file_type)

    if not files:
        print(f"目录中没有找到 .{file_type} 文件：{directory}")
        return 0

    if mode == 'number':
        numbered_files, unnumbered_files = _split_numbered_and_unnumbered(files)

        rename_pairs = []
        log_actions = []  # 用于打印日志

        expected_num = int(start_num)

        # 1) 先处理已编号文件：补齐/修复编号
        for num, original_name, file_path in numbered_files:
            current_name = os.path.basename(file_path)

            if num != expected_num:
                new_name = f"{expected_num}_{original_name}"
                new_path = os.path.join(directory, new_name)
                rename_pairs.append((file_path, new_path))
                log_actions.append((current_name, new_name, "修复编号"))

            expected_num += 1

        # 2) 再处理未编号文件：继续往后编号
        next_num = expected_num
        for file_name, file_path in unnumbered_files:
            new_name = f"{next_num}_{file_name}"
            new_path = os.path.join(directory, new_name)
            rename_pairs.append((file_path, new_path))
            log_actions.append((file_name, new_name, "添加编号"))
            next_num += 1

        renamed_count = _safe_batch_rename(rename_pairs)
        if print_log:
            for old_name, new_name, action in log_actions:
                print(f"{action}: {old_name} -> {new_name}")

        return renamed_count

    elif mode == 'remove':
        rename_pairs = []
        log_actions = []
        reserved_names = set()

        # 只处理带数字前缀的文件
        numbered_files = []
        for file_path in files:
            file_name = os.path.basename(file_path)
            match = _NUM_PREFIX_RE.match(file_name)
            if match:
                numbered_files.append((file_path, match.group(2)))

        # 为避免同名冲突，逐个生成唯一目标名
        for file_path, original_name in numbered_files:
            current_name = os.path.basename(file_path)
            new_name = _make_unique_restored_name(directory, original_name, reserved_names)
            new_path = os.path.join(directory, new_name)

            rename_pairs.append((file_path, new_path))
            log_actions.append((current_name, new_name, "恢复命名"))

        renamed_count = _safe_batch_rename(rename_pairs)
        if print_log:
            for old_name, new_name, action in log_actions:
                print(f"{action}: {old_name} -> {new_name}")

        return renamed_count

    else:
        raise ValueError("mode 只能是 'number' 或 'remove'")


# =========================================================
# 给 GUI 直接调用的两个函数
# =========================================================

def sort_files(directory='.', file_type='csv', start_num=1):
    """
    排序/编号按钮直接调用这个。
    作用：对目录内指定类型文件进行顺序编号
    """
    return manage_sequential_file_naming(
        file_type=file_type,
        directory=directory,
        mode='number',
        start_num=start_num,
        print_log=False
    )


def restore_files(directory='.', file_type='csv'):
    """
    恢复命名按钮直接调用这个。
    作用：移除目录内指定类型文件名的数字前缀
    """
    return manage_sequential_file_naming(
        file_type=file_type,
        directory=directory,
        mode='remove',
        print_log=False
    )



if __name__ == "__main__":
    # 你可以手动测试，平时不要取消注释自动运行
    # sort_files(r"S:\FermiData\fsrq\daily", "csv", start_num=1)
    # restore_files(r"S:\FermiData\fsrq\daily", "csv")
    pass