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
        
    @staticmethod
    def generate_claude_install_script(api_key: str, 
                                     api_provider: str = "anthropic") -> str:
        if api_provider == "anthropic":
            api_config = f"""
export ANTHROPIC_API_KEY='{api_key}'
export ANTHROPIC_MODEL='claude-3-5-sonnet-20241022'
export ANTHROPIC_SMALL_FAST_MODEL='claude-3-haiku-20240307'
"""
        elif api_provider == "bedrock":
            parts = api_key.split(':')
            if len(parts) == 3: 
                access_key, secret_key, region = parts
                api_config = f"""
export AWS_ACCESS_KEY_ID='{access_key}'
export AWS_SECRET_ACCESS_KEY='{secret_key}'
export AWS_REGION='{region}'
export ANTHROPIC_MODEL='anthropic.claude-3-5-sonnet-20241022-v2:0'
export ANTHROPIC_SMALL_FAST_MODEL='anthropic.claude-3-haiku-20240307-v1:0'
"""
            else: 
                api_config = f"""
export AWS_BEARER_TOKEN_BEDROCK='{api_key}'
export AWS_REGION='us-west-2'
export ANTHROPIC_MODEL='anthropic.claude-3-5-sonnet-20241022-v2:0'
export ANTHROPIC_SMALL_FAST_MODEL='anthropic.claude-3-haiku-20240307-v1:0'
"""
        elif api_provider == "vertex":
            parts = api_key.split(':')
            if len(parts) == 3:  
                token, project, region = parts
                api_config = f"""
export GOOGLE_APPLICATION_CREDENTIALS='{token}'
export GOOGLE_CLOUD_PROJECT='{project}'
export CLOUD_ML_REGION='{region}'
export ANTHROPIC_MODEL='claude-3-5-sonnet-20241022'
export ANTHROPIC_SMALL_FAST_MODEL='claude-3-haiku-20240307'
"""
            else:
                api_config = f"""
export VERTEX_AUTH_TOKEN='{api_key}'
export CLOUD_ML_REGION='us-central1'
export ANTHROPIC_MODEL='claude-3-5-sonnet-20241022'
export ANTHROPIC_SMALL_FAST_MODEL='claude-3-haiku-20240307'
"""
        else:
            api_config = f"""
export ANTHROPIC_API_KEY='{api_key}'
export ANTHROPIC_MODEL='claude-3-5-sonnet-20241022'
"""
            
        script_content = f"""#!/bin/bash

# Claude Code Environment Setup Script (Container Version)

set -e
echo "=== Starting Claude Code environment setup ==="

# Check and install Node.js
if ! command -v node &> /dev/null; then
    echo "Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# Create user and set permissions
if ! id "claude_user" &>/dev/null; then
    echo "Creating claude_user..."
    adduser --disabled-password --gecos '' claude_user
fi

chown -R claude_user:claude_user /workspace

# Install Claude Code
echo "Installing Claude Code..."
su - claude_user << 'USEREOF'
npm config set prefix ~/.npm-global
mkdir -p ~/.npm-global/bin

npm install -g @anthropic-ai/claude-code

# Set environment variables
cat > ~/.bashrc << 'BASHEOF'
export PATH="$HOME/.npm-global/bin:$PATH"
{api_config}
alias ll='ls -la'
BASHEOF

source ~/.bashrc

# Verify installation
if command -v claude &> /dev/null; then
    echo "✅ Claude Code installation successful: $(claude --version)"
else
    echo "⚠️ Claude Code may require using full path: ~/.npm-global/bin/claude"
fi
USEREOF

echo "🎉 Claude Code environment setup complete!"
"""
        return script_content
    
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
    def generate_expect_script(timeout: int = 1800) -> str:
       
        return f"""#!/usr/bin/expect
set timeout {timeout}


spawn claude /iterative-cve-fix --print --dangerously-skip-permissions --permission-mode bypassPermissions


expect {{
    "*Repair Completed*" {{ puts ""; exp_continue }}
    "*Task completed*" {{ puts "CVE repair task completed"; exp_continue }}
    "*Successfully generated patch*" {{ puts ""; exp_continue }}
    "*Smart repair completed*" {{ puts ""; exp_continue }}
    "*final-cve-fix.patch*" {{ puts ""; exp_continue }}
    eof {{ puts ""; }}
    timeout {{ puts ""; }}
}}


catch wait result
exit [lindex $result 3]
"""
    
    @staticmethod 
    def generate_settings_file(model: str) -> str:

        settings = {
            "security": {
                "auth": {
                    "selectedType": "gemini-api-key"
                }
            },
            "excludeTools": ["google_web_search"]
        }
        
        if model == '3pro':
            settings["general"] = {"previewFeatures": True}
        
        import json
        return json.dumps(settings, indent=2, ensure_ascii=False)
    
    @staticmethod
    def generate_run_script(work_dir: str, command_name: str = "iterative-cve-fix") -> str:

        return f"""#!/bin/bash


set -e


cd {work_dir}

if ! command -v claude &> /dev/null; then
    if [ -x ~/.npm-global/bin/claude ]; then
        export PATH="$HOME/.npm-global/bin:$PATH"
    else
        echo "❌ Claude Code not available"
        exit 1
    fi
fi

echo "✅ Claude Code version: $(claude --version)"

claude /{command_name} \\
    --print \\
    --dangerously-skip-permissions \\
    --permission-mode bypassPermissions \\
    --output-format json

"""