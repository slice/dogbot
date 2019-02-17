import React from 'react'
import styled from 'styled-components'

import { adjust } from '../theming'

const StyledIcon = styled.img`
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 100%;
  object-fit: cover;

  ${(props) => props.empty && `background: ${adjust(0.3, props.theme.bg)}`}
`

export function GuildIcon({ guild }) {
  return guild.icon_url !== '' ? (
    <Icon url={guild.icon_url} alt={`Server icon for ${guild.name}`} />
  ) : (
    <Icon placeholder />
  )
}

export default function Icon({ url, alt, placeholder = false }) {
  if (url === '' || url == null || placeholder) {
    return <StyledIcon as="div" className="icon" empty />
  }

  return <StyledIcon className="icon" title={alt} src={url} />
}
