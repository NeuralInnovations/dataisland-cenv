import argparse
import base64
import configparser
import json
import os
import pickle
import pkgutil
import sys
import platform
import requests
import subprocess
import re

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from google_auth_httplib2 import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials as GoogleCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
import httplib2

load_dotenv()


# Function to read properties file
def load_embedded_file(path):
    # Check if running as a PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundled mode
        base_path = sys._MEIPASS
        properties_path = os.path.join(base_path, path)
        with open(properties_path, 'r') as f:
            return f.read()
    else:
        # Try loading using pkgutil if the script is part of a package
        try:
            data = pkgutil.get_data(__name__, path)
            if data:
                return data.decode('utf-8')
        except ValueError:
            # If __main__ or not a package, manually load the file from the script directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            properties_path = os.path.join(script_dir, path)
            with open(properties_path, 'r') as f:
                return f.read()


# Initialize the parser
project_properties = configparser.ConfigParser()

# Read the properties file
project_properties.read_string(load_embedded_file('project.properties'))

# Access the properties
project_name = project_properties['DEFAULT']['name'].strip(" \"\t\n\r")
project_version = project_properties['DEFAULT']['version'].strip(" \"\t\n\r")
project_owner = project_properties['DEFAULT']['owner'].strip(" \"\t\n\r")
project_repository = project_properties['DEFAULT']['repository'].strip(" \"\t\n\r")

update_install_dir = "/usr/local/bin" if platform.system() != "Windows" else os.path.expanduser("~\\bin")
update_filename = "cenv-macos" if platform.system() == "Darwin" else f"cenv-{platform.system().lower()}-{platform.machine()}"
update_filename += ".exe" if platform.system() == "Windows" else ""


def normalize_path(path: str) -> str:
    # Split the path into segments
    parts = path.split(os.sep)

    # Replace any occurrence of `~` in segments with the user home directory
    parts = [os.path.expanduser(part) if part == "~" else part for part in parts]

    # Join the parts and normalize the full path
    normalized_path = os.path.normpath(os.path.join(*parts))

    return normalized_path


def ensure_directory_exists(directory):
    """Creates the directory if it does not exist."""
    if not os.path.exists(directory):
        print(f"Creating directory: {directory}")
        os.makedirs(directory, exist_ok=True)


def update_add_to_path_if_needed(directory):
    """Adds the specified directory to PATH if not already included."""
    path = os.environ["PATH"]
    if directory not in path:
        print(f"Adding {directory} to PATH...")
        subprocess.call(f'setx PATH "%PATH%;{directory}"', shell=True)
        print("You may need to restart your terminal for changes to take effect.")


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

    ensure_directory_exists(update_install_dir)

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
    TOKEN_FILE: str

    def __init__(self):
        self.GOOGLE_CREDENTIAL_BASE64 = os.getenv("CENV_GOOGLE_CREDENTIAL_BASE64")
        self.GOOGLE_SHEET_ID = os.getenv("CENV_GOOGLE_SHEET_ID")
        self.GOOGLE_SHEET_NAME = os.getenv("CENV_GOOGLE_SHEET_NAME", "Env")
        self.CONFIG_FILE = os.getenv("CENV_STORE_CONFIG_FILE", "./cenv_config.json")
        self.SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        self.TOKEN_FILE = normalize_path("~/.cenv/.token")
        ensure_directory_exists(os.path.dirname(self.TOKEN_FILE))


configs = Configs()


def save_to_file(data):
    """Saves the Google Sheets data to a local file."""

    # Get the directory part of the path
    directory = os.path.dirname(configs.CONFIG_FILE)

    # Create the directory if it doesn't exist
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    # Check if the file already exists
    # Delete it if it does
    delete_file()

    # Write the data to the file
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

    creds = read_google_token_creds()
    if creds is None:
        credential_str = base64.b64decode(configs.GOOGLE_CREDENTIAL_BASE64)
        credential_json = json.loads(credential_str)
        creds = Credentials.from_service_account_info(credential_json, scopes=configs.SCOPES)

    if creds is None:
        print("Failed to get Google credentials.")
        print("Use 'cenv login' to authenticate with Google account.")
        print("Or set service account using the CENV_GOOGLE_CREDENTIAL_BASE64 environment variable.")
        exit(1)

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
# ENV RESOLVER
# ------------------------------------------------------------

# Define patterns for matching different parts of the .env syntax
pattern_basic = re.compile(r'\$(\w+)')
pattern_braced = re.compile(r'\${(\w+)(?::-([^}]+))?(?::\?([^}]+))?}')
pattern_quoted = re.compile(r'^"(.*)"$')  # Pattern for detecting quoted strings
pattern_comment = re.compile(r'(?<!\\) #.*$')  # Pattern to match unescaped `#` for comments


