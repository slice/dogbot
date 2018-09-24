import joi from 'joi-browser'

const users = joi
  .array()
  .items([joi.number().label('user id'), joi.string().label('discordtag')])

// configuration schema
export const schema = joi.compile(
  joi.object({
    editors: users,
    autoresponses: joi
      .object()
      .keys()
      .pattern(/.{4}/, joi.string()),
    gatekeeper: joi.object({
      enabled: joi.boolean(),
      checks: joi.object(),
      bounce_message: joi.string().min(1),
      broadcast_channel: joi.number().label('broadcast channel id'),
      allowed_users: users,
      quiet: joi.boolean()
    }),
    measure_gateway_lag: joi.boolean(),
    disabled_cogs: joi.array().items(joi.string().label('cog name')),
    publish_quotes: joi.boolean(),
    shortlinks: joi.object({
      enabled: joi.boolean(),
      whitelist: joi.array().items(joi.string().label('shortlink name')),
      blacklist: joi.array().items(joi.string().label('shortlink name'))
    })
  })
)

export function validate (doc) {
  let { error } = joi.validate(doc, schema, { convert: false })
  if (error) throw error
}
