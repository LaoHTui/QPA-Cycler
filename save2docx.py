import json
import os
import re
from collections import defaultdict
from datetime import datetime

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.oxml.shared import OxmlElement
from docx.oxml.shared import qn
from docx.shared import Inches, Pt, Cm, RGBColor

from File_operations import gen_simulated_data as gsd



def save_state(state, state_path, filename='state.json'):
    """
    保存程序状态到指定文件。

    参数:
    - state: 要保存的程序状态，通常为一个字典。
    - filename: 保存状态的文件名，默认为'state.json'。

    该函数将程序状态转换为JSON格式并保存到指定的文件中。
    """
    with open(os.path.join(state_path, f'{filename}.json'), 'w') as f:
        json.dump(state, f, indent=4, ensure_ascii=False)


def load_state(state_path, filename='state.json'):
    """
    从指定文件加载程序状态。

    参数:
    - filename: 要加载状态的文件名，默认为'state.json'。

    返回:
    - 如果文件存在且包含有效的JSON数据，则返回加载的程序状态。
    - 如果文件不存在或为空，则返回None。
    """
    file_path = os.path.join(state_path, f'{filename}.json')
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    else:
        return None


# 创建默认占位图片
def create_placeholder_image(marker, width=400, height=300):
    """创建默认占位图片"""
    # 创建白色背景图片
    img = Image.new('RGB', (width, height), color='white')
    d = ImageDraw.Draw(img)

    # 尝试使用默认字体
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()

    # 添加文本
    text = f"No {marker} Image"
    text_width = d.textlength(text, font=font)
    text_height = 20
    d.text(((width - text_width) / 2, (height - text_height) / 2),
           text, fill='black', font=font)

    # 确保目录存在
    temp_dir = 'temp_images'
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # 保存图片
    path = f'{temp_dir}/placeholder_{marker}.png'
    img.save(path)
    return path

# 获取并排序图片文件
def get_sorted_images(image_dir):
    """获取并排序图片文件，按数字分组并按指定顺序排序"""
    if not os.path.exists(image_dir):
        return {}

    # 获取所有图片文件
    image_files = [f for f in os.listdir(image_dir) if f.endswith(('.png', '.jpg', '.jpeg', '.bmp'))]

    # 按数字前缀分组
    grouped_images = defaultdict(list)
    for img_file in image_files:
        # 使用正则表达式提取数字前缀
        match = re.match(r'^(\d+)_', img_file)
        if match:
            group_num = int(match.group(1))
            grouped_images[group_num].append(img_file)

    # 按组号排序
    sorted_groups = sorted(grouped_images.items())

    # 定义排序顺序
    sort_order = ['LSP', 'DCF', 'JV', 'WWZ']

    # 对每组内的图片按指定顺序排序
    result = {}
    for group_num, images in sorted_groups:
        # 创建一个字典，键为标识符，值为文件名
        marker_dict = {}
        for img in images:
            # 修改正则表达式以适配您的文件名格式
            # 从文件名中提取标识符（最后一个下划线后的部分，去掉扩展名）
            marker = re.search(r'_([A-Za-z]+)\.\w+$', img)
            if marker:
                marker_dict[marker.group(1)] = img
            else:
                # 如果无法提取标识符，尝试其他方法
                # 例如，从文件名中提取最后一部分（不含扩展名）
                filename_without_ext = os.path.splitext(img)[0]
                parts = filename_without_ext.split('_')
                if parts:
                    last_part = parts[-1]
                    if last_part in sort_order:
                        marker_dict[last_part] = img

        # 按指定顺序排序，如果缺少图片则使用占位图片
        sorted_images = []
        for marker in sort_order:
            if marker in marker_dict:
                sorted_images.append(os.path.join(image_dir, marker_dict[marker]))
            else:
                # 使用占位图片
                placeholder_path = create_placeholder_image(marker)
                sorted_images.append(placeholder_path)

        result[group_num] = sorted_images
        # print(sorted_images)

    return result


