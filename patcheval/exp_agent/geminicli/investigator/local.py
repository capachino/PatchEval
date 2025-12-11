import argparse
import json
import logging
import stat
import sys
from pathlib import Path
from typing import Any, Dict, Optional

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
    parser = argparse.ArgumentParser(description="Prepare an extracted workspace for experimentation.")
    parser.add_argument(
        "--cve", type=str, required=True, help="The CVE ID to prepare the workspace for."
    )
    args = parser.parse_args()

    docker_metadata = find_docker_metadata_by_cve(args.cve)
    if not docker_metadata:
        logger.error("No Docker metadata found with CVE ID: %s", args.cve)
        sys.exit(1)

    work_dir = docker_metadata.get("work_dir")
    if not work_dir:
        logger.error("No work directory found with CVE ID: %s", args.cve)
        sys.exit(1)
    repo_dir = work_dir.replace("/workspace", str(args.cve))
        
    problem_statement = docker_metadata.get("problem_statement")
    if not problem_statement:
        logger.error("No problem statement found with CVE ID: %s", args.cve)
        sys.exit(1)

    workspace_dir =  get_project_root() / "patcheval" / "exp_agent" / "geminicli" / "investigator" / args.cve    
    if not workspace_dir.exists():
        logger.error("Workspace destination does not exist for CVE ID: %s at %s", args.cve, workspace_dir)
        sys.exit(1)

    problem_statement_path = workspace_dir / "problem_statement.md"
    with problem_statement_path.open("w") as f:
        f.write(problem_statement)
    logger.info("Wrote problem_statement.md for CVE: %s", args.cve)
        
    vul_run_path = workspace_dir / "vul-run.sh"
    if vul_run_path.exists():
        logger.info("Modifying vul-run.sh for CVE: %s", args.cve)
        with vul_run_path.open("r") as f:
            content = f.read()
        
        content = content.replace("cd /workspace/", "cd ")
        content = content.replace("/workspace/test.patch", "../test.patch")

        with vul_run_path.open("w") as f:
            f.write(content)
        logger.info("vul-run.sh modified for CVE: %s", args.cve)
        
        current_permissions = vul_run_path.stat().st_mode
        vul_run_path.chmod(current_permissions | stat.S_IEXEC)
        logger.info("Made vul-run.sh executable for CVE: %s", args.cve)    

    logger.info("Preparation complete for CVE: %s, workspace prepared at: %s", args.cve, workspace_dir)
    logger.info("`cd %s` to access the repo directory.", repo_dir)


if __name__ == "__main__":
    main()
