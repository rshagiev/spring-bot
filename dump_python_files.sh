#!/bin/bash

# Убедимся, что tree установлен
if ! command -v tree &> /dev/null
then
    echo "❌ Утилита 'tree' не установлена. Установите через 'brew install tree'"
    exit 1
fi

PROJECT_DIR="$(pwd)"
OUTPUT_FILE="$PROJECT_DIR/project_dump.txt"
DATE_STR=$(date)

# Заголовок
echo "🧠 Python Project Dump for LLM — $(basename "$PROJECT_DIR")" > "$OUTPUT_FILE"
echo "📅 Date: $DATE_STR" >> "$OUTPUT_FILE"
echo "📂 Path: $PROJECT_DIR" >> "$OUTPUT_FILE"
echo "==============================================" >> "$OUTPUT_FILE"

# Структура проекта
echo -e "\n\n📁 Project Structure (tree -L 3):\n----------------------------------------------" >> "$OUTPUT_FILE"
tree -I '__pycache__|.git|env|venv|*.pyc' -L 3 >> "$OUTPUT_FILE"

# Requirements
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
  echo -e "\n\n📦 requirements.txt:\n----------------------------------------------" >> "$OUTPUT_FILE"
  cat "$PROJECT_DIR/requirements.txt" >> "$OUTPUT_FILE"
fi

# Содержимое всех .py файлов
echo -e "\n\n📝 Python Files:\n==============================================" >> "$OUTPUT_FILE"

find "$PROJECT_DIR" -type f -name "*.py" \
    ! -path "*/__pycache__/*" \
    ! -path "*/venv/*" \
    ! -path "*/env/*" \
    ! -path "*/.git/*" \
| sort | while read -r FILE
do
  REL_PATH="${FILE#$PROJECT_DIR/}"
  echo -e "\n\n🔹 File: $REL_PATH\n----------------------------------------------" >> "$OUTPUT_FILE"
  cat "$FILE" >> "$OUTPUT_FILE"
done

# Завершение
echo -e "\n\n✅ Dump completed: $OUTPUT_FILE"
echo "You can now copy and paste blocks into ChatGPT or another LLM assistant."