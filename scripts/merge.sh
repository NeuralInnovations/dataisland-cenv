#!/bin/bash

# Extract version from project.properties
version=$(grep '^version[ ]*=[ ]*' project.properties | cut -d'=' -f2 | tr -d '[:space:]')

# Check if version is extracted
if [ -z "$version" ]; then
    echo "Failed to extract version from project.properties"
    exit 1
fi

# Set the PR_IDENTIFIER as "release/${version}"
PR_IDENTIFIER="release/${version}"

echo "Pull request identifier: $PR_IDENTIFIER"

# Fetch PR details using GitHub CLI
pr_status=$(gh pr view "$PR_IDENTIFIER" --json state,mergeable -q '.state')

# Check if PR is open
if [ "$pr_status" != "OPEN" ]; then
    echo "Pull Request is not open. Current status: $pr_status"
    exit 1
fi

# Check the mergeability of the PR
mergeable=$(gh pr view "$PR_IDENTIFIER" --json mergeable -q '.mergeable')

if [ "$mergeable" != "MERGEABLE" ]; then
    echo "Pull Request is not mergeable (Merge conflicts or other issues)."
    exit 1
fi

# Fetch the status of all checks and verify that all are successful
all_checks_passed=$(gh pr checks "$PR_IDENTIFIER" --json state -q '.[] | select(.state != "SUCCESS")')

# If the result is empty, it means all checks have passed
if [ -n "$all_checks_passed" ]; then
    echo "Not all checks have passed. Cannot merge PR."
    exit 1
fi

# If everything is good, proceed to merge
echo "All checks have passed. Merging PR $PR_IDENTIFIER..."

if gh pr merge "$PR_IDENTIFIER" --merge --auto; then
    echo "PR $PR_IDENTIFIER successfully merged."

    # Delete the release branch
    git push origin --delete "release/${version}"
    git branch -d "release/${version}"

    git checkout develop
else
    echo "Failed to merge PR $PR_IDENTIFIER."
    exit 1
fi