let guilds = []

export default class API {
  static async guilds () {
    if (!guilds.length) guilds = await this.get('/api/guilds')
    return guilds
  }

  static get (url) {
    return fetch(url, { credentials: 'include' }).then(resp => resp.json())
  }

  static patch (url, content, config = {}) {
    return fetch(url, {
      body: content,
      credentials: 'include',
      method: 'PATCH',
      ...config
    }).then(resp => resp.json())
  }
}
