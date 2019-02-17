import React from 'react'
import styled from 'styled-components'

import discord from '../assets/discord.svg'

const StyledLogin = styled.div`
  display: flex;
  flex-flow: column nowrap;
  justify-content: center;
  align-items: center;
  margin: 2rem 0;
`

const DiscordLogin = styled.a`
  display: block;
  margin: 1rem 0 0;
  border: solid 1px #ccc;
  border-radius: 0.15rem;
  width: 25rem;
  padding: 1rem;

  img {
    display: block;
  }
`

export default function Login() {
  return (
    <StyledLogin>
      <p>Login with Discord:</p>

      <DiscordLogin href="/auth/login">
        <img
          alt="Login with Discord"
          title="Login with Discord"
          src={discord}
        />
      </DiscordLogin>
    </StyledLogin>
  )
}
