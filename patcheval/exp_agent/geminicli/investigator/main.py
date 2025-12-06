import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from docker_utils import extract_workspace_from_image


logger = logging.getLogger(__name__)


def get_project_root() -> Path:
    """Determines the absolute path to the project root."""
    # Assumes this script is in patcheval/exp_agent/geminicli/investigator
    script_dir = Path(__file__).parent.resolve()
    return script_dir.parents[3]


def find_record_by_cve(cve_id: str) -> Optional[Dict[str, Any]]:
    path = get_project_root() / "patcheval" / "datasets" / "patcheval_dataset.json"
    with path.open("r") as f:
        records = json.load(f)
        return next(
            (record for record in records if record.get("cve_id") == cve_id), None
        )


def find_docker_metadata_by_cve(cve_id: str) -> Optional[Dict[str, Any]]:
    path = get_project_root() / "patcheval" / "exp_agent" / "geminicli" / "dataset.jsonl"
    with path.open("r") as f:
        for line in f:
            record = json.loads(line)
            if record.get("cve_id") == cve_id:
                return record
    return None


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    parser = argparse.ArgumentParser(description="Investigate a CVE.")
    parser.add_argument(
        "--cve", type=str, required=True, help="The CVE ID to investigate."
    )
    args = parser.parse_args()

    logger.info("Investigating CVE: %s", args.cve)

    record = find_record_by_cve(args.cve)
    if not record:
        logger.error("No record found with CVE ID: %s", args.cve)
        sys.exit(1)

    docker_metadata = find_docker_metadata_by_cve(args.cve)
    if not docker_metadata:
        logger.error("No Docker metadata found with CVE ID: %s", args.cve)
        sys.exit(1)

    image_name = docker_metadata.get("image_name")
    logger.info("Docker Image Name: %s", image_name)

    workspace_dest =  get_project_root() / "patcheval" / "exp_agent" / "geminicli" / "investigator" / args.cve

    try:
        extract_workspace_from_image(image_name, workspace_dest)
    except Exception as e:
        logger.error("Failed to extract workspace: %s", e, exc_info=True)
        sys.exit(1)
        
    # TODO: run Gemini CLI with a prompt to analyze the extracted workspace.


if __name__ == "__main__":
    main()