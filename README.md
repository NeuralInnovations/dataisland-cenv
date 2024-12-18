# dataisland-cenv

## Install

macos | ubuntu

**BASH**

```bash
curl https://raw.githubusercontent.com/NeuralInnovations/dataisland-cenv/refs/heads/master/install.sh | bash
```

**ZSH**

```zsh
curl https://raw.githubusercontent.com/NeuralInnovations/dataisland-cenv/refs/heads/master/install.sh | zsh
```

---

## Example of sheet

[Google Sheet Example](https://docs.google.com/spreadsheets/d/1ykOxHza5fxa-HbXPPlSGfTSm2YKG0AteNhDHI6tntUk/edit?gid=0#gid=0)

### Required columns:

- **Category**
- **Name**

[Evn1, Staging, Production, Develop] - are the example of environments

| Category  | Name  | Evn1            | Staging           | Production       | Develop         |
|-----------|-------|-----------------|-------------------|------------------|-----------------|
| Category1 | Name1 | value1          | val1              | val2             | v1              |
| Category2 | Name1 | example1        | env1              | env2             | v2              |
| Database  | Host  | http://env1.com | https://stage.com | https://prod.com | https://dev.com |

---

## How to use

### Requirements

1. #### Google Client Secret file (client_secret.json)
- copy the "client_secret.json" from google console to the root of the project
to develop and test the application

2. #### ENVIRONMENT VARIABLES

```bash
# Google Credentials (service_account json) Base64
CENV_GOOGLE_CREDENTIAL_BASE64=

# Google Sheet File Id (example https://docs.google.com/spreadsheets/d/!!!!ID_HERE!!!!/)
CENV_GOOGLE_SHEET_ID=

# Google Sheet Name (table sheet name)
CENV_GOOGLE_SHEET_NAME=Env

# Where to save the config file locally
CENV_STORE_CONFIG_FILE=config.json
```

For usage, you can enter a command like this:

```bash
# help
cenv help

# login to google or use the service account by setting the environment variable CENV_GOOGLE_CREDENTIAL_BASE64 or --google_credential_base64
cenv login

# logout
cenv logout

# download the last version of the cenv
cenv update

# load the config file (optional, not necessary to use)
cenv load --sheet Env --env dev1

# get the environment
cenv get --sheet Env --env dev1 --category Elastic --name Url

# read, for example cenv read "cenv://Env/Staging/Database/ConnectionString"
cenv read "cenv://$SHEET/$ENV/$CATEGORY/$NAME"

# inject the config file
# example .env.template file
# DATABASE_URL="cenv://Env/Staging/Database/ConnectionString"
cenv inject .env.template > .env

# get version
cenv version

# delete the config file
cenv delete
```

## Injection

The inject command can resolve environment variables from the input file and print to the output.

```bash
cenv inject .env.template
```

```.env.template
ENV_TABLE=UnitTests
ENV_CATEGORY_NAME=Category1
ENV_CATEGORY=$ENV_CATEGORY_NAME
ENV_NAME=unittest
ENV_TEST_NAME=Value2
ENV_VALUE_NAME=$ENV_TEST_NAME
ENV_1=hello
ENV_2=op://Env/$APP_ENV/Database/ConnectionString
ENV_3=cenv://$ENV_TABLE/${ENV_NAME:?error_env_not_found}/${ENV_CATEGORY}/${ENV_VALUE:-Value1}
# support = comments
ENV_4=cenv://$ENV_TABLE/$ENV_NAME/$ENV_CATEGORY/$ENV_VALUE_NAME
```