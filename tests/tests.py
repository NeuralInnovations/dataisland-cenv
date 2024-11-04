import unittest
from io import StringIO
from unittest.mock import patch
import os
import cenv
from cenv import Token, configs

# Sample data for testing
SAMPLE_GOOGLE_SHEET_ID = "test_sheet_id"
SAMPLE_ENV = "test_env"
SAMPLE_CATEGORY = "test_category"
SAMPLE_NAME = "test_name"
SAMPLE_VALUE = "test_value"
SAMPLE_SHEET_DATA = [
    ["Category", "Name", SAMPLE_ENV],
    [SAMPLE_CATEGORY, SAMPLE_NAME, SAMPLE_VALUE]
]


class TestGoogleSheetProcessing(unittest.TestCase):

    @patch('cenv.load_google_sheet', return_value=SAMPLE_SHEET_DATA)
    def test_load_file_and_save(self, mock_load_google_sheet):
        cenv.load_file_and_save("SHEET_NAME", SAMPLE_ENV)
        cenv.delete_file()

    @patch('sys.stdout', new_callable=StringIO)
    @patch('cenv.load_google_sheet', return_value=SAMPLE_SHEET_DATA)
    def test_inject_command(self, mock_load_google_sheet, mock_stdout):
        file_path = "./tests/inject.template"
        if not os.path.exists(file_path):
            file_path = "./inject.template"

        cenv.inject_command(file_path, False)
        printed_output = mock_stdout.getvalue().strip()
        self.assertEqual(printed_output.strip(), """APP_ENV=Test
SHEET_NAME=test_sheet_name
CATEGORY=test_category
NAME=test_name
ENV_NAME=test_env
# = comment
ENV_1=hello
ENV_2=op://Env/Test/Test/Value
ENV_3=test_value""".strip())
        cenv.delete_file()

    @patch('sys.stdout', new_callable=StringIO)
    @patch('cenv.load_google_sheet', return_value=SAMPLE_SHEET_DATA)
    def test_load_command(self, mock_load_google_sheet, mock_stdout):
        cenv.load_command("SHEET_NAME", SAMPLE_ENV)
        printed_output = mock_stdout.getvalue().strip()
        self.assertEqual(printed_output, f"Data loaded and saved to {cenv.configs.CONFIG_FILE}.")
        cenv.delete_file()

    @patch('sys.stdout', new_callable=StringIO)
    @patch('cenv.load_google_sheet', return_value=SAMPLE_SHEET_DATA)
    def test_delete_command(self, mock_load_google_sheet, mock_stdout):
        cenv.load_file_and_save("SHEET_NAME", SAMPLE_ENV)
        cenv.delete_command()
        printed_output = mock_stdout.getvalue().strip()
        self.assertEqual(printed_output, f"{cenv.configs.CONFIG_FILE} deleted.")

    @patch('sys.stdout', new_callable=StringIO)
    @patch('cenv.load_google_sheet', return_value=SAMPLE_SHEET_DATA)
    def test_read_command(self, mock_load_google_sheet, mock_stdout):
        cenv.read_command(f"cenv://SHEET_NAME/{SAMPLE_ENV}/{SAMPLE_CATEGORY}/{SAMPLE_NAME}")
        printed_output = mock_stdout.getvalue().strip()
        self.assertEqual(printed_output, SAMPLE_VALUE)
        cenv.delete_file()

    @patch('sys.stdout', new_callable=StringIO)
    @patch('cenv.load_google_sheet', return_value=SAMPLE_SHEET_DATA)
    def test_get_command(self, mock_load_google_sheet, mock_stdout):
        cenv.get_command("SHEET_NAME", SAMPLE_ENV, SAMPLE_CATEGORY, SAMPLE_NAME)
        printed_output = mock_stdout.getvalue().strip()
        self.assertEqual(printed_output, SAMPLE_VALUE)
        cenv.delete_file()

    @patch('sys.stdout', new_callable=StringIO)
    def test_token_encode_decode(self, mock_stdout):
        token = Token(
            configs.GOOGLE_CREDENTIAL_BASE64,
            configs.GOOGLE_SHEET_ID,
            configs.GOOGLE_SHEET_NAME,
            configs.CONFIG_FILE
        )
        encoded = cenv.token_encode(token)
        decoded = cenv.token_decode(encoded)

        self.assertEqual(token.google_cred_base64, decoded.google_cred_base64)
        self.assertEqual(token.google_sheet_id, decoded.google_sheet_id)
        self.assertEqual(token.google_sheet_name, decoded.google_sheet_name)
        self.assertEqual(token.store_config_file, decoded.store_config_file)

        cenv.token_generate_command()
        printed_output = mock_stdout.getvalue().strip()
        self.assertEqual(printed_output, encoded)


if __name__ == "__main__":
    unittest.main()
