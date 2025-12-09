import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from docker_utils import extract_workspace_from_image


logger = logging.getLogger(__name__)


def get_project_root() -> Path:
    """Determines the absolute path to the project root."""
    # Assumes this script is in patcheval/exp_agent/geminicli/investigator
    script_dir = Path(__file__).parent.resolve()
    return script_dir.parents[3]

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
    parser = argparse.ArgumentParser(description="Extract a docker image for a CVE.")
    parser.add_argument(
        "--cve", type=str, required=True, help="The CVE ID to extract the image for."
    )
    args = parser.parse_args()

    logger.info("Extracting image for CVE: %s", args.cve)

    docker_metadata = find_docker_metadata_by_cve(args.cve)
    if not docker_metadata:
        logger.error("No Docker metadata found with CVE ID: %s", args.cve)
        sys.exit(1)

    image_name = docker_metadata.get("image_name")
    if not image_name:
        logger.error("No Docker image name found with CVE ID: %s", args.cve)
        sys.exit(1)

    workspace_dest =  get_project_root() / "patcheval" / "exp_agent" / "geminicli" / "investigator" / args.cve
    try:
        extract_workspace_from_image(image_name, workspace_dest)
    except Exception as e:
        logger.exception("Failed to extract workspace for %s", args.cve)
        sys.exit(1)

    logger.info("Extraction complete for CVE: %s, extracted to: %s", args.cve, workspace_dest)


if __name__ == "__main__":
    main()
