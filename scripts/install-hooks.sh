#!/bin/sh
# Установить git-хуки из scripts/git-hooks в .git/hooks.
# .git/hooks не версионируется, поэтому на новой машине это нужно сделать руками
# (или этим скриптом): иначе README.md перестанет пересобираться при коммите.

set -e
cd "$(git rev-parse --show-toplevel)" || exit 1

for src in scripts/git-hooks/*; do
    [ -f "$src" ] || continue
    name=$(basename "$src")
    cp "$src" ".git/hooks/$name"
    chmod +x ".git/hooks/$name"
    echo "установлен хук: $name"
done
