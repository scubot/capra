import asyncio
import json
import re
from io import BytesIO
from typing import Dict

import discord
from discord.ext import commands
from discord.ext.commands import Bot
from tinydb import TinyDB, Query


class Capra(commands.Cog):

    def __init__(self, bot):
        self.version = "2.0.0"
        self.bot: Bot = bot
        self.db: TinyDB = TinyDB('./modules/databases/capra')
        self.executable_path = "modules/capra/capra-singleplanner"
        self.disclaimer_path = "modules/capra/disclaimer.txt"

    async def run_dive_planner(self, json_input: str):
        b_json_input = str.encode(json_input)
        proc = await asyncio.create_subprocess_shell(
            self.executable_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        stdout = "".encode()
        stderr = "".encode()
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(input=b_json_input), timeout=15)
        except asyncio.TimeoutError:
            stderr = str.encode("Timed out.")
        finally:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
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
    def generate_json(gfl: int, gfh: int, asc: int, desc: int, bottom_sac: int, deco_sac: int, user_input: str) -> str:
        segments = []
        deco_gases = []
        data = re.findall(r"(D:\d+, \d+, \d+/\d+)+[ ]*(G:.+)*", user_input)
        for section in data:
            if section[1] != '':  # Deco
                deco_match = re.findall(r"(G:)*(.+?)(?:,\s*|$)", section[1])
                for gas_string in deco_match:
                    gas = gas_string[1].split('/')
                    deco_gases.append({
                        "o2": int(gas[0]) / 100,
                        "he": int(gas[1]) / 100
                    })
            if section[0] != '':  # Dive segment
                depth, time, mix = re.findall(r"D:(\d+), (\d+), (\d+/\d+)", section[0])[0]
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
                           'bottom_sac': bottom_sac, 'deco_sac': deco_sac, 'deco_gases': deco_gases})

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
                                         profile['bottom_sac'], profile['deco_sac'], dive_plan)

        stdout, stderr = await self.run_dive_planner(json_string)

        stdout = stdout.decode()
        stderr = stderr.decode()

        if len(stderr) != 0:
            return_string = f'[!] An error occurred inside the dive planner. \n' \
                            f'```{stderr}```'
            await ctx.send(return_string)
        else:
            if len(stdout) > 1000:
                return_string = f'Powered by Capra: https://github.com/the-emerald/capra\n' \
                                f'WARNING: DIVE PLAN MAY BE INACCURATE AND MAY CONTAIN ERRORS THAT COULD LEAD ' \
                                f'TO INJURY OR DEATH.\n\n' \
                                f'{stdout}'
                await ctx.send(content=f"{ctx.author.mention}", file=discord.File(BytesIO(return_string.encode()),
                                                                                  filename="plan.txt"))

            else:
                return_string = f'{ctx.author.mention}\n' \
                                f'Powered by Capra 🐐 \n' \
                                f'**Warning: Dive plan may be inaccurate and may contain errors that could lead ' \
                                f'to injury or death.**\n\n' \
                                f'```{stdout}```'
                await ctx.send(return_string)

    @plan.command(name="set")
    async def setprofile(self, ctx, ascent_rate: int, descent_rate: int, gf_low: int, gf_high: int, bottom_sac: int,
                         deco_sac: int):  # Set a profile
        if not self.check_disclaimer(ctx.message.author.id):
            await ctx.send("[!] You have not read and agreed to the disclaimer. Use help command for more information.")
            return
        table = self.db.table('profile')
        target = Query()
        table.upsert(
            {'userid': ctx.message.author.id, 'asc': ascent_rate, 'desc': descent_rate, 'gfl': gf_low, 'gfh': gf_high,
             'bottom_sac': bottom_sac, 'deco_sac': deco_sac},
            target.userid == ctx.message.author.id
        )
        await ctx.send("[:ok_hand:] User profile updated.")

    @plan.command(name="disclaimer")
    async def disclaimer(self, ctx):  # Show and read disclaimer
        try:
            f = open(self.disclaimer_path, mode='r')
        except FileNotFoundError:
            await ctx.send("[!] Disclaimer file not found. Please complain to a dev about this.")
            return

        disclaimer_text = f.read()
        f.close()

        disclaimer_message = await ctx.author.send(disclaimer_text)

        def check(reaction, user):
            return user == ctx.message.author and str(reaction.emoji) == '👌' \
                   and reaction.message.id == disclaimer_message.id

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
            await ctx.author.send("[:ok_hand:] You have accepted the disclaimer, and can now use the dive planner.")


def setup(bot):
    bot.add_cog(Capra(bot))
