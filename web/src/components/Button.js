import React from 'react'
import classnames from 'classnames'

import './Button.scss'

export default function Button({ className: providedClassName, ...props }) {
  const className = classnames('button', providedClassName)
  return <button type="button" className={className} {...props} />
}
