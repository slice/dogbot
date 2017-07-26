from io import BytesIO


async def get_bytesio(session, url: str):
    async with session.get(url) as resp:
        return BytesIO(await resp.read())


async def get_json(session, url):
    async with session.get(url) as resp:
        return await resp.json()
