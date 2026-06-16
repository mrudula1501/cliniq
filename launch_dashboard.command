#!/bin/bash
# ClinIQ — Launch Live Dashboard
# Double-click this in Finder to open the dashboard in your browser
cd "$(dirname "$0")"

echo ""
echo "============================================="
echo "  ClinIQ Dashboard — Starting"
echo "============================================="
echo ""

# Install streamlit and plotly if needed
echo "Checking dependencies..."
pip3 install streamlit plotly pandas python-dotenv snowflake-connector-python --quiet --break-system-packages 2>/dev/null || \
pip3 install streamlit plotly pandas python-dotenv snowflake-connector-python --quiet
echo "  ✓ Dependencies ready"
echo ""

# Find streamlit
STREAMLIT=$(which streamlit 2>/dev/null)
if [ -z "$STREAMLIT" ]; then
    for dir in \
        "/Library/Frameworks/Python.framework/Versions/3.11/bin" \
        "/Library/Frameworks/Python.framework/Versions/3.12/bin" \
        "$HOME/Library/Python/3.11/bin" \
        "$HOME/Library/Python/3.12/bin" \
        "/usr/local/bin"; do
        [ -f "$dir/streamlit" ] && STREAMLIT="$dir/streamlit" && break
    done
fi

if [ -z "$STREAMLIT" ]; then
    echo "  Streamlit not found in PATH, using python3 -m streamlit"
    STREAMLIT="python3 -m streamlit"
fi

echo "  Opening dashboard at http://localhost:8501"
echo "  Press Ctrl+C to stop"
echo ""

$STREAMLIT run dashboard/app.py \
    --server.port 8501 \
    --server.headless false \
    --browser.gatherUsageStats false \
    --theme.base light \
    --theme.primaryColor "#1F6FEB" \
    --theme.backgroundColor "#F0F4F8" \
    --theme.secondaryBackgroundColor "#FFFFFF"
