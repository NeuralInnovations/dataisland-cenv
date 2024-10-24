#!/usr/bin/env bash

# ---------------------------------------------------------
# read property from the file
# $1 - property name
# $2 - property file
# ---------------------------------------------------------
function read_property {
    property_name=$1
    property_file=$2
    grep "^$property_name" "$property_file" | cut -d'=' -f2-
}

# ---------------------------------------------------------
# write property to the file
# $1 - property name
# $2 - property value
# $3 - property file
# ---------------------------------------------------------
write_property() {
    property_name=$1
    property_value=$2
    property_file=$3

    awk -v pat="^$property_name=" -v value="$property_name=$property_value" '{ if ($0 ~ pat) print value; else print $0; }' $property_file >$property_file.tmp
    mv $property_file.tmp $property_file
}
