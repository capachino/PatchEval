#!/bin/bash

# Script to run local investigation for a given CVE ID
# 1) Extracts the image workspace to a local directory named {CVE ID}
# 2) Writes a `problem_statement.md` file with details about the CVE which can be used in prompts or context for commands
# 3) Adjusts paths in `vul-run.sh` so it can run locally. This script is used to run the PoC test
#
# Note: re-running this script for the same CVE ID will overwrite the existing directory, 
# which often is intended to try different approaches.

# Exit on error, and treat pipeline errors as failures
set -e
set -o pipefail

# Check if a CVE ID is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <CVE_ID>"
  exit 1
fi

CVE_ID=$1

# Run extraction script
# Use -u for unbuffered output so logs appear instantly
python3 -u "extract.py" --cve "$CVE_ID"

# Check if extraction was successful
if [ ! -d "$CVE_ID" ]; then
    echo "Extraction failed. Directory $CVE_ID not found."
    exit 1
fi

python3 -u "local.py" --cve "$CVE_ID"
