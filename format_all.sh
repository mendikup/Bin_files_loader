#!/bin/bash
echo "🧹 Formatting and sorting imports..."

# הפעל את הכלים דרך הנתיב המלא בתוך ה-venv
python -m isort src
python -m black src

echo "✅ Done formatting!"
