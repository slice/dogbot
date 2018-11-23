export interface User {
  avatar: string
  discriminator: string
  id: string
  locale: string
  mfa_enabled: boolean
  username: string
}

export interface Guild {
  icon_url: string
  id: string
  members: number
  name: string
  owner: { id: string; tag: string }
}
