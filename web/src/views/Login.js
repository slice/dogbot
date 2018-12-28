import React from 'react'

import discord from '../assets/discord.svg'
import './Login.scss'

export default function Login() {
  return (
    <div id="login">
      <p>Before you can do that, you have to login to prove your identity:</p>

      <a href="/auth/session/new" id="discord-login-link">
        <img
          alt="Login with Discord"
          title="Login with Discord"
          src={discord}
        />
      </a>
    </div>
  )
}
