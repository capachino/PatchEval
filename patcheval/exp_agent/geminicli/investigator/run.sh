#!/bin/bash

# Exit on error, and treat pipeline errors as failures
set -e
set -o pipefail

# Check if a CVE ID and batch ID is provided
if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: $0 <CVE_ID> <BATCH_ID>"
  exit 1
fi

CVE_ID=$1
BATCH_ID=$2

# Get the directory of this script
SCRIPT_DIR=$(dirname "$0")

# Change to the script directory
cd "$SCRIPT_DIR" || exit

# Create outputs directory
mkdir -p "outputs"

# Run extraction script
# Use -u for unbuffered output so logs appear instantly
python3 -u "extract.py" --cve "$CVE_ID"

# Check if extraction was successful
if [ ! -d "$CVE_ID" ]; then
    echo "Extraction failed. Directory $CVE_ID not found."
    exit 1
fi

cd "$CVE_ID" || exit

# Define output file paths
PROMPT_FILE="../outputs/${CVE_ID}_${BATCH_ID}_prompt.md"
RESPONSE_FILE="../outputs/${CVE_ID}_${BATCH_ID}_response"

# Run the python script, save the prompt to a file, and call gemini with -i
# python3 -u "../main.py" --cve "$CVE_ID" --batch_id "$BATCH_ID" | tee "$PROMPT_FILE" | gemini | tee "$RESPONSE_FILE"
python3 -u "../main.py" --cve "$CVE_ID" --batch_id "$BATCH_ID" > "$PROMPT_FILE"
gemini -i "$(cat "$PROMPT_FILE")"