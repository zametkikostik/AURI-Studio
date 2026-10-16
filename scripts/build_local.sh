#!/usr/bin/env bash
# Локальная сборка portable-пакета (Linux)
set -e
cd "$(dirname "$0")/.."

VERSION="${1:-dev}"
OUT="dist/auri-studio-linux-${VERSION}"

echo "Building local portable package → $OUT"
rm -rf dist
mkdir -p "$OUT"

# Копируем исходники
cp -r app templates static scripts packaging "$OUT/"
cp .env.example README.md requirements.txt Dockerfile docker-compose.yml "$OUT/"
cp packaging/run-linux.sh "$OUT/"
chmod +x "$OUT/run-linux.sh" "$OUT/scripts/"*.sh "$OUT/packaging/"*.sh 2>/dev/null || true

# Архив
cd dist
tar -czf "auri-studio-linux-${VERSION}.tar.gz" "auri-studio-linux-${VERSION}"
echo "Done: dist/auri-studio-linux-${VERSION}.tar.gz"
ls -lh "auri-studio-linux-${VERSION}.tar.gz"
