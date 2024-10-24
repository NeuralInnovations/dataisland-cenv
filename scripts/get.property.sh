#!/usr/bin/env bash

# ---------------------------------------------------------
# include libraries
# ---------------------------------------------------------
source ./scripts/property.utils.sh

# ---------------------------------------------------------
# read arguments
# ---------------------------------------------------------
while [[ "$#" -gt 0 ]]; do
    case $1 in
    --property)
        PROPERTY_NAME="$2"
        shift
        ;;
    --file)
        PROPERTY_FILE="$2"
        shift
        ;;
    --help)
        echo "Usage: $0 --property <property> --file <file>"
        exit 0
        ;;
    *)
        echo "Unknown parameter: $1"
        exit 1
        ;;
    esac
    shift
done

# ---------------------------------------------------------
# check requirements
# ---------------------------------------------------------
[[ -z "$PROPERTY_NAME" ]] && echo "Error: --property not set." && exit 1
[[ -z "$PROPERTY_FILE" ]] && echo "Error: --file not set." && exit 1

# ---------------------------------------------------------
# read property
# ---------------------------------------------------------
echo $(read_property $PROPERTY_NAME $PROPERTY_FILE)