# 设置无边框表格
def set_no_border_table(table):
    """设置表格为无边框"""
    tbl = table._tbl
    tblPr = tbl.tblPr

    # 检查是否存在tblBorders元素，如果不存在则创建
    if tblPr.xpath('w:tblBorders') == []:
        tblBorders = parse_xml(r'<w:tblBorders {}><w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
                               r'<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/><w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
                               r'<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/><w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
                               r'<w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/></w:tblBorders>'.format(
            nsdecls('w')))
        tblPr.append(tblBorders)
    else:
        # 如果已存在，则修改边框属性
        for border in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            border_tag = tblPr.xpath('w:tblBorders/w:{}'.format(border))[0]
            border_tag.set(qn('w:val'), 'none')
            border_tag.set(qn('w:sz'), '0')
            border_tag.set(qn('w:space'), '0')
            border_tag.set(qn('w:color'), 'auto')


# 添加书签
def add_bookmark(paragraph, bookmark_name):
    """在段落中添加书签"""
    run = paragraph.add_run()
    tag = run._r
    start = parse_xml(r'<w:bookmarkStart {} w:id="0" w:name="{}"/>'.format(nsdecls('w'), bookmark_name))
    end = parse_xml(r'<w:bookmarkEnd {} w:id="0"/>'.format(nsdecls('w')))
    tag.append(start)
    tag.append(end)


# 设置页脚和页码
def setup_footer(doc):
    """设置页脚和页码"""
    section = doc.sections[0]
    footer = section.footer

    # 清除默认的页脚段落
    for paragraph in footer.paragraphs:
        p = paragraph._element
        p.getparent().remove(p)

    # 添加居中的页码
    paragraph = footer.paragraphs[0] if len(footer.paragraphs) > 0 else footer.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    fld_char1 = parse_xml(r'<w:fldChar {} w:fldCharType="begin"/>'.format(nsdecls('w')))
    fld_char2 = parse_xml(r'<w:fldChar {} w:fldCharType="separate"/>'.format(nsdecls('w')))
    fld_char3 = parse_xml(r'<w:fldChar {} w:fldCharType="end"/>'.format(nsdecls('w')))

    run._r.append(fld_char1)
    run._r.append(parse_xml(r'<w:instrText {} xml:space="preserve">PAGE </w:instrText>'.format(nsdecls('w'))))
    run._r.append(fld_char2)
    run._r.append(parse_xml(r'<w:t {}>1</w:t>'.format(nsdecls('w'))))
    run._r.append(fld_char3)


def setup_header(doc, program_name="Program"):
    """设置页眉，左边写程序名，右边写日期"""
    section = doc.sections[0]
    header = section.header

    # 清除默认的页眉段落
    for paragraph in header.paragraphs:
        p = paragraph._element
        p.getparent().remove(p)

    # 添加页眉表格（用于左右布局）
    table = header.add_table(rows=1, cols=2, width=Inches(7.4))  # 添加width参数
    table.style = 'Table Grid'
    table.autofit = False

    # 设置表格列宽
    table.columns[0].width = Inches(3)
    table.columns[1].width = Inches(3)
    set_no_border_table(table)

    # 获取当前日期
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 左边单元格：程序名称
    left_cell = table.cell(0, 0)
    left_paragraph = left_cell.paragraphs[0]
    left_run = left_paragraph.add_run(program_name)
    left_run.bold = True

    # 右边单元格：日期
    right_cell = table.cell(0, 1)
    right_paragraph = right_cell.paragraphs[0]
    right_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    right_run = right_paragraph.add_run(current_date)


# 添加参数表格到文档
def add_parameters_table(doc, params_dict, title="Parameter Settings"):
    """将参数字典添加为表格到Word文档"""
    # 添加标题
    doc.add_heading(title, level=1)

    # 遍历参数字典的每个部分
    for section_name, section_params in params_dict.items():
        # 添加部分标题
        doc.add_heading(section_name, level=2)

        # 创建表格
        table = doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'

        # 设置表头
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Parameter Name'
        hdr_cells[1].text = 'Parameter Value'

        # 设置表头样式
        for cell in hdr_cells:
            paragraph = cell.paragraphs[0]
            run = paragraph.runs[0]
            run.bold = True

        # 添加参数行
        for param_name, param_value in section_params.items():
            row_cells = table.add_row().cells
            row_cells[0].text = str(param_name)
            row_cells[1].text = str(param_value)

        # 添加空行
        doc.add_paragraph()

    # 添加分页符
    doc.add_page_break()


