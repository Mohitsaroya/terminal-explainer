#!/usr/bin/env bash
# Create the practice folder used by study/tasks.md.
#   bash study/seed.sh [target-folder]   (default: ./practice)
set -euo pipefail

root="${1:-practice}"
rm -rf "$root"
mkdir -p "$root"/{downloads,project/src,notes}
cd "$root"

for i in 1 2 3; do echo "meeting notes $i" > "downloads/notes-$i.txt"; done
echo "holiday photo" > downloads/beach.jpg
echo "report draft" > downloads/report.docx
echo "keep me" > notes/important.txt
echo "scratch" > notes/scratch.txt
echo "old todo" > notes/todo.txt
echo "the secret recipe" > project/src/.hidden-recipe.md

cat > project/src/app.py <<'PY'
import requests  # task 5: fails until the package is installed

print("app is running")
PY

cat > project/src/broken.py <<'PY'
def greet(name)
    print(f"hello {name}")
PY

echo "Seeded practice folder at $(pwd)"
