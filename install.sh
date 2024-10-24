#!/bin/bash

# Set the repository owner and name
OWNER="NeuralInnovations"
REPOSITORY="dataisland-cenv"
CPU_ARCH=$(arch)

# Determine the current platform
platform=""
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    platform="linux-amd64"
    install_dir="/usr/local/bin"
    if [[ "$CPU_ARCH" == "aarch64" ]] || [[ "$CPU_ARCH" == "arm64" ]]; then
        platform="linux-arm64"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    platform="macos"
    install_dir="/usr/local/bin"
elif [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "cygwin"* || "$OSTYPE" == "win32" ]]; then
    platform="windows"
    install_dir="$HOME/bin"
else
    echo "Unsupported platform: $OSTYPE"
    exit 1
fi

# Get the latest release information using GitHub API
release_info=$(curl -s "https://api.github.com/repos/$OWNER/$REPOSITORY/releases/latest")

# Determine the filename for the current platform
filename="cenv-$platform"

# Extract the download URL for the specific platform binary
download_url=$(echo "$release_info" | grep "browser_download_url" | grep "$filename" | cut -d '"' -f 4)

# Check if the download URL was found
if [[ -z "$download_url" ]]; then
    echo "Download URL for platform $platform not found."
    exit 1
fi

# Download the binary
echo "Downloading $filename..."
curl -L -o cenv "$download_url"

# Make the binary executable (skipped on Windows)
if [[ "$platform" != "windows" ]]; then
    chmod +x cenv
fi

# Create the install directory if it doesn't exist (for Windows)
if [[ "$platform" == "windows" && ! -d "$install_dir" ]]; then
    mkdir -p "$install_dir"
fi

# Move the binary to the install directory
echo "Installing to $install_dir..."
if [[ "$platform" == "windows" ]]; then
    mv cenv "$install_dir/cenv.exe"
else
    sudo mv cenv "$install_dir/cenv"
fi

# Add the directory to PATH (for Windows) if it's not already
if [[ "$platform" == "windows" ]]; then
    if [[ ":$PATH:" != *":$install_dir:"* ]]; then
        echo "Adding $install_dir to PATH in .bashrc..."
        echo "export PATH=\$PATH:$install_dir" >> ~/.bashrc
        # Reload .bashrc to update PATH in the current session
        source ~/.bashrc
    fi
fi

echo "Installation complete. You can now use 'cenv'."