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
import os
from pathlib import Path
from typing import Dict, Any
from .dataset import CVERecord


# Log
# - settings file
# - default prompt templates as toml
# - exclude google search tool in settings


class ScriptGenerator:
    
    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir        
    
    def generate_cve_fix_command(self, record: CVERecord) -> str:
        """Generate CVE fix command file"""
        # Gemini uses .toml files for command templates
        template_file = f"default.toml"
        template_path = self.templates_dir / template_file        
        content = template_path.read_text(encoding='utf-8')
        
        replacements = {
            "{{CVE_ID}}": record.cve_id,
            "{{WORK_DIR}}": record.work_dir,
            "{{PROBLEM_STATEMENT}}": record.problem_statement,
            "{{REPO_NAME}}": Path(record.work_dir).name
        }
        
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)
            
        return content
    
    @staticmethod 
    def generate_settings_file(model: str, enable_web_search: bool) -> str:

        settings: Dict[str, Any] = {
            "security": {
                "auth": {
                    "selectedType": "gemini-api-key"
                }
            },
        }

        if not enable_web_search:
            settings["excludeTools"] = ["google_web_search"]
        
        if model == '3pro':
            settings["general"] = {"previewFeatures": True}
        
        import json
        return json.dumps(settings, indent=2, ensure_ascii=False)
