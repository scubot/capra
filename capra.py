import asyncio
import json
import re

from discord.ext import commands
from discord.ext.commands import Bot
from tinydb import TinyDB, Query


class Capra(commands.Cog):

    def __init__(self, bot):
        self.version = "0.1.0"
        self.bot: Bot = bot
        self.db: TinyDB = TinyDB('./modules/databases/capra')
        # ---

    def check_disclaimer(self, userid: int) -> bool:
        table = self.db.table('disclaimer')
        target_user = Query()
        return bool(table.get(target_user.userid == userid))

    def check_user_profile(self, userid: int) -> bool:
        pass

    @staticmethod
    def generate_json(gfl: int, gfh: int, asc: int, desc: int, user_input: str) -> str:
        segments = []
        deco_gases = []
        data = re.findall(r"(D:[\d]+, [\d]+, [\d]+/[\d]+)* |(G:.+)", user_input)
        for section in data:
            if section[0] == '':  # Deco
                deco_match = re.findall(r"(G:)*(.+?)(?:,\s*|$)", section[1])
                for gas_string in deco_match:
                    gas = gas_string[1].split('/')
                    deco_gases.append({
                        "o2": int(gas[0]) / 100,
                        "he": int(gas[1]) / 100
                    })
            else:  # Dive segment
                depth, time, mix = re.findall(r"D:([\d]+), ([\d]+), ([\d]+/[\d]+)", section[0])[0]
                mix = mix.split('/')
                segments.append(
                    {
                        "depth": int(depth),
                        "time": int(time),
                        "o2": int(mix[0]) / 100,
                        "he": int(mix[1]) / 100
                    }
                )

        return json.dumps({'gfl': gfl, 'gfh': gfh, 'asc': asc, 'desc': desc, 'segments': segments,
                           'deco_gases': deco_gases})

    @commands.group(invoke_without_command=True)
    async def plan(self, ctx, *, dive_plan: str):  # Plan a dive
        if not self.check_disclaimer(ctx.author.id):
            await ctx.send("[!] You have not read and agreed to the disclaimer. Use help command for more information.")
            return
        if not self.check_user_profile(ctx.author.id):
            await ctx.send("[!] Set a dive profile before planning a dive!")
            return
        json_string = self.generate_json(0, 0, 0, 0, dive_plan)  # TODO: Fetch GFL/H/ and Asc/Desc rates from DB
        # TODO: Send to executable
        # TODO: Receive output as stdin
        # TODO: Return output or upload as file

    @plan.command(name='reset')
    async def reset(self):
        pass

    @plan.command(name="set")
    async def setprofile(self, ctx, ascent_rate: int, descent_rate: int, gf_low: int, gf_high: int):  # Set a profile
        if not self.check_disclaimer(ctx.author):
            await ctx.send("[!] You have not read and agreed to the disclaimer. Use help command for more information.")
        table = self.db.table('profile')
        target = Query()
        table.upsert(
            {'userid': ctx.author.id, 'asc': ascent_rate, 'desc': descent_rate, 'gfl': gf_low, 'gfh': gf_high},
            target.userid == ctx.author.id
        )
        await ctx.send("[:ok_hand:] User profile updated.")

    @plan.command(name="disclaim")
    async def disclaimer(self, ctx):  # Show and read disclaimer
        try:
            f = open('disclaimer.txt', mode='r')
        except FileNotFoundError:
            await ctx.send("[!] Disclaimer file not found. Please complain to a dev about this.")
            return

        disclaimer_text = f.read()
        f.close()

        def check(reaction, user):
            return user == ctx.message.author and str(reaction.emoji) == '👍'

        await ctx.send(disclaimer_text)
        try:
            await self.bot.wait_for('reaction-add', timeout=60, check=check)
        except asyncio.TimeoutError:
            return  # Received nothing. Time out
        else:
            await ctx.send("[:ok_hand:] You have accepted the disclaimer, and can now use the dive planner.")
            # TODO: Add TinyDB update


def setup(bot):
    bot.add_cog(Capra(bot))
