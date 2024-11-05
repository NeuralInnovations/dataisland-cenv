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

# Function to merge a PR for a specific branch
pr_status() {
    local base_branch=$1

    echo "Checking PR for base branch: $base_branch..."

    # Fetch the PR number for the base branch using the head reference "release/${version}" and base branch
    pr_number=$(gh pr list --head "$PR_IDENTIFIER" --base "$base_branch" --json number -q '.[0].number')

    if [ -z "$pr_number" ]; then
        echo "No open PR found for $PR_IDENTIFIER to $base_branch."
        return 1
    fi

    echo "PR number for $base_branch: $pr_number"

    # Check if PR is open
    pr_status=$(gh pr view "$pr_number" --json state -q '.state')

    if [ "$pr_status" != "OPEN" ]; then
        echo "Pull Request to $base_branch is not open. Current status: $pr_status"
        return 1
    fi

    # Check the mergeability of the PR
    mergeable=$(gh pr view "$pr_number" --json mergeable -q '.mergeable')

    if [ "$mergeable" != "MERGEABLE" ]; then
        echo "Pull Request to $base_branch is not mergeable (Merge conflicts or other issues)."
        return 1
    fi

    # Fetch the status of all checks and verify that all are successful
    all_checks_passed=$(gh pr checks "$pr_number" --json state -q '.[] | select(.state != "SUCCESS")')

    # If the result is empty, it means all checks have passed
    if [ -n "$all_checks_passed" ]; then
        echo "Not all checks have passed for PR to $base_branch. Cannot merge."
        return 1
    fi

    # If everything is good, proceed to merge
    echo "All checks have passed. There may be a merger of PR $pr_number to $base_branch..."
    return $?
}

# First, merge PR to master branch
if pr_status "master"; then
    echo "PR $PR_IDENTIFIER can be merged to master."
else
    echo "Can't be merge to PR $PR_IDENTIFIER to master."
    exit 1
fi

# Then, merge PR to develop branch
if pr_status "develop"; then
    echo "PR $PR_IDENTIFIER can be merged to develop."
else
    echo "Can't be merge to PR $PR_IDENTIFIER to develop."
    exit 1
fi

echo "All checks have passed. Ready to merge PR $PR_IDENTIFIER to master and develop branches."
