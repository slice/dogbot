import React from 'react'
import ReactDOM from 'react-dom'
import { createGlobalStyle } from 'styled-components'

import { sansSerif, monospace } from './theming'
import App from './components/App'

export const GlobalStyle = createGlobalStyle`
  html,
  body,
  #root,
  #app-wrapper,
  #content {
    width: 100%;
    height: 100%;
  }

  body {
    margin: 0;
    padding: 0;

    color: ${(props) => props.theme.fg};
    background: ${(props) => props.theme.bg};

    font-size: 16px;
    line-height: 1.3;
    font-family: ${sansSerif};
  }

  code {
    font-family: ${monospace};
  }

  :focus {
    outline: ${(props) => props.theme.accent} auto 4px;
  }

  *,
  *:before,
  *:after {
    box-sizing: border-box;
  }

  #content {
    max-width: 850px;
    padding: 1rem 2rem 2rem 2rem;
    margin: 0 auto;
  }
`

ReactDOM.render(<App />, document.getElementById('root'))
