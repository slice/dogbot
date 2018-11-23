export default class API {
  static async get<R>(route: string): Promise<R> {
    const resp = await window.fetch(route, { credentials: 'include' })
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status} (${resp.statusText})`)
    }
    return await resp.json()
  }
}
