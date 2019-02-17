import React from 'react'
import styled from 'styled-components'

import { adjust } from '../theming'
import ShrinkableText from './ShrinkableText'
import { GuildIcon } from './Icon'

const StyledGuild = styled.div`
  display: flex;
  flex-flow: row nowrap;
  align-items: center;
  padding: 1rem;

  ${ShrinkableText} {
    display: block;
    font-size: 1.25rem;
    margin-left: 1rem;
    font-weight: bold;
  }

  &:hover {
    background: ${(props) => adjust(0.03, props.theme.bg)}
    border-radius: 0.15rem;
    cursor: pointer;
  }
`

export default function Guild({ guild }) {
  return (
    <StyledGuild>
      <GuildIcon guild={guild} />
      <ShrinkableText>{guild.name}</ShrinkableText>
    </StyledGuild>
  )
}
