module.exports = {
  devServer: {
    proxy: {
      '/auth*': { target: 'http://localhost:8993' },
      '/api*': { target: 'http://localhost:8993' }
    }
  }
}
