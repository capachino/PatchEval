import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


def get_project_root() -> Path:
    """Determines the absolute path to the project root."""
    # Assumes this script is in patcheval/exp_agent/geminicli/investigator
    script_dir = Path(__file__).parent.resolve()
    return script_dir.parents[3]


def find_record_by_cve(cve_id: str) -> Optional[Dict[str, Any]]:
    path = get_project_root() / "patcheval" / "datasets" / "patcheval_dataset.json"
    records = json.loads(path.read_text()) # Consistent with rest of script
    return next((r for r in records if r.get("cve_id") == cve_id), None)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    parser = argparse.ArgumentParser(description="Investigate a CVE.")
    parser.add_argument(
        "--cve", type=str, required=True, help="The CVE ID to investigate."
    )
    parser.add_argument(
        "--batch_id", type=str, required=True, help="The ID of the batch run e.g. `25pro`."
    )    
    args = parser.parse_args()

    logger.info("Investigating CVE: %s", args.cve)

    record = find_record_by_cve(args.cve)
    if not record:
        logger.error("No record found with CVE ID: %s", args.cve)
        sys.exit(1)
        
    geminicli_eval_path = (
        get_project_root()
        / "patcheval"
        / "exp_agent"
        / "geminicli"
    )    
    eval_output_path = geminicli_eval_path / "evaluation_output"
    script_path = geminicli_eval_path / "investigator"

    tool_patch_path = (
        eval_output_path
        / "results"
        / args.batch_id
        / "logs"
        / args.cve
        / "fix.patch"
    )
    tool_generated_patch = tool_patch_path.read_text()

    poc_test_error_path = (
        eval_output_path
        / "results"
        / args.batch_id
        / "logs"
        / args.cve
        / "erro_output.log"
    )
    poc_test_error_log = poc_test_error_path.read_text()

    template_path = (
        script_path
        / "explain_vulnerability.md"
    )
    template = template_path.read_text()
        
    poc_test_path = (
        script_path
        / args.cve
        / "test.patch"
    )
    poc_test_patch = poc_test_path.read_text()
        
    prompt = template.replace("{{CVE_ID}}", args.cve)
    prompt = prompt.replace("{{CVE_DESCRIPTION}}", record.get("cve_description", ""))
    vul_func_str = ""
    if record.get("vul_func"):
        vul_func_str = json.dumps(record.get("vul_func"), indent=4)
    prompt = prompt.replace("{{VULN_FUNC}}", vul_func_str)
    prompt = prompt.replace("{{VULN_PATCH}}", record.get("vul_patch", ""))
    prompt = prompt.replace("{{TOOL_GENERATED_PATCH}}", tool_generated_patch)
    prompt = prompt.replace("{{POC_TEST_PATCH}}", poc_test_patch)
    prompt = prompt.replace("{{POC_TEST_ERROR_LOG}}", poc_test_error_log)

    print(prompt)


if __name__ == "__main__":
    main()
