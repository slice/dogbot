import React from 'react'
import AceEditor from 'react-ace'
import 'brace/mode/yaml'
import 'brace/theme/github'

import './ConfigEditor.scss'

export default function ConfigEditor(props) {
  return (
    <AceEditor mode="yaml" theme="github" name="config-editor" {...props} />
  )
}
