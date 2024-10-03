#!/bin/bash

REPO="NeuralInnovations/dataisland-cenv"
BINARY_NAME="cenv_linux"
INSTALL_DIR="~/"

# Fetch the latest release download URL for the binary
get_latest_release_asset_id() {
    response=$(curl -s \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    -L https://api.github.com/repos/$REPO/releases/latest)

    if  [[ $(echo "$response" | grep -i "Not Found") ]]; then
        echo "Error: Unable to access the repository or no releases found. Please check the repository or token."
        exit 1
    fi
    # echo "$response"

    # Extract the asset download URL
    ASSET_BLOCK=$(echo "$reponse" | grep -A 10 '"name": "$BINARY_NAME"')
    ASSET_ID=$(echo "$ASSET_BLOCK" | grep '"id":' | awk '{print $2}' | sed 's/,//')
    echo "Asset id: $ASSET_ID"

    if [[ -z "$ASSET_ID"  ]]; then
        echo "Error: Unable to find a release asset ID."
        exit 1
    fi

    echo $ASSET_ID
}

# Function to down load the release asset using the asset ID
download_binary() {
    ASSET_ID=$(get_latest_release_asset_id)

    echo "Downloading $BINARY_NAME (Asset ID: $ASSET_ID) from the private repo..."

    # GitHub API URL to download the asset
    ASSET_URL="https://api.github.com/repos/$REPO/releases/assets/$ASSET_ID"

    # Download the asset using the GitHub API
    curl -s -L \
        -H "Accept: application/octet-stream" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        $ASSET_URL -o $BINARY_NAME

    if [[ $? -ne 0 ]]; then
        echo "Error: Failed to download the binary."
        exit 1
    fi
}

# Make the binary executable and move it to the install directory
install_binary() {
    echo "Make the binary executable..."
    chmod +x $BINARY_NAME

    echo "Installing the binary to $INSTALL_DIR..."
    sudo mv $BINARY_NAME "$INSTALL_DIR/$BINARY_NAME"
    
    if [[ $? -ne 0 ]]; then
        echo "Error: Installation failed."
        exit 1
    fi
}

# Update system PATH if not already present
update_path() {
    if [[ ":$PATH" != *":$INSTALL_DIR:"* ]]; then
        echo "Adding $INSTALL_DIR to your PATH..."
        echo "export PATH=\$PATH:$INSTALL_DIR" >> ~/.bashrc
        source ~/.bashrc
    else
        echo "PATH already includes $INSTALL_DIR"
    fi
}

# Main script flow execution
download_binary
install_binary
update_path

echo "Installation completed!"