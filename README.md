# `dogbot`

my sweet little bot

## configuration example

```yml
tokens:
  bot: '<discord token>'
bot:
  woof:
    invite: '<support server invite>'
    guild_id: <support server id>
    donator_role: <support server donator role id>
  owner_id: <owner id>
  prefixes: ['<prefix>', '<another prefix...>']
  github: '<repo owner>/<repo name>'
  options:
    description: '<bot description>'
    pm_help: null
credentials:
  owm: '<open weather map key>' # optional
  oxford: # optional
    application_id: '<oxford app id>'
    application_key: '<oxford app key>'
  reddit:
    client_id: '<reddit app client id>'
    client_secret: '<reddit app secret>'
    user_agent: 'discord:dogbot:v1.0.0 (by /u/<reddit username>)'
db:
  redis: '<redis host>'
  postgres:
    user: '<postgres role name>'
    password: '<postgres role password>'
    database: '<postgres db name>'
    host: '<postgres host>'
monitoring:
  health_webhook: '<webhook url with token>' # optional
  datadog: # optional
    statsd_host: '<statsd host>'
    api_key: '<http api key>'
    app_key: '<http app key>'
  monitor_channels: # optional
    # guild joins/leaves will be logged here
    - <monitor channel id>
  raven_client_url: '<raven client url>' # optional
  discordpw_token: '<discord pw token>' # optional
```
