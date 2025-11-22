#!/bin/bash
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

#!/bin/bash

# Log
# - Fixed possible bug with API key placeholder

set -e  

echo "=== Gemini Environment Setup Script ==="

if id "gemini_user" &>/dev/null; then
    echo "🗑️  Removing existing gemini_user..."
    userdel -r gemini_user 2>/dev/null || true
fi


echo "👤 Creating gemini_user..."
adduser --disabled-password --gecos '' gemini_user >/dev/null


if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null 2>&1
    apt-get install -y nodejs >/dev/null 2>&1
    echo "✅ Node.js $(node --version) installed"
else
    echo "✅ Node.js $(node --version) already installed"
fi


echo "🔧 Setting workspace permissions..."
chown -R gemini_user:gemini_user /workspace 2>/dev/null || true


echo "⚙️  Installing Gemini Code..."
su - gemini_user << 'USEREOF'

npm config set prefix ~/.npm-global >/dev/null 2>&1


mkdir -p ~/.npm-global/bin

npm install -g @google/gemini-cli >/dev/null 2>&1


NPM_PREFIX=$(npm config get prefix)


cat > ~/.bashrc << 'BASHEOF'

export PATH="$HOME/.npm-global/bin:$PATH"
export PATH=$PATH:/usr/local/go/bin

# Gemini API configuration
export GEMINI_API_KEY='{{GEMINI_API_KEY}}'

# Useful aliases
alias ll='ls -la'
alias la='ls -la'
BASHEOF


source ~/.bashrc


if [ -L ~/.npm-global/bin/gemini ]; then
    target=$(readlink ~/.npm-global/bin/gemini)
    if [ -x "$target" ]; then
        echo "✅ Gemini installation verified"
    else
        chmod +x "$target"
        echo "✅ Gemini permissions fixed"
    fi
else
    echo "⚠️  Gemini symlink not found, checking alternatives..."
fi


if ~/.npm-global/bin/gemini --version >/dev/null 2>&1; then
    echo "✅ Gemini ready to use"
elif command -v gemini &> /dev/null; then
    echo "✅ Gemini found in PATH"
else
    echo "❌ Gemini installation may have issues"
fi
USEREOF

echo "📁 Setting up Gemini commands directory..."
su - gemini_user << 'CMDEOF'
mkdir -p /workspace/markdown-it/.gemini/commands 2>/dev/null || true
CMDEOF

echo "🔍 Final verification..."
su - gemini_user << 'VERIFYEOF'

source ~/.bashrc


if command -v gemini &> /dev/null; then
    echo "✅ Gemini ready: $(gemini --version 2>/dev/null || echo 'version check failed')"
elif ~/.npm-global/bin/gemini --version >/dev/null 2>&1; then
    echo "✅ Gemini available via direct path"
else
    echo "❌ Gemini not accessible"
    echo "💡 Use full path: ~/.npm-global/bin/gemini"
fi

echo "🔧 Environment: Node $(node --version), NPM $(npm --version)"
echo "🔑 API configured: ${GEMINI_API_KEY:0:10}***"
VERIFYEOF

echo ""
echo "🎉 Setup Complete!"
echo ""
echo "Usage:"
echo "  su - gemini_user"
echo "  cd /workspace/your-project"
echo "  gemini /your-command"
echo ""
echo "💡 If 'gemini' not found, use: ~/.npm-global/bin/gemini"