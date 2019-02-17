import React from 'react'
import styled from 'styled-components'

import Icon from './Icon'

const StyledUser = styled.div`
  display: flex;
  align-items: center;
`

const Name = styled.div`
  margin-left: 0.5em;
`

export default function User({ user, className }) {
  const icon =
    user.avatar != null ? (
      <Icon
        url={`https://cdn.discordapp.com/avatars/${user.id}/${
          user.avatar
        }.png?size=128`}
        alt={`${user.username}'s avatar`}
      />
    ) : (
      <Icon placeholder />
    )

  return (
    <StyledUser className={className}>
      {icon}
      <Name className="username">
        {user.username}#{user.discriminator}
      </Name>
    </StyledUser>
  )
}
