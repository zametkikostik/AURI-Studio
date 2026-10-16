#!/data/data/com.termux/files/usr/bin/bash
set -e
echo "=== AURI Studio — Termux installer ==="

pkg update -y
pkg install -y python ffmpeg redis git

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo ">>> Отредактируйте .env и вставьте OPENROUTER_API_KEY"
  echo "    nano .env"
fi

echo ""
echo "Установка завершена."
echo "Запуск: bash run-termux.sh"
