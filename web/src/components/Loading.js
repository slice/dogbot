import React from 'react'
import styled, { keyframes } from 'styled-components'

const loadingAnimation = keyframes`
  0%  {
    transform: scale(1);
  }
  50% {
    transform: scale(0.5);
  }
  100% {
    transform: scale(1);
  }
`

export const Pulser = styled.div`
  display: inline-block;
  width: 2rem;
  height: 2rem;
  border-radius: 100%;
  background: ${(props) => props.theme.accent};
  animation: 1s ease infinite ${loadingAnimation};
`

const StyledLoading = styled.div`
  display: inline-flex;
  align-items: center;
  margin: 1rem 0;
`

const LoadingText = styled.div`
  margin-left: 1rem;
  text-transform: uppercase;
  font-size: 0.8rem;
`

export default function Loading() {
  return (
    <StyledLoading>
      <Pulser />
      <LoadingText>Loading...</LoadingText>
    </StyledLoading>
  )
}
