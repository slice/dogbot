import React from 'react'

import './GuildIcon.scss'

export default function GuildIcon({ guild }) {
  if (guild.icon_url === '') {
    return <div className="guild-icon placeholder" />
  }

  return (
    <img
      className="guild-icon"
      alt={`Server icon for ${guild.name}`}
      src={guild.icon_url}
    />
  )
}
