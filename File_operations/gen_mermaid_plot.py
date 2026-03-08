import subprocess
import tempfile
import os

def generate_mermaid_image(mermaid_code, output_filename="flowchart.png"):
    """
    将 Mermaid 代码生成 PNG 图片。

    参数:
        mermaid_code (str): Mermaid 流程图代码。
        output_filename (str): 输出的图片文件名。
    """
    # 使用临时文件来存储 mermaid 代码，避免冲突
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as tmp_file:
        tmp_file.write(mermaid_code)
        temp_mmd_path = tmp_file.name

    try:
        # 构建 mmdc 命令
        # 提示：-t 参数可以指定内置主题，例如 'default'， 'forest'， 'dark'， 'neutral'
        cmd = [
            'mmdc',
            '-i', temp_mmd_path,
            '-o', output_filename,
            '-t', 'default',  # 可选主题
            '-b', 'white',    # 背景色
            '-w', '1920',     # 图片宽度
            '-H', '1080'      # 图片高度
        ]

        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"流程图已成功生成: {output_filename}")
        else:
            print(f"生成失败: {result.stderr}")
    finally:
        # 清理临时文件
        os.unlink(temp_mmd_path)

# 你的 Mermaid 代码
mermaid_code = """
graph TD
    A[开始] --> B{周期在误差范围内是否一致？};
    B --o|是| C[执行加权平均<br>输出合并后的周期与误差];
    B --x|否| D{检查是否为常见谐波关系？};
    D --o|是| E[识别为谐波关系<br>输出基频周期];
    D --x|否| F[认定为独立信号<br>输出两个独立周期];
"""
generate_mermaid_image(mermaid_code, ".\\my_flowchart.png")