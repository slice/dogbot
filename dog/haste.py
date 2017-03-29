import aiohttp

hastebin_endpoint = 'https://paste.safe.moe/documents'
hastebin_fmt = 'https://paste.safe.moe/{}.py'

async def haste(text):
    async with aiohttp.ClientSession() as session:
        async with session.post(hastebin_endpoint, data=text) as resp:
            resp_json = await resp.json()
            return hastebin_fmt.format(resp_json['key'])
