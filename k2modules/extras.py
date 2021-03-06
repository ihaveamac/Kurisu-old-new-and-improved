from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from .util import Extension

if TYPE_CHECKING:
    from kurisu2 import Kurisu2  # for type hinting


class Extras(Extension):
    """Extra commands and features."""

    @commands.command(name='kurisu', aliases=('kurisu2', 'about'))
    async def about_kurisu(self, ctx: commands.Context):
        """About Kurisu."""
        embed = discord.Embed(title='Kurisu2', color=discord.Color.green(), url='https://github.com/nh-server/Kurisu',
                              description='Kurisu2, the Nintendo Homebrew server bot!')
        embed.set_author(name='ihaveahax and 916253')
        embed.set_thumbnail(url='http://i.imgur.com/hjVY4Et.jpg')
        await ctx.send(embed=embed)

    @commands.command(name='membercount')
    async def member_count(self, ctx: commands.Context):
        """Posts the server member count."""
        guild = await self.bot.get_main_guild()
        await ctx.send(f'{guild} has {guild.member_count:,} members!')

    # TODO: make this owner-only
    @commands.command()
    async def quit(self, ctx: commands.Context):
        """Shuts down the bot."""
        self.log.info('Shutdown initiated by %s in #%s', ctx.author, ctx.channel)
        await ctx.send('\N{WAVING HAND SIGN} Goodbye!')
        await self.bot.close()


def setup(bot: 'Kurisu2'):
    bot.add_cog(Extras(bot))
