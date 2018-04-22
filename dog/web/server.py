from quart import Quart, session, redirect, g
from .api import api
from .auth import auth

app = Quart(__name__)
app.bot = None


@app.before_request
def assign_globals():
    g.bot = app.bot


@app.route('/')
def dashboard():
    return '...'


app.register_blueprint(api, url_prefix='/api')
app.register_blueprint(auth, url_prefix='/auth')
