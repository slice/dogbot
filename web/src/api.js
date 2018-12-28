export default class API {
  static async request(method, route, options) {
    const resp = await window.fetch(route, {
      credentials: 'include',
      method,
      ...options,
    })

    if (!resp.ok) {
      try {
        var { message } = await resp.json()
      } catch (err) {
        throw new Error(`HTTP ${resp.status} (${resp.statusText})`)
      }

      throw new Error(message)
    }

    try {
      const data = await resp.json()
      return data
    } catch (err) {
      throw new Error('Malformed JSON response')
    }
  }
}

for (const verb of ['get', 'patch', 'put', 'delete', 'post']) {
  API[verb] = (...params) => {
    return API.request(verb.toUpperCase(), ...params)
  }
}
