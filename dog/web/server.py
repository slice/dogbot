from quart import Quart, g

from .api import api
from .auth import auth
from .quotes import quotes

app = Quart(__name__)
app.bot = None  # type: ignore


@app.before_request
def assign_globals():
    g.bot = app.bot  # type: ignore


app.register_blueprint(api, url_prefix="/api")
app.register_blueprint(auth, url_prefix="/auth")
app.register_blueprint(quotes, url_prefix="/api/quotes")
