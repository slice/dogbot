import React from 'react'

import './Icon.scss'

export function GuildIcon({ guild }) {
  return guild.icon_url !== '' ? (
    <Icon url={guild.icon_url} alt={`Server icon for ${guild.name}`} />
  ) : (
    <Icon placeholder />
  )
}

export default function Icon({ url, alt, placeholder = false }) {
  if (url === '' || url == null || placeholder) {
    return <div className="icon placeholder" />
  }

  return <img className="icon" alt={alt} src={url} />
}
