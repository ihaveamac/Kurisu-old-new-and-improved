#!/usr/bin/env python3
import logging
import os
from asyncio import Event
from configparser import ConfigParser
from datetime import datetime
from subprocess import check_output, CalledProcessError
from sys import argv
from sys import exit, exc_info, hexversion
from traceback import format_exception
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from k2modules.data.names import *
from k2modules.util import ActionsLogManager, ConfigurationManager, RestrictionsManager, UserLogManager, WarnsManager
from k2modules.util.database import ConnectionManager

if TYPE_CHECKING:
    from typing import Dict, Union


class Kurisu2(commands.Bot):
    """Base class for Kurisu2."""

    _guild: discord.Guild = None
    db_conn: 'ConnectionManager'

    restrictions: RestrictionsManager
    configuration: ConfigurationManager
    warns: WarnsManager
    actionslog: ActionsLogManager
    userlog: UserLogManager

    def __init__(self, command_prefix, dsn, logging_level=logging.WARNING, **options):
        super().__init__(command_prefix, **options)
        self.dsn = dsn

        self._roles: Dict[str, discord.Role] = {}
        self._channels: Dict[str, discord.TextChannel] = {}
        self._failed_extensions: Dict[str, BaseException] = {}

        self.exitcode = 0

        self._is_all_ready = Event(loop=self.loop)

        # TODO: actually use logging properly, somehow. if I can figure it out.
        # judging from https://www.python.org/dev/peps/pep-0282/ I shouldn't have to pass around a log object.
        # actually when I tried do use "logging" directly, it interfered with discord.py. so maybe I'll fix this later
        self.log = logging.getLogger('Kurisu2')
        self.log.setLevel(logging_level)

        ch = logging.StreamHandler()
        self.log.addHandler(ch)

        os.makedirs('logs', exist_ok=True)
        fh = logging.FileHandler(f'logs/kurisu2-{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log')
        self.log.addHandler(fh)

        fmt = logging.Formatter('%(asctime)s - %(name)s - %(module)s - %(levelname)s - %(message)s')
        ch.setFormatter(fmt)
        fh.setFormatter(fmt)

        self.debug = logging_level is logging.DEBUG

        self.db_closed = False

        self.log.debug('Kurisu2 class initialized')

    async def start(self, *args, **kwargs):
        self.db_conn = ConnectionManager(self.dsn)
        await self.db_conn.prepare()

        self.restrictions = RestrictionsManager(self)
        self.configuration = ConfigurationManager(self)
        await self.configuration.load()
        self.warns = WarnsManager(self)
        self.actionslog = ActionsLogManager(self)
        self.userlog = UserLogManager(self)

        self.log.debug('Kurisu2 database connection initialized')

        self.load_extensions()
        await super().start(*args, **kwargs)

    def load_extensions(self):
        blacklisted_cogs = ()
        # this is not a good way of doing things i think
        for c in ('k2modules.' + x.name[:-3] for x in os.scandir('k2modules')
                  if x.name.endswith('.py') and x.name != '__init__.py'):
            if c in blacklisted_cogs:
                self.log.info('Not automatically loading %s since it is listed in blacklisted_cogs', c)
                continue
            self.log.debug('Loading extension %s', c)
            try:
                self.load_extension(c)
            except BaseException as e:
                self.log.error('%s failed to load.', c, exc_info=e)
                self._failed_extensions[c] = e

    async def on_ready(self):
        self.log.debug('Logged in as %s', self.user)
        guilds = self.guilds
        assert len(guilds) == 1
        self._guild = guilds[0]

        for n in channel_names.values():
            self._channels[n] = discord.utils.get(self._guild.channels, name=n)
            self.log.debug('Result of searching for channel %s: %r', n, self._channels[n])

        for n in role_names.values():
            self._roles[n] = discord.utils.get(self._guild.roles, name=n)
            self.log.debug('Result of searching for role %s: %r', n, self._roles[n])

        startup_message = f'{self.user.name} has started! {self._guild} has {self._guild.member_count:,} members!'
        embed = None
        if self._failed_extensions:
            startup_message += ' <@78465448093417472>'  # mentions ihaveahax (me) if something fails
            embed = discord.Embed(title='Extensions failed to load')
            for c, e in self._failed_extensions.items():
                embed.add_field(name=c, value=f'{type(e).__module__}.{type(e).__qualname__}: {e}')

        await self._channels[channel_names[startup_message_channel]].send(startup_message, embed=embed)

        self._is_all_ready.set()

    async def get_main_guild(self) -> discord.Guild:
        if not self._is_all_ready:
            await self.wait_until_all_ready()
        return self._guild

    async def get_channel_by_name(self, name: str) -> discord.TextChannel:
        if not self._is_all_ready:
            await self.wait_until_all_ready()
        return self._channels[channel_names[name]]

    async def get_role_by_name(self, name: str) -> discord.Role:
        if not self._is_all_ready:
            await self.wait_until_all_ready()
        return self._roles[role_names[name]]

    def is_private_channel(self, channel: 'Union[discord.TextChannel, str]'):
        if isinstance(channel, discord.TextChannel):
            channel = channel.name
            try:
                channel = channel_alias_names[channel]
            except KeyError:
                return False
        return channel in private_channels

    async def on_command_error(self, ctx: commands.Context, exc: commands.CommandInvokeError):
        author: discord.Member = ctx.author
        command: commands.Command = ctx.command or '<unknown cmd>'

        try:
            original = exc.original
        except AttributeError:
            # just in case it's not CommandInvokeError for whatever reason
            original = exc

        if isinstance(exc, commands.CommandNotFound):
            return

        elif isinstance(exc, commands.NoPrivateMessage):
            await ctx.send(f'`{command}` cannot be used in direct messages.')

        elif isinstance(exc, commands.MissingPermissions):
            await ctx.send(f"{author.mention} You don't have permission to use `{command}`.")

        elif isinstance(exc, commands.CheckFailure):
            await ctx.send(f'{author.mention} You cannot use `{command}`.')

        elif isinstance(exc, commands.BadArgument):
            formatter = commands.DefaultHelpCommand()
            await formatter.prepare_help_command(ctx, command)
            formatter.add_command_formatting(command)
            formatter.paginator.close_page()
            help_text = formatter.paginator.pages[0]
            await ctx.send(f'{author.mention} A bad argument was given: `{exc}`\n{help_text}')

        elif isinstance(exc, commands.MissingRequiredArgument):
            formatter = commands.DefaultHelpCommand()
            await formatter.prepare_help_command(ctx, command)
            formatter.add_command_formatting(command)
            formatter.paginator.close_page()
            help_text = formatter.paginator.pages[0]
            await ctx.send(f'{author.mention} You are missing required arguments.\n{help_text}')

        elif isinstance(exc, commands.CommandInvokeError):
            self.log.debug('Exception in %s: %s: %s', command, type(exc).__name__, exc, exc_info=original)
            await ctx.send(f'{author.mention} `{command}` raised an exception during usage')
            if self.debug:
                await ctx.send(f'```\n{"".join(format_exception(type(exc), exc, exc.__traceback__))}\n```')

        else:
            self.log.debug('Unexpected exception in %s: %s: %s', command, type(exc).__name__, exc, exc_info=original)
            if not isinstance(command, str):
                command.reset_cooldown(ctx)
            await ctx.send(f'{author.mention} Unexpected exception occurred while using the command `{command}`')
            if self.debug:
                await ctx.send(f'```\n{"".join(format_exception(type(exc), exc, exc.__traceback__))}\n```')

    async def on_error(self, event_method, *args, **kwargs):
        self.log.error('Exception occurred in %s', event_method, exc_info=exc_info())

    def add_cog(self, cog):
        super().add_cog(cog)
        self.log.debug('Initialized %s.%s', type(cog).__module__, type(cog).__name__)

    async def close(self):
        self.log.info('Kurisu is shutting down')
        self.dbcon.close()
        self.db_closed = True
        await super().close()

    async def is_all_ready(self):
        """Checks if the bot is finished setting up."""
        return self._is_all_ready.is_set()

    async def wait_until_all_ready(self):
        """Wait until the bot is finished setting up."""
        await self._is_all_ready.wait()