def resolve_value(env_vars, value):
    # Check if the original value was quoted
    is_quoted = pattern_quoted.match(value)

    # Remove surrounding quotes if the value is quoted for internal processing
    if is_quoted:
        value = pattern_quoted.sub(r'\1', value)

    # Resolve patterns like $USER_NAME or ${USER_NAME}
    def replace_var(match):
        var_name = match.group(1)
        tmp_val = env_vars.get(var_name, None)
        if tmp_val:
            if tmp_val.startswith(('"', "'")):
                tmp_val = tmp_val[1:]
            if tmp_val.endswith(('"', "'")):
                tmp_val = tmp_val[:-1]
            return tmp_val
        return os.getenv(var_name, '')

    def replace_braced_var(match):
        var_name = match.group(1)
        default_value = match.group(2)
        error_message = match.group(3)

        # Check if the variable exists in our env_vars or system environment
        if var_name in env_vars:
            tmp_val = env_vars[var_name]
            if tmp_val.startswith('"'):
                tmp_val = tmp_val[1:]
            if tmp_val.endswith('"'):
                tmp_val = tmp_val[:-1]
            return tmp_val
        elif var_name in os.environ:
            return os.getenv(var_name)
        elif default_value is not None:
            return default_value
        elif error_message is not None:
            raise ValueError(error_message)
        else:
            return ''

    # Resolve basic $VAR and braced ${VAR} patterns within the string
    value = pattern_basic.sub(replace_var, value)
    value = pattern_braced.sub(replace_braced_var, value)

    # If the initial value was quoted, apply quotes to the entire final resolved value
    if is_quoted:
        value = f'"{value}"'

    return value


# ------------------------------------------------------------
# COMMANDS
# ------------------------------------------------------------
def read_google_token_creds():
    creds = None
    if os.path.exists(configs.TOKEN_FILE):
        with open(configs.TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request(httplib2.Http()))
                else:
                    creds = None
    return creds


def google_logout_command():
    if os.path.exists(configs.TOKEN_FILE):
        os.remove(configs.TOKEN_FILE)


def google_login_command():
    creds = read_google_token_creds()

    # If no valid credentials, go through OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request(httplib2.Http()))
        else:
            flow = InstalledAppFlow.from_client_config(
                json.loads(load_embedded_file('client_secret.json')),
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials for future runs
        with open(configs.TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return creds


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


def inject_command(template_path: str, skip_comments: bool):
    """Processes a template file, replacing placeholders with actual data."""
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file '{template_path}' does not exist.")

    env_vars = {}

    output_lines = []

    # Regular expression to strip comments that are outside of quoted strings
    comment_pattern = re.compile(r'(?<!\\)(?:"[^"]*"|\'[^\']*\'|[^\'"#])*?#.*$')
    pattern_comment = re.compile(r'(?<!\\)(["\'].*?["\']|[^"\']*?)(?<!\\) #.*$')

    def remove_comment(line_to_clean):
        """
        Remove any inline comment that starts with # outside of quoted strings.
        """
        # Remove the comment if it's outside of quotes
        cleaned_line = pattern_comment.sub(r'\1', line_to_clean).strip()
        return cleaned_line

    with open(template_path, 'r') as file:
        for line in file:
            stripped_line = line.strip()
            is_comment = stripped_line.startswith(("#", "//", ";", '"', "'", "/*", "="))

            if skip_comments:
                # Remove inline comments if they're outside of quotes
                stripped_line = remove_comment(stripped_line)

            if skip_comments and is_comment:
                continue
            if not is_comment and "=" in stripped_line:
                # Remove inline comments only if they are outside of quotes
                line_no_comment = remove_comment(stripped_line)

                # Process key-value pairs
                first, second = line_no_comment.split("=", 1)
                key = first.strip()
                source_value = second.strip()

                # Resolve the value with your custom logic
                value = resolve_value(env_vars, source_value)
                if value.startswith("cenv://"):
                    value = read_cenv_url(value)
                env_vars[key] = value

                # Add resolved key-value to output
                output_lines.append(f"{key}={value}")
            else:
                # Retain full line if it’s a comment or doesn’t contain '='
                output_lines.append(stripped_line)

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

    # Login command
    login_parser = subparsers.add_parser("login", help="Authenticate with Google account")

    # Logout command
    logout_parser = subparsers.add_parser("logout", help="Logout from Google account")

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
    inject_parser.add_argument("--skip-comments", action='store_true', required=False, default=False,
                               help="skip comments")

    args = parser.parse_args()

    configs.GOOGLE_CREDENTIAL_BASE64 = args.google_credential_base64 or configs.GOOGLE_CREDENTIAL_BASE64
    configs.GOOGLE_SHEET_ID = args.google_sheet_id or configs.GOOGLE_SHEET_ID
    configs.CONFIG_FILE = args.config_file or configs.CONFIG_FILE

    configs.CONFIG_FILE = normalize_path(configs.CONFIG_FILE)

    if args.command == "delete":
        delete_command()
    elif args.command == "version":
        print(f"{project_version}")
    elif args.command == "login":
        google_login_command()
    elif args.command == "logout":
        google_logout_command()
    elif args.command == "update":
        update_cenv()
    else:
        if configs.GOOGLE_CREDENTIAL_BASE64 is None and read_google_token_creds() is None:
            raise ValueError(
                "No auth. Use 'cenv login' or set CENV_GOOGLE_CREDENTIAL_BASE64 environment variable or --google_credential_base64 parameter to use service account. Please, see help.")
        if configs.GOOGLE_SHEET_ID is None:
            raise ValueError(
                "CENV_GOOGLE_SHEET_ID environment variable or --google_sheet_id parameter is not set. Please, see help.")
        if configs.CONFIG_FILE is None or configs.CONFIG_FILE == "." or configs.CONFIG_FILE == "":
            raise ValueError(
                "CENV_STORE_CONFIG_FILE environment variable or --config_file parameter is not set. Please, see help.")

        if args.command == "load":
            load_command(sheet=args.sheet, env=args.env)
        elif args.command == "get":
            get_command(sheet=args.sheet, env=args.env, category=args.category, name=args.name)
        elif args.command == "read":
            read_command(args.cenv_url)
        elif args.command == "inject":
            inject_command(args.template_path, args.skip_comments)


if __name__ == "__main__":
    main()
