# dataisland-cenv

## Install

macos | ubuntu

```bash
curl https://raw.githubusercontent.com/NeuralInnovations/dataisland-cenv/refs/heads/master/install.sh | bash
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

ENVIRONMENT VARIABLES

```bash
# Google Credentials
CENV_GOOGLE_CREDENTIAL_BASE64=

# Google Sheet File Id
CENV_GOOGLE_SHEET_ID=

# Google Sheet Name (table)
CENV_GOOGLE_SHEET_NAME=Env

# Where to save the config file locally
CENV_STORE_CONFIG_FILE=config.json
```

For usage, you can enter a command like this:

```bash
# help
cenv help

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