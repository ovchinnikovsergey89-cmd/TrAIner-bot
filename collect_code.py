import os

# Папки, которые нужно игнорировать
IGNORE_DIRS = {'.git', '__pycache__', 'venv', 'env', '.idea', '.vscode', 'build', 'dist'}
# Расширения файлов, которые нужно брать (добавьте .html или .json если нужно)
EXTENSIONS = {'.py', '.txt', '.md', '.json', '.yaml', '.yml'}

output_file = 'project_code.txt'

with open(output_file, 'w', encoding='utf-8') as outfile:
    # Записываем структуру папок (дерево)
    outfile.write("=== STRUCTURE ===\n")
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        level = root.replace('.', '').count(os.sep)
        indent = ' ' * 4 * (level)
        outfile.write(f"{indent}{os.path.basename(root)}/\n")
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            if any(f.endswith(ext) for ext in EXTENSIONS) and f != output_file and f != 'collect_code.py':
                outfile.write(f"{subindent}{f}\n")
    outfile.write("\n" + "="*20 + "\n\n")

    # Записываем содержимое файлов
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS] # Исключаем папки
        
        for file in files:
            if any(file.endswith(ext) for ext in EXTENSIONS) and file != output_file and file != 'collect_code.py':
                path = os.path.join(root, file)
                outfile.write(f"\n{'='*10} START FILE: {path} {'='*10}\n")
                try:
                    with open(path, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"Error reading file: {e}")
                outfile.write(f"\n{'='*10} END FILE: {path} {'='*10}\n")

print(f"Готово! Весь код сохранен в файле {output_file}")