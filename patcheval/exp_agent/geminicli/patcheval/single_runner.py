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
import logging
import time
import threading
import os
from pathlib import Path
from typing import Dict, Any, Optional

from .dataset import CVERecord
from .docker_utils import (
    pull_image_with_retry, 
    stop_container, run_work_container_no_mount
)
from .gemini_runner_enhanced import GeminiRunnerEnhanced
from .patch import write_patch_file, get_patch_stats, validate_patch


# Log
# - Removed `claude_timeout` related code
# - Removed `api_provider` arg
# - Removed `port` arg
# - Respect `success` result from execute_cve_repair
# - Removed `strategy` related code
# - Removed cost and tool limits
# - Removed `settings_file` arg
# - Removed readable logs
# - Removed `timeout` arg as it wasn't used


def run_single_cve(record: CVERecord,
                  outputs_root: Path,
                  semaphore: Optional[threading.Semaphore] = None,
                  keep_container: bool = False,
                  enable_detailed_logging: bool = True,
                  save_process_logs: bool = False,
                  allow_git_diff_fallback: bool = False,
                  model: str = "25pro",
                  gemini_extension_path: Optional[str] = None,
                  command_name: str = "default"
                  ) -> Dict[str, Any]:
    
    if semaphore is None:
        semaphore = threading.Semaphore(1)
    
    problem_id = record.problem_id
    start_time = time.time()
    logger = logging.getLogger(__name__)
    
    result = {
        "problem_id": problem_id,
        "cve_id": record.cve_id,
        "is_success": False,
        "agent_duration": 0.0,
        "total_duration": 0.0,
        "container_id": "",
        "patch_stats": {},
        "error_message": "",
        "stage": "initialization",
    }
    
    container_id = ""
    
    try:

        
        result["stage"] = "api_check"
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GEMINI_API_KEY environment variable")
        
        result["stage"] = "docker_setup"
        pull_image_with_retry(record.image_name, semaphore)
        
        result["stage"] = "work_container"
        container_id = run_work_container_no_mount(
            record.image_name, problem_id, semaphore)
        result["container_id"] = container_id
        
        
        gemini = GeminiRunnerEnhanced(
            container_id, 
            record.work_dir,
            enable_detailed_logging=enable_detailed_logging,
            allow_git_diff_fallback=allow_git_diff_fallback
        )
        
        if not gemini.setup_environment(record, api_key, model, gemini_extension_path):
            pass
        
        result["stage"] = "gemini_execution"
        
        gemini_start = time.time()
        success, output_log, patch_content = gemini.execute_cve_repair(command_name=command_name)
        
        result["is_success"] = success
        
        gemini_duration = time.time() - gemini_start        
        result["agent_duration"] = gemini_duration
        
        if not success:
            if not patch_content:
                patch_content = gemini._extract_patch()
        
        result["stage"] = "patch_processing"
        
        if not patch_content or not patch_content.strip():
            if allow_git_diff_fallback:
            
                try:
                    import subprocess
                    git_diff = subprocess.run(
                        f"docker exec {container_id} bash -c 'cd {record.work_dir} && git diff'",
                        shell=True, capture_output=True, text=True
                    ).stdout
                    if git_diff.strip():
                        patch_content = git_diff
                       
                        result["patch_source"] = "git_diff_fallback"  
                    else:
                        pass
                except Exception as e:
                    pass
            else:
                pass   
        if not validate_patch(patch_content, relaxed=True):
            pass
        
        patch_stats = get_patch_stats(patch_content)
        result["patch_stats"] = patch_stats
        
        logger.info(f" {patch_stats}")
        
        result["stage"] = "output_writing"
        
        outputs_root.mkdir(parents=True, exist_ok=True)
        (outputs_root / "patches").mkdir(exist_ok=True)
        (outputs_root / "agent_logs").mkdir(exist_ok=True)
        
        patch_file_path = outputs_root / "patches" / f"{problem_id}.patch"
        write_patch_file(patch_content, patch_file_path)
        
        log_file_path = outputs_root / "agent_logs" / f"{problem_id}.log"
        
        container_logs = gemini.get_container_logs()
        gemini.set_success_and_finalize_log(True, patch_content, container_logs)
        
        full_log = {
            "problem_id": problem_id,
            "cve_id": record.cve_id,
            "duration": gemini_duration,
            "patch_stats": patch_stats,
            "gemini_output": output_log,
            "container_logs": container_logs
        }
        
        if enable_detailed_logging:
            full_log["detailed_process"] = gemini.get_detailed_process_log()
        
        import json
        log_file_path.write_text(json.dumps(full_log, indent=2, ensure_ascii=False))
        
        if save_process_logs:
            process_log_path = outputs_root / "process_logs" / f"{problem_id}_process.json"
            process_log_path.parent.mkdir(exist_ok=True)
            gemini.save_process_log(str(process_log_path))
        
        if result["is_success"] and result.get("patch_source") == "git_diff_fallback":
            result["is_success"] = False  
            result["is_partial_success"] = True  
            result["warning"] = ""
           
        
        gemini.cleanup()
        
        result["stage"] = "completed"
        result["total_duration"] = time.time() - start_time
        

    except Exception as e:
        result["error_message"] = str(e)
        result["is_success"] = False
        result["total_duration"] = time.time() - start_time
        logger.error(f"{result['stage']}: {e}")
        
        try:
            if container_id and "gemini" in locals():
                container_logs = gemini.get_container_logs() if 'gemini' in locals() else ""
                gemini.set_success_and_finalize_log(False, "", container_logs)
                
                log_file_path = outputs_root / "agent_logs" / f"{problem_id}_failed.log"
                outputs_root.mkdir(parents=True, exist_ok=True)
                (outputs_root / "agent_logs").mkdir(exist_ok=True)
                
                failed_log = {
                    "problem_id": problem_id,
                    "cve_id": record.cve_id,
                    "stage": result["stage"],
                    "error": str(e),
                    "container_logs": container_logs
                }
                
                import json
                log_file_path.write_text(json.dumps(failed_log, indent=2, ensure_ascii=False))
        except Exception as log_e:
            logger.warning(f"{log_e}")
        
    finally:
        if container_id:
            try:
                if not keep_container:
                    stop_container(f"bench.{problem_id}.work")
                else:
                    pass
            except Exception as cleanup_e:
                pass
    
    return result

    