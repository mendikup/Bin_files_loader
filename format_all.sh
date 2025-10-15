#!/bin/bash
echo "🧹 Formatting and sorting imports..."
isort src --line-length 120
black src --line-length 120
echo "✅ Done formatting!"
