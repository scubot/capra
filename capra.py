from wasmer import Instance
from discord.ext import commands


class Capra(commands.Cog):
    def __init__(self, bot, wasm):
        self.version = "0.1.0"
        self.bot = bot
        self.wasm = wasm

    @commands.command()
    async def ndl(self, ctx, depth: int, time: int = 0, gf: int = 100):
        ndl = f'{self.wasm.exports.no_deco_limit(depth, time, gf)} min'
        if ndl == 0:
            ndl = "Decompression reached"
        elif ndl == -1:  # usize::MAX
            ndl = "Unlimited"
        await ctx.send(f"NDL: {ndl}")


def setup(bot):
    wasm_location = './modules/capra/capra.wasm'
    wasm = Instance(open(wasm_location, 'rb').read())
    bot.add_cog(Capra(bot, wasm))
