#!/bin/bash

# Check if the argument is provided and valid
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <minor|patch>"
    exit 1
fi

if [ "$1" != "minor" ] && [ "$1" != "patch" ]; then
    echo "Invalid argument. Use 'minor' or 'patch'."
    exit 1
fi

# Extract current version from project.properties
version=$(grep '^version[ ]*=[ ]*' project.properties | cut -d'=' -f2 | tr -d '[:space:]')

# Split version into major, minor, and patch
IFS='.' read -r major minor patch <<< "$version"

# Determine whether to increment minor or patch version
if [ "$1" == "patch" ]; then
    # Increment patch version
    new_patch=$((patch + 1))
    new_minor=$minor  # Minor stays the same

elif [ "$1" == "minor" ]; then
    # Increment minor version and reset patch
    new_minor=$((minor + 1))
    new_patch=0  # Reset patch to 0
fi

# Form the new version string
new_version="$major.$new_minor.$new_patch"

# Update the version in project.properties using sed
os_type=$(uname)
if [ "$os_type" == "Darwin" ]; then
    sed -i '' "s/version[ ]*=.*/version=$new_version/" project.properties
else
    sed -i "s/version[ ]*=.*/version=$new_version/" project.properties
fi

# Optionally, you may want to update requirements or dependencies
# This can be customized as needed for the Python project

# Create a new branch for the release
git checkout -b "release/$new_version"

# Optionally, commit the changes
git add project.properties
git commit -m "release/$new_version"

echo "Branch release/$new_version created, version updated in project.properties."

# Check if GitHub CLI (gh) is installed
if command -v gh > /dev/null; then
    echo "GitHub CLI (gh) is installed."

    # Push the changes to the remote repository
    git push origin "release/$new_version"

    # Create a pull request for develop
    gh pr create \
        --base develop \
        --head "release/$new_version" \
        --title "release/$new_version" \
        --body "Release $new_version"

    # Create a pull request for master
    gh pr create \
        --base master \
        --head "release/$new_version" \
        --title "release/$new_version" \
        --body "Release $new_version"

else
    echo "GitHub CLI (gh) is not installed. Please install it to proceed."
fi