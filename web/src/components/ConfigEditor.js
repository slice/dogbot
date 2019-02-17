import React from 'react'
import AceEditor from 'react-ace'
import 'brace/mode/yaml'
import 'brace/theme/dawn'

import './ConfigEditor.scss'

export default function ConfigEditor(props) {
  return <AceEditor mode="yaml" theme="dawn" name="config-editor" {...props} />
}
