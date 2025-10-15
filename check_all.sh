#!/bin/bash
echo "🔍 Checking code style with isort, black, mypy, pylint..."
isort src --check --diff --line-length 120 || exit 1
black src --check --line-length 120 || exit 1
mypy src || exit 1
pylint src || exit 1
echo "✅ All checks passed!"
