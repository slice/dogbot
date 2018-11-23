import React from 'react'

import './Guild.scss'
import { Guild as GuildT } from '../types'

const Guild: React.SFC<{ guild: GuildT }> = ({ guild }) => {
  return (
    <div className="guild">
      <img className="icon" src={guild.icon_url} />
      <div className="name">{guild.name}</div>
    </div>
  )
}

export default Guild
