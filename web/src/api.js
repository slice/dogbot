export default class API {
  static request (url) {
    return fetch(url, { credentials: 'include' }).then(resp => resp.json())
  }
}
