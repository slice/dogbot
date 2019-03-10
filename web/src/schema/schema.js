import { string, object, number, bool, array, lazy, setLocale } from 'yup'

// set a better message for when objects have unknown keys
setLocale({
  object: {
    // eslint-disable-next-line
    noUnknown: '${path} cannot have unknown keys',
  },
})

const defs = {
  // a discord id (snowflake)
  id: number().min(1),

  // a basic gatekeeper check
  check: object({
    enabled: bool().required(),
  }).noUnknown(),

  // user-specified thresholds
  threshold: string().matches(
    /\d+\/\d+/,
    '${path} is not a valid threshold (rate/per)' // eslint-disable-line
  ),

  // a user id or discord tag
  user: lazy((value) =>
    typeof value === 'string'
      ? string().matches(/^.+#\d{4}$/, '${path} is not a valid Discord tag') // eslint-disable-line
      : defs.id.label('user ID')
  ),

  // a shortlink name
  shortlinks: ['mastodon', 'pep', 'keybase', 'osu'],
}

defs.checks = object({
  block_default_avatars: defs.check,
  block_bots: defs.check,
  block_all: defs.check,
  minimum_creation_time: defs.check.shape({
    minimum_age: number()
      .min(0)
      .required(),
  }),
  username_regex: defs.check.shape({
    regex: string()
      .min(0)
      .required(),
    case_sensitive: bool(),
  }),
}).noUnknown()

export default object({
  editors: array(defs.user),
  gatekeeper: object({
    enabled: bool(),
    ban_threshold: defs.threshold,
    bannable_checks: defs.checks,
    checks: defs.checks,
    auto_lockdown: object({
      threshold: defs.threshold,
    }).noUnknown(),
    bounce_message: string(),
    allowed_users: array(defs.user),
    broadcast_channel: defs.id,
    quiet: bool(),
    echo_dm_failures: bool(),
  }).noUnknown(),
  measure_gateway_lag: bool(),
  disabled_cogs: array(
    string().oneOf([
      'Currency',
      'Gatekeeper',
      'Health',
      'Info',
      'Mod',
      'Profile',
      'Quoting',
      'Time',
      'Utility',
    ])
  ),
  publish_quotes: bool(),
  shortlinks: object({
    enabled: bool().required(),
    whitelist: array(string().oneOf(defs.shortlinks)),
    blacklist: array(string().oneOf(defs.shortlinks)),
  }).noUnknown(),
}).noUnknown()
