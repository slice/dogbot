export default class API {
  static async get(route) {
    const resp = await window.fetch(route, { credentials: 'include' })

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status} (${resp.statusText})`)
    }

    try {
      const data = await resp.json()
      return data
    } catch (err) {
      throw new Error('Malformed JSON response')
    }
  }
}
