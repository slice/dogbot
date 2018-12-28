import React from 'react'
import { Link } from 'react-router-dom'

import './Landing.scss'

export default function Landing() {
  return (
    <div id="landing">
      <header>dogbot!</header>
      <p className="lead">
        dogbot is a highly configurable utility and moderation Discord bot,
        kinda like rowboat. It can keep track of users' timezones, gatekeep your
        server, create quotes from messages, and it even has some fun stuff like
        a virtual currency.
      </p>
      <Link className="landing-button" to="/guilds">
        Manage my servers
      </Link>
    </div>
  )
}
