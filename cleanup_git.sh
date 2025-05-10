#!/bin/bash

# Cleanup Script to remove sensitive and large files from git tracking
# This script should be run after .gitignore is set up properly

echo "Removing environment files from git tracking..."
git rm --cached .env
git rm --cached server/.env
git rm --cached server/application/.env

echo "Removing large binary files..."
git rm --cached connector/lib/python3.8/site-packages/numpy/.dylibs/libopenblas64_.0.dylib
git rm -r --cached connector/lib/python3.8/site-packages/

echo "Removing cache files..."
git rm -r --cached __pycache__/
git rm -r --cached server/agent/cmd/__pycache__/
git rm -r --cached server/agent/tools/__pycache__/
git rm -r --cached server/agent/llm/__pycache__/

echo "Removing metadata and indexes..."
git rm --cached server/agent/meta/index.faiss
git rm --cached server/agent/meta/metadata.json

echo "Making the script executable..."
chmod +x cleanup_git.sh

echo "Done! Now commit the changes with: git commit -m 'Remove sensitive and large files from git tracking'"
echo "Don't forget to push your changes after committing." 