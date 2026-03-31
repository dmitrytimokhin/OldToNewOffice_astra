import os

def print_project_structure(start_path, ignore_dirs=None, ignore_files=None):
    """
    Рекурсивно выводит структуру проекта в терминал.
    :param start_path: корневая директория проекта
    :param ignore_dirs: список папок, которые нужно игнорировать
    :param ignore_files: список файлов, которые нужно игнорировать
    """
    if ignore_dirs is None:
        ignore_dirs = ['.git', '__pycache__', 'venv', '.idea', '.venv', 'env']
    if ignore_files is None:
        ignore_files = ['.pyc', '.pyo', '.DS_Store', '.log', '.tmp']

    print(f"📁 {os.path.basename(start_path)}/")

    for root, dirs, files in os.walk(start_path):
        level = root.replace(start_path, '').count(os.sep)
        indent = '│   ' * level + "├── " if level > 0 else ""

        if level > 0:
            print(f"{indent}{os.path.basename(root)}/")

        # Фильтруем игнорируемые директории
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        sub_indent = '│   ' * (level + 1) + "├── "

        # Выводим файлы, исключая игнорируемые
        for f in sorted(files):
            if any(f.endswith(ext) for ext in ignore_files):
                continue
            print(f"{sub_indent}{f}")

if __name__ == "__main__":
    project_root = "."  # Можно изменить на нужный путь, например: "my_bot_project/"
    print_project_structure(project_root)