def main(*, debug=False, change_directory=False):
    """Main script to run the bot."""
    if discord.version_info.major < 1:
        print(f'discord.py is not at least 1.0.0x. (current version: {discord.__version__})')
        return 2

    if not hexversion >= 0x030702F0:  # 3.7.2
        print('Kurisu2 requires 3.7.2 or later.')
        return 2

    if change_directory:
        # set current directory to the bot location
        dir_path = os.path.dirname(os.path.realpath(__file__))
        os.chdir(dir_path)

    # attempt to get current git information
    try:
        commit = check_output(['git', 'rev-parse', 'HEAD']).decode('ascii')[:-1]
    except CalledProcessError as e:
        print(f'Checking for git commit failed: {type(e).__name__}: {e}')
        commit = "<unknown>"

    try:
        branch = check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode()[:-1]
    except CalledProcessError as e:
        print(f'Checking for git branch failed: {type(e).__name__}: {e}')
        branch = "<unknown>"

    config = ConfigParser()
    config.read('config.ini')
    token: str = config['Main']['token']
    dsn: str = config['Database']['dsn']

    # do not remove a command prefix unless it is demonstrably causing problems
    bot = Kurisu2(('.', '!'), dsn, logging_level=logging.DEBUG if debug else logging.INFO,
                  description="Kurisu2, the bot for Nintendo Homebrew!", pm_help=None)

    bot.log.info('Starting Kurisu2 on commit %s on branch %s', commit, branch)

    bot.log.debug('Running bot')
    # noinspection PyBroadException

    try:
        bot.run(token)
    except Exception as e:
        # this should ideally never happen
        bot.log.critical('Kurisu2 shut down due to a critical error.', exc_info=e)

    return bot.exitcode


if __name__ == '__main__':
    exit(main(debug='d' in argv, change_directory=True))
