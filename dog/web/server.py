from sanic import Sanic, response

app = Sanic(__name__)
app.bot = None


@app.route('/api/status')
async def api_ping(_request):
    return response.json({
        'ready': app.bot.is_ready(),
        'ping': app.bot.latency,
        'guilds': len(app.bot.guilds),
    })
