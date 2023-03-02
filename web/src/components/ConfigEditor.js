import React from 'react'
import styled from 'styled-components'
import { lighten } from 'polished'
import AceEditor from 'react-ace'

import 'ace-builds/src-noconflict/mode-yaml'
import 'ace-builds/src-noconflict/theme-twilight'
import 'ace-builds/src-noconflict/theme-dawn'

const StyledAceEditor = styled(AceEditor).attrs((props) => ({
  theme: props.theme.name === 'dark' ? 'twilight' : 'dawn',
  _theme: props.theme,
}))`
  width: 100% !important;

  &.ace-twilight {
    background-color: ${(props) => lighten(0.03, props._theme.bg)} !important;

    .ace_gutter {
      background-color: ${(props) => lighten(0.05, props._theme.bg)} !important;
      color: ${(props) => props._theme.fg} !important;
    }
  }
`

export default function ConfigEditor(props) {
  return <StyledAceEditor mode="yaml" name="config-editor" {...props} />
}
