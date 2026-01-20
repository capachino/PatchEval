import argparse
import json
import logging
import stat
import sys
import subprocess
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


def modify_run_script(script_path: Path, workspace_dir: Path, cve_id: str) -> None:
    if script_path.exists():
        logger.info("Modifying %s for CVE: %s", script_path.name, cve_id)
        with script_path.open("r") as f:
            content = f.read()

        content = content.replace("/workspace/", workspace_dir.as_posix() + "/")

        with script_path.open("w") as f:
            f.write(content)
        logger.info("%s modified for CVE: %s", script_path.name, cve_id)

        current_permissions = script_path.stat().st_mode
        script_path.chmod(current_permissions | stat.S_IEXEC)
        logger.info("Made %s executable for CVE: %s", script_path.name, cve_id)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    parser = argparse.ArgumentParser(description="Prepare an extracted workspace for experimentation.")
    parser.add_argument(
        "--cve", type=str, required=True, help="The CVE ID to prepare the workspace for."
    )
    parser.add_argument(
        "--patch_batch_id", type=str, help="The ID of the batch run to retrieve the fix patch from."
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

    problem_instruction = "Please fix the vulnerabilities in the code repository based on the following information:"    
    problem_statement = problem_statement.replace(problem_instruction, "").strip()
    formatted_arg = problem_statement.replace('\n', '\\n').replace('\\', '\\\\').replace('"', '\\"')

    problem_statement_path = workspace_dir / "problem_statement.md"

    with problem_statement_path.open("w") as f:
        f.write(formatted_arg)
    logger.info("Wrote problem_statement.md for CVE: %s", args.cve)

    if args.patch_batch_id:
        geminicli_path = get_project_root() / "patcheval" / "exp_agent" / "geminicli"
        source_patch_path = (
            geminicli_path
            / "evaluation_output"
            / "results"
            / args.patch_batch_id
            / "logs"
            / args.cve
            / "fix.patch"
        )
        if source_patch_path.exists():
            content = source_patch_path.read_text()
            dest_patch_path = workspace_dir / "fix.patch"
            dest_patch_path.write_text(content)
            logger.info("Overwrote fix.patch with content from batch %s", args.patch_batch_id)
        else:
            logger.error("Patch file not found for batch %s at %s", args.patch_batch_id, source_patch_path)
            sys.exit(1)
    
    modify_run_script(workspace_dir / "vul-run.sh", workspace_dir, args.cve)
    modify_run_script(workspace_dir / "fix-run.sh", workspace_dir, args.cve)
    modify_run_script(workspace_dir / "prepare.sh", workspace_dir, args.cve)

    prepare_script = workspace_dir / "prepare.sh"
    if prepare_script.exists():
        logger.info("Running prepare.sh for CVE: %s", args.cve)
        try:
            subprocess.run([str(prepare_script)], cwd=str(workspace_dir), check=True)
        except subprocess.CalledProcessError as e:
            logger.error("Failed to run prepare.sh: %s", e)
            sys.exit(1)

    logger.info("Preparation complete for CVE: %s, workspace prepared at: %s", args.cve, workspace_dir)
    logger.info("`cd %s` to access the repo directory.", repo_dir)


if __name__ == "__main__":
    main()