# 从JSON文件读取参数
def load_params_from_json(file_path):
    """从JSON文件读取参数"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return None


def set_cell_border(cell, border_dict):
    """
    Set cell's border according to border_dict

    border_dict: {
        'top': {'sz': 8, 'val': 'single', 'color': '#000000'},
        'bottom': {'sz': 8, 'val': 'single', 'color': '#000000'},
        'start': {'sz': 0, 'val': 'none', 'color': '#FFFFFF'},
        'end': {'sz': 0, 'val': 'none', 'color': '#FFFFFF'}
    }
    """
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()

    # Check for tag existence, if none found, then create one
    tcBorders = tcPr.first_child_found_in('w:tcBorders')
    if tcBorders is None:
        tcBorders = OxmlElement('w:tcBorders')
        tcPr.append(tcBorders)

    # List over all available tags
    for edge in ('start', 'top', 'end', 'bottom', 'insideH', 'insideV'):
        edge_data = border_dict.get(edge)
        if edge_data:
            tag = 'w:{}'.format(edge)

            # Check for tag existence, if none found, then create one
            element = tcBorders.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                tcBorders.append(element)

            # Set border attributes
            for key, value in edge_data.items():
                element.set(qn('w:{}'.format(key)), value)
def get_grouped_images_name(candidate:dict) -> dict:
    name_dict = {}
    for key, value in candidate.items():
        name_dict[key] = value["source"]
    return name_dict


def create_running_results_2_word(data_dict, grouped_images_path, custom_group_names, json_params, label_dict=None,
                                  title=None, conclusion_text=None, output_filename='./示例测试数据表格输出.docx',
                                  image_width=3.5, table_row_height=4, table_cell_width=3, simulate= False):
    """
    Create a proper three-line table in a Word document
    custom_group_names = {
        1: "Experimental Group A",
        2: "Control Group B",
        3: "Validation Group C"
    }

    Parameters:
    - image_width: Width of each image in inches (default: 2.0)
    - table_row_height: Height of table rows in inches (default: 2.5)
    - table_cell_width: Width of table cells in inches (default: 2.8)
    """

    # 获取并排序图片
    grouped_im = get_sorted_images(grouped_images_path)

    data = pd.DataFrame(data_dict)
    doc = Document()

    # 设置页面边距
    sections = doc.sections
    for section in sections:
        section.top_margin = Cm(1.5)  # 减小边距
        section.bottom_margin = Cm(1.5)
        section.left_margin = Cm(1.5)
        section.right_margin = Cm(1.5)

    # 设置页脚和页码
    setup_footer(doc)

    # 设置页眉
    setup_header(doc, "QPA-Cycler0.3")

    if title:
        # Add title
        heading = doc.add_heading(level=1)
        heading_run = heading.add_run(title)
        heading_run.bold = True
        heading_run.font.size = Pt(14)  # 设置字体大小
        heading_run.font.color.rgb = RGBColor(0, 0, 0)  # 设置字体颜色（黑色）
        heading_run.font.name = 'Times New Roman'  # 设置字体
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph()
        # Add some space after the title
        # doc.add_paragraph()
    if conclusion_text:
        # doc.add_paragraph()  # 添加空行
        conclusion_paragraph = doc.add_paragraph()
        conclusion_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        conclusion_run = conclusion_paragraph.add_run(conclusion_text)
        conclusion_run.font.size = Pt(10)
        conclusion_run.font.name = 'Times New Roman'
        conclusion_run.italic = False  # 斜体

    # Create table
    table = doc.add_table(rows=len(data) + 1, cols=len(data.columns))

    # Set table style to remove all borders initially
    table.style = 'Table Grid'

    # Set header row
    for j, column_name in enumerate(data.columns):
        cell = table.cell(0, j)
        cell.text = str(column_name)
        # Set font to bold
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True
                # 添加以下代码设置字体
                run.font.size = Pt(12)  # 设置字体大小
                run.font.color.rgb = RGBColor(0, 0, 0)  # 设置字体颜色
                run.font.name = 'Times New Roman'  # 设置字体
        # Center alignment
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Fill data
    for i, row in enumerate(data.itertuples(), 1):
        for j, value in enumerate(row[1:], 0):
            cell = table.cell(i, j)
            cell.text = str(value)
            # 添加以下代码设置字体
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(10)  # 设置字体大小
                    run.font.color.rgb = RGBColor(0, 0, 0)  # 设置字体颜色
                    run.font.name = 'Times New Roman'  # 设置字体
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    # Define border settings for three-line table
    # Top and bottom borders will be visible, side borders will be hidden
    border_settings = {
        'top': {'sz': '6', 'val': 'single', 'color': '#000000'},
        'bottom': {'sz': '6', 'val': 'single', 'color': '#000000'},
        'start': {'sz': '0', 'val': 'none', 'color': '#FFFFFF'},
        'end': {'sz': '0', 'val': 'none', 'color': '#FFFFFF'},
        'insideH': {'sz': '0', 'val': 'none', 'color': '#FFFFFF'},
        'insideV': {'sz': '0', 'val': 'none', 'color': '#FFFFFF'}
    }

    # Apply border settings to all cells to remove vertical lines
    for row in table.rows:
        for cell in row.cells:
            set_cell_border(cell, border_settings)

    # Now add special border for header row (bottom border)
    header_border = border_settings.copy()
    header_border['bottom'] = {'sz': '8', 'val': 'single', 'color': '#000000'}
    for j in range(len(data.columns)):
        set_cell_border(table.cell(0, j), header_border)

    # Add bottom border to last row
    for j in range(len(data.columns)):
        set_cell_border(table.cell(len(data), j), border_settings)

    # 添加参数表格（如果有）
    if json_params and 'auto' in json_params:
        add_parameters_table(doc, json_params['auto'], "Analysis Parameter Settings")
    if simulate and json_params and 'simulate_params' in json_params:
        sim_params_dict = {"simulate_params": json_params['simulate_params']}
        add_parameters_table(doc,sim_params_dict , "Simulation Parameter Settings")
    # 创建多个图片组
    doc.add_heading("Image Groups", level=1)
    for group_num, image_paths in grouped_im.items():

        # 使用自定义组名或默认组名
        if group_num in custom_group_names:
            group_title = custom_group_names[group_num]
        else:
            group_title = f"分组{group_num}"
            # 可以选择记录日志
            print(f"警告：分组 {group_num} 没有自定义名称，使用默认值")

        # 添加组标题（使用Word的标题样式）
        heading = doc.add_heading(group_title, level=2)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 添加书签
        add_bookmark(heading, f'group_{group_num}')

        # 创建2x2表格用于四宫格布局
        table = doc.add_table(rows=2, cols=2)

        # 设置表格为无边框
        set_no_border_table(table)

        # 使用传入的参数设置表格宽度和高度
        for row in table.rows:
            row.height = Inches(table_row_height)  # 使用参数设置表格行高
            for cell in row.cells:
                cell.width = Inches(table_cell_width)  # 使用参数设置表格单元格宽度

        # 设置表格单元格边距为0
        tbl = table._tbl
        tblPr = tbl.tblPr
        tblCellMar = parse_xml(
            r'<w:tblCellMar {}><w:top w:w="0" w:type="dxa"/><w:left w:w="0" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="0" w:type="dxa"/></w:tblCellMar>'.format(
                nsdecls('w')))
        tblPr.append(tblCellMar)

        # 定义排序顺序
        sort_order = ['LSP', 'DCF', 'JV', 'WWZ']

        # 将图片添加到表格单元格中
        for i, marker in enumerate(sort_order):
            if i >= 4:  # 只处理前4个位置
                break

            row = i // 2
            col = i % 2
            cell = table.cell(row, col)

            # 清除默认段落
            cell.paragraphs[0].clear()

            # 添加图片到单元格
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

            # 获取当前标记对应的图片路径
            image_path = image_paths[i] if i < len(image_paths) else None

            # 检查图片是否存在
            if image_path and os.path.exists(image_path) and "placeholder" not in image_path:
                run = paragraph.add_run()
                run.add_picture(image_path, width=Inches(image_width))  # 使用参数设置图片宽度
            else:
                # 如果图片不存在或者是占位图片，显示占位文本
                run = paragraph.add_run()
                run.text = f"No {marker} Image"
                run.italic = True
                run.font.color.rgb = RGBColor(128, 128, 128)  # 灰色文本

            # 添加图片标题
            title_paragraph = cell.add_paragraph()
            title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            title_run = title_paragraph.add_run(f'{marker}')
            title_run.bold = True
            title_run.font.size = Pt(10)  # 减小字体大小

        if label_dict and f"{group_num}" in label_dict:
            heading = doc.add_heading("Detailed Information", level=3)

            # 获取标题中的run对象
            heading_run = heading.runs[0]

            # 设置字体属性
            heading_run.font.name = 'Times New Roman'  # 设置字体
            heading_run.font.size = Pt(12)  # 设置字体大小
            heading_run.bold = True  # 设置为粗体
            heading_run.font.color.rgb = RGBColor(0, 0, 0)  # 设置字体颜色（黑色）
            heading_run.alignment = WD_ALIGN_PARAGRAPH.CENTER

            # 获取该组的标签字符串
            label_str = label_dict[f"{group_num}"]

            # 按分号分割不同的周期信息
            period_parts = label_str.split(';')

            for part in period_parts:
                part = part.strip()  # 去除前后空格
                if not part:
                    continue

                # 创建新段落
                period_paragraph = doc.add_paragraph()
                period_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

                # 尝试提取Period编号
                period_match = re.search(r'Period (\d+):', part)

                if period_match:
                    # 提取Period编号部分
                    period_num = period_match.group(0)
                    period_text = period_num  # "Period X:"

                    # 剩余文本
                    remaining_text = part[len(period_num):].strip()

                    # 添加Period编号部分（加粗放大）
                    period_run = period_paragraph.add_run(period_text)
                    period_run.font.size = Pt(12)  # 比正常文本大2pt
                    period_run.font.name = 'Times New Roman'
                    period_run.font.color.rgb = RGBColor(0, 0, 128)
                    period_run.bold = True

                    # 添加剩余文本（正常格式）
                    if remaining_text:
                        # 添加一个空格分隔
                        space_run = period_paragraph.add_run(" ")
                        space_run.font.size = Pt(10)

                        text_run = period_paragraph.add_run(remaining_text)
                        text_run.font.size = Pt(10)
                        text_run.font.name = 'Times New Roman'
                        text_run.bold = False
                else:
                    # 没有Period编号的情况，直接添加整个文本
                    text_run = period_paragraph.add_run(part)
                    text_run.font.size = Pt(10)
                    text_run.font.name = 'Times New Roman'
                    text_run.bold = False

        # 添加分页符（除了最后一组）
        if group_num < max(grouped_im.keys()):
            doc.add_page_break()

    # Save document
    doc.save(output_filename)
    print(f"Word document saved as: {output_filename}")


def reorganize_period_data_list(data_list):
    # 初始化结果字典
    result_dict = {
        "Source Name": [],
    }

    # 首先找出所有可能的周期键（如period_1, period_2等）
    max_period_count = 0
    for item in data_list:
        # 统计每个源有多少个周期
        period_keys = [k for k in item.keys() if k.startswith('period_')]
        max_period_count = max(max_period_count, len(period_keys))

    # 为每个可能的周期创建列
    for i in range(1, max_period_count + 1):
        result_dict[f"Detected Period{i}"] = []
        result_dict[f"Detected Period Error{i}"] = []

    # 填充数据
    for item in data_list:
        result_dict["Source Name"].append(item['source'])

        # 获取所有周期键并按数字排序
        period_keys = sorted([k for k in item.keys() if k.startswith('period_')],
                             key=lambda x: int(x.split('_')[1]))

        # 为每个周期填充数据
        for i in range(1, max_period_count + 1):
            if i <= len(period_keys):
                period_data = item[period_keys[i - 1]] if item[period_keys[i - 1]]["period"] > 0 else {'period': "-", 'period_err': "-"}
                result_dict[f"Detected Period{i}"].append(period_data.get('period', "-"))
                result_dict[f"Detected Period Error{i}"].append(period_data.get('period_err', "-"))
            else:
                # 如果没有这个周期的数据，填充None
                result_dict[f"Detected Period{i}"].append("-")
                result_dict[f"Detected Period Error{i}"].append("-")

    return result_dict

def get_labels(data:dict) -> dict:
    label_dict = {}

    for item in data["afm_dict"]:
        source_num = item["source"].split("_")[0]

        period_labels = []

        for key in sorted(item.keys()):
            if key.startswith("period_"):
                period_data = item[key]
                period_num = int(key.split("_")[1])

                period = period_data.get("period", "N/A")
                period_err = period_data.get("period_err", "N/A")

                # 检查是否确实没有检测到周期
                if period == -1 and period_err == -1:
                    period_info = f"Period {period_num}: LSP Method did not detect a cycle, skip this source"
                elif period != -1 and period_err != -1:
                    # 有有效周期
                    period_str = f"Period {period_num}: {period} ± {period_err} days"
                    label_str = period_data.get('label', 'No label available')
                    period_info = f"For {period_str}, {label_str}"
                else:
                    # 部分数据缺失的情况
                    period_info = f"Period {period_num}: Incomplete data, unable to determine cycle"

                period_labels.append(period_info)

        if period_labels:
            label_dict[source_num] = " ; ".join(period_labels)
    return label_dict

def save2docx(data_path: str, state_dict_filename: str = 'state', json_params_filename: str = 'config',
              title="Report on the Results of the Quasi Periodic Analysis Program for Fermi Data", conclusion_text=None,
              docx_output_path='.\\',
              image_width=3.5, table_row_height=4, table_cell_width=3):
    state_dicts = load_state(fr"{data_path}\Running_Data", state_dict_filename)
    data_dict = reorganize_period_data_list(state_dicts['afm_dict'])

    json_params = load_state(fr"{data_path}\Running_Data", json_params_filename)

    # 创建一个字典，键是组号，值是组名
    custom_group_names = {}
    saved_source_name_list = state_dicts['processed_files']

    for idx, f in enumerate(saved_source_name_list, 1):  # 从1开始计数
        # 分离名字，美观输出
        group_name = f.split("_")[0] + "_" + f.split("_")[1] + f.split("_")[2]
        custom_group_names[idx] = group_name

    current_date = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    label_dict = get_labels(state_dicts)

    create_running_results_2_word(data_dict,
                                  data_path,
                                  custom_group_names,
                                  json_params,
                                  label_dict=label_dict,
                                  title=title,
                                  conclusion_text=conclusion_text,
                                  output_filename=docx_output_path + "\\结果报告" + current_date + ".docx",
                                  image_width=image_width,
                                  table_row_height=table_row_height,
                                  table_cell_width=table_cell_width)

def save2docx_sim(data_path: str, state_dict_filename: str = 'state', json_params_filename: str = 'config',
                      title="Report on the Results of the Quasi Periodic Analysis Program for Simulated  Data",
                      docx_output_path='.\\',
                      image_width=3.5, table_row_height=1, table_cell_width=1):
        """
        生成模拟数据的报告文档，包含检测结果和性能分析

        参数:
        - data_path: 数据存储路径
        - state_dict_filename: 状态字典文件名
        - json_params_filename: 参数配置文件
        - title: 报告标题
        - conclusion_text: 结论文本
        - docx_output_path: Word文档输出路径
        - image_width: 图片宽度(英寸)
        - table_row_height: 表格行高(英寸)
        - table_cell_width: 表格单元格宽度(英寸)
        """
        # 加载状态数据和参数配置
        state_dicts = load_state(os.path.join(data_path, 'Running_Data'), state_dict_filename)
        json_params = load_state(os.path.join(data_path, 'Running_Data'), json_params_filename)

        # # 重组周期数据
        # data_dict = reorganize_period_data_list(state_dicts['afm_dict'])

        # 创建组名映射
        custom_group_names = {}
        name_list = []
        saved_source_name_list = state_dicts['processed_files']

        for idx, f in enumerate(saved_source_name_list, 1):  # 从1开始计数
            group_name = f.split("_")[0] + "_" + f.split("_")[1] + f.split("_")[2]
            custom_group_names[idx] = group_name
            name_list.append(group_name)
        # 生成时间戳
        current_date = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        output_filename = os.path.join(docx_output_path, f"结果报告_{current_date}.docx")

        # 分析周期准确度
        acc_dict = gsd.analyze_period_accuracy(state_dicts['afm_dict'])
        save_state(acc_dict,state_path=os.path.join(data_path, 'Running_Data'), filename="accuracy")

        # 获取准确度数据列表
        docx_dict = gsd.get_accuracy_datalist(acc_dict)
        summary = acc_dict["summary"]
        # 指定排序
        docx_dict = {
            "Source Name": name_list,  # 先放zip
            "Signal Type": docx_dict["Signal Type"],
            "Real Period": docx_dict["Real Period"],
            "Detected Period": docx_dict["Detected Period"],
            "Detected Period Error": docx_dict["Detected Period Error"],
            "Judgment": docx_dict["Judgment"]
        }
        # 创建性能报告文本
        report_text = f"""
        === SIGNAL DETECTION ANALYSIS REPORT ===

        1. File Statistics:
           - Total files analyzed: {summary['total_files']}
           - Periodic signal files: {summary['periodic_files']}
           - Random signal files: {summary['random_files']}

        2. Period Detection Results:
           - Total true periods: {summary['total_true_periods']}
           - Total detected periods: {summary['total_detected_periods']}
           - Correctly detected true periods: {summary['correctly_detected_true_periods']}

        3. File-level Detection Accuracy:
           - Files with strictly correct period detection: {summary['correctly_detected_files_strict']}
           - Files with relaxed correct period detection: {summary['correctly_detected_files_relaxed']}
           - Correctly rejected random signals: {summary['correctly_rejected_random_signals']}

        4. Performance Metrics:
           - Detection rate: {summary['detection_rate'] * 100:.2f}%
           - False positive rate: {summary['false_positive_rate'] * 100:.2f}%
           - Strict accuracy for periodic signals: {summary['strict_accuracy'] * 100:.2f}%
           - Relaxed accuracy for periodic signals: {summary['relaxed_accuracy'] * 100:.2f}%
           - Accuracy for random signals: {summary['random_accuracy'] * 100:.2f}%
           - Overall accuracy: {summary['overall_accuracy'] * 100:.2f}%
        """

        label_dict = get_labels(state_dicts)
        # 创建Word文档
        create_running_results_2_word(
            docx_dict,
            data_path,
            custom_group_names,
            json_params,
            label_dict=label_dict,
            title=title,
            conclusion_text=report_text,
            output_filename=output_filename,
            image_width=image_width,
            table_row_height=table_row_height,
            table_cell_width=table_cell_width,
            simulate=True
        )
if __name__ == '__main__':
    # 对于真实数据
    config_map="config"
    with open(f'{config_map}.json') as f:
        config = json.load(f)
    save2docx(data_path=config["global"]["output_path"],
              state_dict_filename=config["global"]["state_filename"],
              json_params_filename='config',
              docx_output_path=config["global"]["output_path"])

    # # 对于模拟数据
    # config_map = "config"
    # with open(f'{config_map}.json') as f:
    #     config = json.load(f)
    # save2docx_sim(
    #     data_path=config["global"]["output_path"],
    #     title="Simulation Report",
    #     state_dict_filename=config["global"]["state_filename"],
    #     json_params_filename='config',
    #     docx_output_path=config["global"]["output_path"],
    # )

