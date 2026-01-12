import os
from pathlib import Path

# ================= 配置区域 =================
# 1. 目标文件夹路径 (请确认路径存在)
TARGET_DIR = r"E:\图书管理系统1\LibraryManage"

# 2. 输出文件名
OUTPUT_FILE = "项目全貌.txt"

# 3. 需要提取的后缀
TARGET_EXTENSIONS = {'.py', '.html'}

# 4. 需要忽略的文件夹 (避免扫描虚拟环境或Git目录)
IGNORE_DIRS = {'.git', '.idea', '__pycache__', 'venv', '.vscode', 'node_modules'}


# ===========================================

def get_file_content(file_path):
    """
    尝试读取文件内容，自动处理编码问题 (UTF-8 或 GBK)
    """
    try:
        # 优先尝试 utf-8
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            # 失败则尝试 gbk (Windows常见中文编码)
            with open(file_path, 'r', encoding='gbk') as f:
                return f.read()
        except Exception:
            return f"# 错误：无法读取此文件 (可能包含二进制内容或特殊编码): {file_path.name}"
    except Exception as e:
        return f"# 读取错误: {str(e)}"


def generate_tree_and_collect(directory, collected_files, prefix=""):
    """
    1. 生成目录树字符串
    2. 将符合条件的文件路径收集到 collected_files 列表中
    """
    directory = Path(directory)
    tree_str = ""

    try:
        entries = sorted(list(directory.iterdir()), key=lambda x: x.name.lower())
    except PermissionError:
        return "", []

    # 过滤列表
    filtered_entries = []
    for entry in entries:
        if entry.is_dir():
            if entry.name not in IGNORE_DIRS:
                filtered_entries.append(entry)
        elif entry.is_file():
            if entry.suffix.lower() in TARGET_EXTENSIONS:
                filtered_entries.append(entry)

    entries_count = len(filtered_entries)

    for index, entry in enumerate(filtered_entries):
        connector = "└── " if index == entries_count - 1 else "├── "
        tree_str += f"{prefix}{connector}{entry.name}\n"

        if entry.is_file():
            # 收集文件路径用于后续读取内容
            collected_files.append(entry)

        if entry.is_dir():
            extension = "    " if index == entries_count - 1 else "│   "
            sub_tree = generate_tree_and_collect(entry, collected_files, prefix + extension)
            tree_str += sub_tree

    return tree_str


def main():
    base_path = Path(TARGET_DIR)

    if not base_path.exists():
        print(f"❌ 错误：找不到路径 {TARGET_DIR}")
        return

    print(f"🚀 正在扫描: {TARGET_DIR} ...")

    # 容器：用于存放扫描到的文件对象
    files_to_read = []

    # --- 第一步：生成结构树 ---
    tree_content = generate_tree_and_collect(base_path, files_to_read)

    # 准备写入的内容列表
    output_lines = []

    # 写入标题和结构树
    output_lines.append(f"# 项目全貌: {base_path.name}")
    output_lines.append(f"> 生成时间: {os.path.basename(__file__)}")
    output_lines.append("\n## 1. 项目目录结构")
    output_lines.append("```text")
    output_lines.append(base_path.name)
    output_lines.append(tree_content if tree_content else "    (无符合条件的文件)")
    output_lines.append("```")

    # --- 第二步：写入文件代码内容 ---
    output_lines.append(f"\n## 2. 文件代码详情 (共 {len(files_to_read)} 个文件)")

    for file_path in files_to_read:
        # 获取相对路径，做标题用
        relative_path = file_path.relative_to(base_path)
        file_ext = file_path.suffix.lower().replace('.', '')  # py, html

        # 针对 markdown 语法的小调整
        lang_tag = file_ext
        if lang_tag == 'py': lang_tag = 'python'

        content = get_file_content(file_path)

        output_lines.append(f"\n### 📄 {relative_path}")
        output_lines.append(f"```{lang_tag}")
        output_lines.append(content)
        output_lines.append("```")
        output_lines.append("---")  # 分割线

    # --- 第三步：保存到文件 ---
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        print(f"✅ 完成！")
        print(f"📂 统计: 扫描了 {len(files_to_read)} 个文件")
        print(f"📄 结果已保存为: {os.path.abspath(OUTPUT_FILE)}")
    except Exception as e:
        print(f"❌ 写入失败: {e}")


if __name__ == "__main__":
    main()