#!/bin/bash

# This script runs the investigator main.py script and pipes the output to the gemini command.

# Check if a CVE ID and batch ID is provided
if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: $0 <CVE_ID> <BATCH_ID>"
  exit 1
fi

CVE_ID=$1
BATCH_ID=$2

# Get the directory of this script
SCRIPT_DIR=$(dirname "$0")

# Change to the script directory. This is important because the script later does a cd into the CVE directory.
cd "$SCRIPT_DIR" || exit

# Create outputs directory if it doesn't exist
mkdir -p "outputs"

# Run extraction script
python3 "extract.py" --cve "$CVE_ID"

# Check if extraction was successful
if [ ! -d "$CVE_ID" ]; then
    echo "Extraction failed. Directory $CVE_ID not found."
    exit 1
fi

cd "$CVE_ID" || exit

# Define output files
PROMPT_FILE="../outputs/${CVE_ID}_${BATCH_ID}_prompt.md"
RESPONSE_FILE="../outputs/${CVE_ID}_${BATCH_ID}_response"

# Run the python script, save the prompt, pipe to gemini, and save the response
python3 "../main.py" --cve "$CVE_ID" --batch_id "$BATCH_ID" | tee "$PROMPT_FILE" | gemini | tee "$RESPONSE_FILE"