import joi from 'joi-browser'

// configuration schema
export const schema = joi.compile(
  joi.object({
    editors: joi.array().items([joi.number().label('user id'), joi.string().label('discordtag')]),
    autoresponses: joi.object().keys().pattern(/.{4}/, joi.string()),
    gatekeeper: joi.object({
      enabled: joi.boolean(),
      checks: joi.object(),
      bounce_message: joi.string().min(1),
      broadcast_channel: joi.number().label('broadcast channel id')
    }),
    measure_gateway_lag: joi.boolean(),
    disabled_cogs: joi.array().items(joi.string().label('cog name'))
  })
)

export function validate (doc) {
  let { error } = joi.validate(doc, schema, { convert: false })
  if (error) throw error
}
