import argparse
import base64
import configparser
import json
import os
import pkgutil
import sys

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


def get_credentials():
    """Handles the authentication using a service account and returns the credentials."""
    credential_str = base64.b64decode(configs.GOOGLE_CREDENTIAL_BASE64)
    credential_json = json.loads(credential_str)
    creds = Credentials.from_service_account_info(credential_json, scopes=configs.SCOPES)

    return creds


def fetch_full_sheet(service, sheet_name):
    """Fetches the entire data from the specified Google Sheets worksheet."""
    try:
        sheet = service.spreadsheets()
        result = (
            sheet.values()
            .get(spreadsheetId=configs.GOOGLE_SHEET_ID, range=sheet_name)
            .execute()
        )
        values = result.get("values", [])
        return values
    except HttpError as err:
        print(err)
        return None


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


def load_file(sheet: str, env: str):
    """Downloads the Google Sheets data and saves it locally."""
    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)
    rows = fetch_full_sheet(service, sheet)
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
            load_file(sheet=sheet, env=env)

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
    load_file(sheet=sheet, env=env)
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

    output_lines = []

    with open(template_path, 'r') as file:
        for line in file:
            if "cenv://" in line:
                key, cenv_url = line.strip().split("=", 1)
                value = read_cenv_url(cenv_url)
                output_lines.append(f"{key}={value}")
            else:
                output_lines.append(line.strip())

    print("\n".join(output_lines))


def main():
    parser = argparse.ArgumentParser(
        description=f"""Manage and search Google Sheets data.
        {project_name} {project_version}
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


if __name__ == "__main__":
    main()
