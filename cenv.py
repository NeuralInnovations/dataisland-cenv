import argparse
import base64
import configparser
import json
import os
import pkgutil
import sys
import platform
import requests
import subprocess
import re

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()


# Function to read properties file
def load_properties():
    # Check if running as a PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundled mode
        base_path = sys._MEIPASS
        properties_path = os.path.join(base_path, 'project.properties')
        with open(properties_path, 'r') as f:
            return f.read()
    else:
        # Try loading using pkgutil if the script is part of a package
        try:
            data = pkgutil.get_data(__name__, 'project.properties')
            if data:
                return data.decode('utf-8')
        except ValueError:
            # If __main__ or not a package, manually load the file from the script directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            properties_path = os.path.join(script_dir, 'project.properties')
            with open(properties_path, 'r') as f:
                return f.read()


# Initialize the parser
projectProperties = configparser.ConfigParser()

# Read the properties file
projectProperties.read_string(load_properties())

# Access the properties
project_name = projectProperties['DEFAULT']['name']
project_version = projectProperties['DEFAULT']['version']
project_owner = projectProperties['DEFAULT']['owner']
project_repository = projectProperties['DEFAULT']['repository']

update_install_dir = "/usr/local/bin" if platform.system() != "Windows" else os.path.expanduser("~\\bin")
update_filename = f"cenv-{platform.system().lower()}-{platform.machine()}"


def update_add_to_path_if_needed(directory):
    """Adds the specified directory to PATH if not already included."""
    path = os.environ["PATH"]
    if directory not in path:
        print(f"Adding {directory} to PATH...")
        subprocess.call(f'setx PATH "%PATH%;{directory}"', shell=True)
        print("You may need to restart your terminal for changes to take effect.")


def update_ensure_directory_exists(directory):
    """Creates the directory if it does not exist."""
    if not os.path.exists(directory):
        print(f"Creating directory: {directory}")
        os.makedirs(directory)


def update_get_latest_release_url():
    """Fetches the latest release URL from GitHub API for the platform."""
    api_url = f"https://api.github.com/repos/{project_owner}/{project_repository}/releases/latest"
    response = requests.get(api_url)
    response.raise_for_status()  # Ensure we got a valid response
    release_info = response.json()
    for asset in release_info["assets"]:
        if update_filename in asset["name"]:
            return asset["browser_download_url"]
    return None


def update_download_binary(url, dest_path):
    """Downloads the binary and saves it to the destination path."""
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(dest_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)


def update_cenv():
    """Updates the cenv tool by downloading and replacing the binary."""

    update_ensure_directory_exists(update_install_dir)

    download_url = update_get_latest_release_url()
    if not download_url:
        print(f"No download URL found for platform {update_filename}. Update aborted.")
        return

    print(f"Downloading latest version of cenv from {download_url}...")
    dest_path = os.path.join(update_install_dir, "cenv" + (".exe" if platform.system() == "Windows" else ""))
    temp_path = dest_path + ".new"

    if platform.system() == "Windows":
        update_add_to_path_if_needed(update_install_dir)

    update_download_binary(download_url, temp_path)

    # Make the binary executable (if not Windows)
    if platform.system() != "Windows":
        os.chmod(temp_path, 0o755)

    # Replace old binary with the new one
    os.replace(temp_path, dest_path)
    print("Update complete. You can now use the latest version of 'cenv'.")


class Configs:
    GOOGLE_CREDENTIAL_BASE64: str
    GOOGLE_SHEET_ID: str
    GOOGLE_SHEET_NAME: str
    CONFIG_FILE: str
    SCOPES: list[str]

    def __init__(self):
        self.GOOGLE_CREDENTIAL_BASE64 = os.getenv("CENV_GOOGLE_CREDENTIAL_BASE64")
        self.GOOGLE_SHEET_ID = os.getenv("CENV_GOOGLE_SHEET_ID")
        self.GOOGLE_SHEET_NAME = os.getenv("CENV_GOOGLE_SHEET_NAME", "Env")
        self.CONFIG_FILE = os.getenv("CENV_STORE_CONFIG_FILE", "./cenv_config.json")
        self.SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


