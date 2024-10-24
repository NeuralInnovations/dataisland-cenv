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

# Function to merge a PR and check if it is mergeable and has passed all checks
merge_pr() {
    local base_branch=$1

    echo "Checking PR for base branch: $base_branch..."

    # Check if the PR exists for the target branch
    pr_status=$(gh pr view "$PR_IDENTIFIER" --base "$base_branch" --json state -q '.state')

    # Check if PR is open
    if [ "$pr_status" != "OPEN" ]; then
        echo "Pull Request to $base_branch is not open. Current status: $pr_status"
        return 1
    fi

    # Check the mergeability of the PR
    mergeable=$(gh pr view "$PR_IDENTIFIER" --base "$base_branch" --json mergeable -q '.mergeable')

    if [ "$mergeable" != "MERGEABLE" ]; then
        echo "Pull Request to $base_branch is not mergeable (Merge conflicts or other issues)."
        return 1
    fi

    # Fetch the status of all checks and verify that all are successful
    all_checks_passed=$(gh pr checks "$PR_IDENTIFIER" --json state -q '.[] | select(.state != "SUCCESS")')

    # If the result is empty, it means all checks have passed
    if [ -n "$all_checks_passed" ]; then
        echo "Not all checks have passed for PR to $base_branch. Cannot merge."
        return 1
    fi

    # If everything is good, proceed to merge
    echo "All checks have passed. Merging PR $PR_IDENTIFIER to $base_branch..."
    gh pr merge "$PR_IDENTIFIER" --merge --base "$base_branch"
    return $?
}

# First, merge PR to master branch
if merge_pr "master"; then
    echo "PR $PR_IDENTIFIER successfully merged to master."
else
    echo "Failed to merge PR $PR_IDENTIFIER to master."
    exit 1
fi

# Then, merge PR to develop branch
if merge_pr "develop"; then
    echo "PR $PR_IDENTIFIER successfully merged to develop."
else
    echo "Failed to merge PR $PR_IDENTIFIER to develop."
    exit 1
fi

# If both merges are successful, delete the release branch
echo "Deleting the release branch release/${version}..."
git push origin --delete "release/${version}"
git branch -d "release/${version}"

echo "Release branch deleted."