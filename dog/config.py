import lifesaver


class DogOAuthConfig(lifesaver.config.Config):
    client_id: int
    client_secret: str
    redirect_uri: str


class DogWebConfig(lifesaver.config.Config):
    # Hypercorn config
    http: dict

    # Quart config
    app: dict


class DogAPIKeysConfig(lifesaver.config.Config):
    google_maps: str


class DogConfig(lifesaver.bot.BotConfig):
    dashboard_link: str = "http://localhost:8080"
    server_invite: str = "https://discord.gg/invalid-invite"

    oauth: DogOAuthConfig
    web: DogWebConfig
    api_keys: DogAPIKeysConfig
