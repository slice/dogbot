import React from 'react'

import './GuildIcon.scss'

export default function GuildIcon({ guild }) {
  return (
    <img
      className="guild-icon"
      alt={`Server icon for ${guild.name}`}
      src={guild.icon_url}
    />
  )
}
