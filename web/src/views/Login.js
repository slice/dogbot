import React from 'react'

import discord from '../assets/discord.svg'
import './Login.scss'

export default function Login() {
  return (
    <div id="login">
      <p>Login with Discord:</p>

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
