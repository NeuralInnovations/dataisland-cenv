# dataisland-cenv

## Install

macos | ubuntu
```bash
curl https://raw.githubusercontent.com/NeuralInnovations/dataisland-cenv/refs/heads/master/install.sh | sh
```

---

## How to use
### Requirements
ENVIRONMENT VARIABLES
```bash
# Google Credentials
GOOGLE_CREDENTIAL_BASE64=

# Google Sheet File Id
GOOGLE_SHEET_ID=

# Google Sheet Name (table)
GOOGLE_SHEET_NAME=Env

# Where to save the config file locally
CONFIG_FILE=config.json
```

For usage, you can enter a command like this:
```bash
# load the config file
cenv load

# find the environment
cenv find --sheet Env --env dev1 --category Elastic --name Url

# delete the config file
cenv delete
```