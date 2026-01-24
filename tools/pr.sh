#!/bin/bash
set -e

label=${1:-enhancement}  # enhancement or bug
msg=${2:-"Update"}

branch="pr-$(date +%s)"
git checkout -b "$branch"
git commit -am "$msg"
git push -u origin "$branch"
gh pr create --fill --label "$label"
gh pr merge --squash --auto
git checkout main

echo "PR created with label '$label' and auto-merge enabled"
