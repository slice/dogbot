import React from 'react'

import './Guild.scss'

export default function Guild({ guild }) {
  return (
    <div className="guild">
      <img
        className="icon"
        alt={`Server icon for ${guild.name}`}
        src={guild.icon_url}
      />
      <div className="name">{guild.name}</div>
    </div>
  )
}
