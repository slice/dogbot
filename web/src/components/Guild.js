import React from 'react'

import './Guild.scss'
import GuildIcon from './GuildIcon'

export default function Guild({ guild }) {
  return (
    <div className="guild">
      <GuildIcon guild={guild} />
      <div className="name">{guild.name}</div>
    </div>
  )
}
