export default class API {
  static request (url) {
    return fetch(url).then(resp => resp.json())
  }
}