configs = Configs()


def save_to_file(data):
    """Saves the Google Sheets data to a local file."""
    delete_file()
    with open(configs.CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)


def delete_file() -> bool:
    """Deletes the local file containing the Google Sheets data."""
    if os.path.exists(configs.CONFIG_FILE):
        os.remove(configs.CONFIG_FILE)
        return True
    else:
        return False


def get_file_content():
    """Reads the local file containing the Google Sheets data."""
    if os.path.exists(configs.CONFIG_FILE):
        with open(configs.CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        return None


def sheet_to_map(rows, sheet: str, env: str):
    """Converts a Google Sheets worksheet to a dictionary."""
    rows = rows.copy()
    header_row = rows.pop(0)

    # Define config by name of the server
    server_index = header_row.index(env)

    data = {
        "__ENV__": env,
        "__SHEET__": sheet,
        "__SHEET_ID__": configs.GOOGLE_SHEET_ID
    }
    # Initialize a variable to track the current category
    current_category = None
    category_data = {}

    for row in rows:
        if len(row) > server_index:
            category = row[0]
            subcategory = row[1]
            value = row[server_index]

            # Check if the category has changed
            if category != current_category:
                # If it's a new category, save the current category data and start a new one.
                if current_category:
                    if current_category in data:
                        data[current_category] = {**data[current_category], **category_data}
                    else:
                        data[current_category] = category_data

                current_category = category
                category_data = {}

            # Add the subcategory and value to the current category's dictionary
            category_data[subcategory] = value

    if current_category:
        if current_category in data:
            data[current_category] = {**data[current_category], **category_data}
        else:
            data[current_category] = category_data

    return data


def load_google_sheet(sheet_name: str) -> []:
    """
        Downloads the Google Sheets data and saves it locally.
        Handles the authentication using a service account and returns the credentials.
        """
    # get credentials
    credential_str = base64.b64decode(configs.GOOGLE_CREDENTIAL_BASE64)
    credential_json = json.loads(credential_str)
    creds = Credentials.from_service_account_info(credential_json, scopes=configs.SCOPES)

    # get service
    service = build("sheets", "v4", credentials=creds)

    rows = None
    try:
        sheet = service.spreadsheets()
        result = (
            sheet.values()
            .get(spreadsheetId=configs.GOOGLE_SHEET_ID, range=sheet_name)
            .execute()
        )
        rows = result.get("values", [])
    except HttpError as err:
        print(err)
        exit(1)
    return rows


def load_file_and_save(sheet_name: str, env: str):
    rows = load_google_sheet(sheet_name)
    data = sheet_to_map(rows, sheet_name, env)
    save_to_file(data)


def get_value(sheet_data, category: str, name: str):
    """Gets the value in the sheet based on environment, category, and name."""
    if not sheet_data:
        return "No data found."
    if not category or not name:
        return "Category and name are required."

    if category not in sheet_data:
        print(f"Category '{category}' not found.")
        exit(1)
    if name not in sheet_data[category]:
        print(f"Name '{name}' not found in category '{category}'.")
        exit(1)

    return sheet_data[category][name]


def load_value(sheet: str, env: str, category: str, name: str) -> str:
    """Loads sheet and finds and return a value from the local file based on the specified parameters."""
    need_load = True
    try_count = 2
    data = None
    while need_load and try_count > 0:
        try_count -= 1
        need_load = False
        if not os.path.exists(configs.CONFIG_FILE):
            load_file_and_save(sheet_name=sheet, env=env)

        data = get_file_content()
        env_valid = "__ENV__" in data and data["__ENV__"] == env
        sheet_valid = "__SHEET__" in data and data["__SHEET__"] == sheet
        sheet_id_valid = "__SHEET_ID__" in data and data["__SHEET_ID__"] == configs.GOOGLE_SHEET_ID
        if not env_valid or not sheet_valid or not sheet_id_valid:
            need_load = True
            delete_file()

    if not data:
        print("No data found.")
        exit(1)

    result = get_value(data, category, name)
    return result


def read_cenv_url(url: str) -> str:
    """Parses the cenv URL and retrieves the corresponding value."""
    if not url.startswith("cenv://"):
        raise ValueError("Invalid cenv URL. Must start with 'cenv://'.")

    # Split the URL after the "cenv://" part
    parts = url[7:].split("/", 3)

    if len(parts) != 4:
        raise ValueError("Invalid cenv URL format. Must be 'cenv://SHEET/ENV/CATEGORY/NAME'.")

    sheet, env, category, name = parts

    return load_value(
        sheet=sheet,
        env=env,
        category=category,
        name=name
    )


# ------------------------------------------------------------
# COMMANDS
# ------------------------------------------------------------

def load_command(sheet: str, env: str):
    """Downloads the Google Sheets data and saves it locally."""
    load_file_and_save(sheet_name=sheet, env=env)
    print(f"Data loaded and saved to {configs.CONFIG_FILE}.")


def delete_command():
    """Deletes the local file containing the Google Sheets data."""
    if delete_file():
        print(f"{configs.CONFIG_FILE} deleted.")
    else:
        print(f"{configs.CONFIG_FILE} does not exist.")


def get_command(sheet: str, env: str, category: str, name: str):
    print(load_value(sheet=sheet, env=env, category=category, name=name))


def read_command(cenv_url: str):
    """Reads a value from Google Sheets using a cenv URL."""
    print(read_cenv_url(cenv_url))


def inject_command(template_path):
    """Processes a template file, replacing placeholders with actual data."""
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file '{template_path}' does not exist.")

    # Regular expressions for matching various patterns
    pattern_basic = re.compile(r'\$(\w+)')
    pattern_braced = re.compile(r'\${(\w+)(?::-([^}]+))?(?::\?([^}]+))?}')

    env_vars = {}

    def resolve_value(value):
        # Resolve patterns like $USER_NAME or ${USER_NAME}
        def replace_var(match):
            var_name = match.group(1)
            return env_vars.get(var_name, os.getenv(var_name, ''))

        def replace_braced_var(match):
            var_name = match.group(1)
            default_value = match.group(2)
            error_message = match.group(3)

            # Check if the variable exists in our env_vars or system environment
            if var_name in env_vars:
                return env_vars[var_name]
            elif var_name in os.environ:
                return os.getenv(var_name)
            elif default_value is not None:
                return default_value
            elif error_message is not None:
                raise ValueError(f"Env variable {var_name} not found: {error_message}")
            else:
                return ''

        # Resolve basic $VAR and braced ${VAR} patterns
        value = pattern_basic.sub(replace_var, value)
        value = pattern_braced.sub(replace_braced_var, value)

        return value

    output_lines = []

    with open(template_path, 'r') as file:
        for line in file:
            if "cenv://" in line:
                key, cenv_url = line.strip().split("=", 1)
                key = key.strip()
                cenv_url = cenv_url.strip()

                resolved_cenv_url = resolve_value(cenv_url)
                value = read_cenv_url(resolved_cenv_url)
                env_vars[key] = resolved_cenv_url
                output_lines.append(f"{key}={value}")
            elif "=" in line and not line.strip().startswith(("#", "//", ";", '"', "'", "/*", "=")):
                key, value = line.strip().split("=", 1)
                key = key.strip()
                value = value.strip()
                env_vars[key] = resolve_value(value)
                output_lines.append(f"{key}={env_vars[key]}")
            else:
                output_lines.append(line.strip())

    print("\n".join(output_lines))


def main():
    parser = argparse.ArgumentParser(
        description=f"""Manage and search Google Sheets data.
        {project_name} {project_version}
        https://github.com/{project_owner}/{project_repository}
        Environment variables: CENV_GOOGLE_CREDENTIAL_BASE64, CENV_GOOGLE_SHEET_ID, CENV_STORE_CONFIG_FILE"""
    )
    parser.add_help = True
    parser.add_argument("--version", action="version", version=f"{project_version}")
    parser.add_argument("--google_credential_base64", required=False,
                        help="Base64 encoded Google service account credentials or use CENV_GOOGLE_CREDENTIAL_BASE64 environment variable")
    parser.add_argument("--google_sheet_id", required=False,
                        help="Google Sheet ID or use CENV_GOOGLE_SHEET_ID environment variable")
    parser.add_argument("--google_sheet_name", required=False,
                        help="Google Sheet name or use CENV_GOOGLE_SHEET_NAME environment variable")
    parser.add_argument("--config_file", required=False,
                        help="Local file to save the Google Sheets data or use CENV_STORE_CONFIG_FILE environment variable")

    subparsers = parser.add_subparsers(dest="command")

    # Version command
    version_parser = subparsers.add_parser("version", help="Show the version of the tool")

    # Update command
    update_parser = subparsers.add_parser("update", help=f"Update {project_name} to the latest version")

    # Load command
    load_parser = subparsers.add_parser("load", help="Load data from Google Sheets and save it locally")
    load_parser.add_argument("--env", type=str, required=True, help="Environment to download")
    load_parser.add_argument("--sheet", type=str, required=True, help="Sheet name")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete the locally saved data")

    # Find command
    find_parser = subparsers.add_parser("get", help="Get a specific value in the loaded data")
    find_parser.add_argument("--sheet", type=str, required=True, help="Sheet name")
    find_parser.add_argument("--env", type=str, required=True, help="Environment column")
    find_parser.add_argument("--category", type=str, required=True, help="Category")
    find_parser.add_argument("--name", type=str, required=True, help="Name")

    # Read command
    read_parser = subparsers.add_parser("read", help="Read value from Google Sheets using cenv URL")
    read_parser.add_argument("cenv_url", type=str, help="cenv URL in the format cenv://SHEET/ENV/CATEGORY/NAME")

    # Inject command
    inject_parser = subparsers.add_parser("inject", help="Inject data from Google Sheets into a template file")
    inject_parser.add_argument("template_path", type=str, help="Path to the template file")

    args = parser.parse_args()

    configs.GOOGLE_CREDENTIAL_BASE64 = args.google_credential_base64 or configs.GOOGLE_CREDENTIAL_BASE64
    configs.GOOGLE_SHEET_ID = args.google_sheet_id or configs.GOOGLE_SHEET_ID
    configs.CONFIG_FILE = args.config_file or configs.CONFIG_FILE

    if configs.GOOGLE_CREDENTIAL_BASE64 is None:
        raise ValueError(
            "GOOGLE_CREDENTIAL_BASE64 environment variable or --google_credential_base64 parameter is not set. Please, see help.")
    if configs.GOOGLE_SHEET_ID is None:
        raise ValueError(
            "GOOGLE_SHEET_ID environment variable or --google_sheet_id parameter is not set. Please, see help.")
    if configs.CONFIG_FILE is None:
        raise ValueError(
            "CONFIG_FILE environment variable or --config_file parameter is not set. Please, see help.")

    if args.command == "load":
        load_command(sheet=args.sheet, env=args.env)
    elif args.command == "delete":
        delete_command()
    elif args.command == "get":
        get_command(sheet=args.sheet, env=args.env, category=args.category, name=args.name)
    elif args.command == "read":
        read_command(args.cenv_url)
    elif args.command == "inject":
        inject_command(args.template_path)
    elif args.command == "version":
        print(f"{project_version}")
    elif args.command == "update":
        update_cenv()


if __name__ == "__main__":
    main()
