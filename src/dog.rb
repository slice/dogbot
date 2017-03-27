require 'discordrb'

# good config loading code /s
config = JSON.parse(File.read('config.json'))

bot = Discordrb::Bot.new token: config['token'], client_id: config['client_id']

bot.run
