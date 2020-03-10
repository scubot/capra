import asyncio
import json
import re
from asyncio.subprocess import PIPE
from typing import Dict
from subprocess import STDOUT, check_output

from discord.ext import commands
from discord.ext.commands import Bot
from tinydb import TinyDB, Query


class Capra(commands.Cog):

    def __init__(self, bot):
        self.version = "0.1.0"
        self.bot: Bot = bot
        self.db: TinyDB = TinyDB('./modules/databases/capra')
        # ---

    @staticmethod
    async def run_dive_planner(json_input: str):  # (stdin, stdout)
        path = "/home/emerald/scubot/modules/capra/capra-singleplanner"
        b_json_input = str.encode(json_input)
        proc = await asyncio.create_subprocess_shell(
            path,
            stdin=PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

        # await proc.communicate(input=b_json_input)
        stdout = "".encode()
        stderr = "".encode()
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(input=b_json_input), timeout=15)
        except asyncio.TimeoutError:
            stderr = str.encode("Timed out.")
        return stdout, stderr

    def check_disclaimer(self, userid: int) -> bool:
        table = self.db.table('disclaimer')
        target_user = Query()
        return bool(table.get(target_user.userid == userid))

    def check_user_profile(self, userid: int) -> Dict:
        table = self.db.table('profile')
        target = Query()
        return table.get(target.userid == userid)

    @staticmethod
    def generate_json(gfl: int, gfh: int, asc: int, desc: int, user_input: str) -> str:
        segments = []
        deco_gases = []
        data = re.findall(r"(D:[\d]+, [\d]+, [\d]+/[\d]+)+[ ]*(G:.+)*", user_input)
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
        if not self.check_disclaimer(ctx.message.author.id):
            await ctx.send("[!] You have not read and agreed to the disclaimer. Use help command for more information.")
            return
        profile = self.check_user_profile(ctx.message.author.id)
        if not profile:
            await ctx.send("[!] Set a dive profile before planning a dive!")
            return

        json_string = self.generate_json(profile["gfl"], profile["gfh"], profile["asc"], profile["desc"],
                                         dive_plan)

        stdout, stderr = await self.run_dive_planner(json_string)

        stdout = stdout.decode()
        stderr = stderr.decode()

        if len(stderr) != 0:
            return_string = f'[!] An error occurred inside the dive planner. \n' \
                            f'```{stderr}```'
            await ctx.send(return_string)
        else:
            if len(stdout) > 1000:
                await ctx.send("way too long bro")  # TODO: Replace with file uploading
            else:
                return_string = f'Powered by Capra 🐐 \n' \
                                f'**Warning: Dive plan may be inaccurate and may contain errors that could lead ' \
                                f'to injury or death.**\n\n' \
                                f'{stdout}'
                await ctx.send(return_string)

    @plan.command(name="set")
    async def setprofile(self, ctx, ascent_rate: int, descent_rate: int, gf_low: int, gf_high: int):  # Set a profile
        if not self.check_disclaimer(ctx.message.author.id):
            await ctx.send("[!] You have not read and agreed to the disclaimer. Use help command for more information.")
        table = self.db.table('profile')
        target = Query()
        table.upsert(
            {'userid': ctx.message.author.id, 'asc': ascent_rate, 'desc': descent_rate, 'gfl': gf_low, 'gfh': gf_high},
            target.userid == ctx.message.author.id
        )
        await ctx.send("[:ok_hand:] User profile updated.")

    @plan.command(name="disclaim")
    async def disclaimer(self, ctx):  # Show and read disclaimer
        try:
            f = open('/home/emerald/scubot/modules/capra/disclaimer.txt', mode='r')
        except FileNotFoundError:
            await ctx.send("[!] Disclaimer file not found. Please complain to a dev about this.")
            return

        disclaimer_text = f.read()
        f.close()

        def check(reaction, user):
            return user == ctx.message.author and str(reaction.emoji) == '👍'

        await ctx.send(disclaimer_text)
        try:
            await self.bot.wait_for('reaction_add', timeout=60, check=check)
        except asyncio.TimeoutError:
            return  # Received nothing. Time out
        else:
            table = self.db.table('disclaimer')
            target = Query()
            table.upsert({
                'userid': ctx.message.author.id
            }, target.userid == ctx.message.author.id)
            await ctx.send("[:ok_hand:] You have accepted the disclaimer, and can now use the dive planner.")


def setup(bot):
    bot.add_cog(Capra(bot))
