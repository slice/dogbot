from dog.ext.gatekeeper.cog import Gatekeeper


def setup(bot):
    bot.add_cog(Gatekeeper(bot))
