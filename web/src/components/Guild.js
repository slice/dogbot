import React from 'react'

import './Guild.scss'
import ShrinkableText from './ShrinkableText'
import GuildIcon from './GuildIcon'

export default function Guild({ guild }) {
  return (
    <div className="guild">
      <GuildIcon guild={guild} />
      <ShrinkableText className="name">{guild.name}</ShrinkableText>
    </div>
  )
}
