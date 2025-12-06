# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import utils
import os
from pathlib import Path
import argparse


# Log
# - Skip over records without generated patches
# - Change output dir arg to accept the output root
# - Skip over records that do not have successful run results


def _load_run_results(run_index_path: Path) -> dict[str, bool]:
    statuses = {}
    
    with open(run_index_path, 'r', encoding='utf-8') as f:
        text = f.read()
        for line in text.replace("\\n", "\n").split("\n"):
            if not line:
                continue
            record = json.loads(line.strip())
            problem_id = record.get("problem_id", "")
            if not problem_id:
                continue
            
            # Do not overwrite a True status with a False one
            if statuses.get(problem_id) is not True:
                statuses[problem_id] = record.get("is_success", False)

    return statuses


def main():
    test_data = json.load(open(args.test_data_path))
    cve2language = {it['cve_id']: it["programing_language"] for it in test_data}
    dataset_path = args.dataset_path
    dataset = utils.load_jsonl_file(dataset_path)
    output_dir = args.output_dir
    patches_dir = os.path.join(output_dir, "patches")    
    process_data_path = args.process_data_path
    failed_cve = []
    missing_cve = []
    nopatch_cve = []
    process_data = []
    
    run_index_path = os.path.join(output_dir, "run_index.jsonl")
    run_results = _load_run_results(run_index_path)
    
    for data in dataset:
        cve_id, image_name = data['cve_id'], data['image_name']
        if cve_id not in run_results:
            missing_cve.append(cve_id)
            continue
        
        if not run_results[cve_id]:
            failed_cve.append(cve_id)
            continue

        patch_path = f"{patches_dir}/{cve_id}.patch"        
        if not os.path.exists(patch_path) or os.path.isdir(patch_path):
            nopatch_cve.append(cve_id)
            continue

        stats = {}
        agent_logs_dir = os.path.join(output_dir, "agent_logs")        
        agent_log_path = f"{agent_logs_dir}/{cve_id}.log"
        with open(agent_log_path) as f:
            agent_log = json.load(f)
            detailed_process = agent_log.get("detailed_process", None)
            if detailed_process:
                stats = detailed_process.get("stats", {})

        with open(patch_path) as f:
            fix_patch = f.read()
    # if cve_id.upper() not in cve2language:
        # continue
            process_data.append(
                {
                    "cve": cve_id.upper(),
                    "language": cve2language[cve_id.upper()],
                    "input_tokens": stats.get("total_input_tokens", 0),
                    "output_tokens": stats.get("total_output_tokens", 0),
                    'fix_patch': fix_patch
                }
            )
    Path(process_data_path).parent.mkdir(parents=True, exist_ok=True)
    utils.write_jsonl(process_data, process_data_path)
    print(f"Wrote {len(process_data)} records to {process_data_path}\n")
    print(f"Missing CVEs: {missing_cve}\n")
    print(f"Skipped CVEs (failed run): {failed_cve}\n")
    print(f"Skipped CVEs (no patch): {nopatch_cve}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()


    parser.add_argument(
        "--process_data_path",
        type=str,
        required=True
    )
    parser.add_argument(
        "--dataset_path",
        type=str,
        required=False,
        default="dataset.jsonl"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        required=True
    )
    parser.add_argument(
        "--test_data_path",
        type=str,
        required=True
    )
    args = parser.parse_args()
    main()