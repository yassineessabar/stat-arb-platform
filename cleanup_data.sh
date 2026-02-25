#!/bin/bash

echo "=============================="
echo "🧹 CLEANING UP DATA FILES"
echo "=============================="

# Remove backtest result files
echo "Removing backtest results..."
rm -f backtest_results_*.pkl
rm -f backtest_plot_*.png

# Remove log files
echo "Removing log files..."
rm -f backtest.log
rm -f *.log

# Remove any temporary test files
echo "Removing test files..."
rm -f test_*.py
rm -f temp_*.json

# Remove __pycache__ directories
echo "Removing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Remove .pyc files
find . -name "*.pyc" -delete 2>/dev/null

echo ""
echo "✅ Data cleanup complete!"
echo ""
echo "Files kept:"
echo "- Source code (*.py)"
echo "- Configuration files (*.json, *.yaml)"
echo "- Documentation (*.md)"
echo ""