import aiohttp

HASTEBIN_ENDPOINT = 'https://paste.safe.moe/documents'
HASTEBIN_FMT = 'https://paste.safe.moe/{}.py'

async def haste(text):
    async with aiohttp.ClientSession() as session:
        async with session.post(HASTEBIN_ENDPOINT, data=text) as resp:
            resp_json = await resp.json()
            return HASTEBIN_FMT.format(resp_json['key'])
