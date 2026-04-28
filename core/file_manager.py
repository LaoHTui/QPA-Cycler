import glob
import os
import re
from typing import Dict, Iterable, Set, Union

from File_operations import data_numbering as dn


def manage_sequential_file_naming(file_type: str, directory: str, mode: str = "number"):
    """
    直接封装你原来的编号整理函数，不改底层库。
    """
    return dn.manage_sequential_file_naming(file_type=file_type, directory=directory, mode=mode)


def scan_numbered_files(folder_path: str, file_type: str) -> Dict[int, str]:
    """
    扫描目录下所有匹配 file_type 的文件，
    并按“文件名开头数字”建立映射：{编号: 文件路径}
    """
    pattern = os.path.join(folder_path, f"*.{file_type}")
    files = glob.glob(pattern)

    file_map: Dict[int, str] = {}
    for file_path in files:
        file_name = os.path.basename(file_path)
        match = re.match(r"^(\d+)", file_name)
        if match:
            num = int(match.group(1))
            file_map[num] = file_path

    return file_map


def parse_target_numbers(
    numbers: Union[int, list, str],
    available_numbers: Iterable[int] = None
) -> Set[int]:
    """
    把 config 里的 file_numbers 解析成一个编号集合。

    支持：
    - int：单个编号；负数表示全部
    - list：[1, 3, 7]
    - str：
        - "3-50"
        - "1,3,7"
        - "5"
    """
    available_numbers = set(available_numbers) if available_numbers is not None else set()

    if isinstance(numbers, int):
        if numbers < 0:
            return set(available_numbers)
        return {numbers}

    if isinstance(numbers, list):
        result = set()
        for n in numbers:
            try:
                result.add(int(n))
            except (TypeError, ValueError):
                pass
        return result

    if isinstance(numbers, str):
        s = numbers.strip()
        if not s:
            return set()

        if "-" in s:
            start_end = s.split("-")
            if len(start_end) == 2:
                try:
                    start = int(start_end[0].strip())
                    end = int(start_end[1].strip())
                    return set(range(start, end + 1))
                except ValueError:
                    return set()
            return set()

        if "," in s:
            result = set()
            try:
                for item in s.split(","):
                    result.add(int(item.strip()))
                return result
            except ValueError:
                return set()

        try:
            return {int(s)}
        except ValueError:
            return set()

    return set()