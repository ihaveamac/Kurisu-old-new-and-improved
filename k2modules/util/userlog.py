from typing import TYPE_CHECKING

from discord import Member, User

from .managerbase import BaseManager

if TYPE_CHECKING:
    from typing import Union
    from k2modules.util import OptionalMember

action_messages = {
    'warn': ('\N{WARNING SIGN}', 'Warn', 'warned', {'moderator-logs'}),
    'ban': ('\N{NO ENTRY}', 'Ban', 'banned', {'moderator-logs'}),
    'kick': ('\N{WOMANS BOOTS}', 'Kick', 'kicked', {'moderator-logs'}),
    # specific role changes
    'mute': ('\N{SPEAKER WITH CANCELLATION STROKE}', 'Mute', 'muted', {'moderator-logs'}),
    'unmute': ('\N{SPEAKER}', 'Unmute', 'unmuted', {'moderator-logs'}),
    'take-help': ('\N{NO ENTRY SIGN}', 'Help access taken', 'took help access from', {'moderator-logs', 'helpers'}),
    'give-help': ('\N{HEAVY LARGE CIRCLE}', 'Help access restored', 'restored help access for', {'moderator-logs', 'helpers'}),
    # non-specific role changes
    'add-perm-role': ('\N{BLACK QUESTION MARK ORNAMENT}', 'Add role', 'added a permanent role to', {'moderator-logs'}),
    'add-temp-role': ('\N{BLACK QUESTION MARK ORNAMENT}', 'Add role', 'added a temporary role to', {'moderator-logs'}),
    'remove-role': ('\N{BLACK QUESTION MARK ORNAMENT}', 'Remove role', 'removed a role from', {'moderator-logs'}),
    'test': ('\N{BLACK QUESTION MARK ORNAMENT}', 'Test action', 'performed a test action on', {'helpers'})
}

actions_extra = {
}

general_messages = {
    'member_update': 'Member Update',
}


class UserLogManager(BaseManager):
    """Manages posting logs."""

    async def post_action_log(self, author: 'Union[Member, User, OptionalMember]',
                              target: 'Union[Member, User, OptionalMember]', kind: str, reason: str = None,
                              action_id: int = None):
        member = target if isinstance(target, (Member, User)) else target.member
        msg_meta = action_messages[kind]
        msg = [f'{msg_meta[0]} **{msg_meta[1]}**: <@!{author.id}> {msg_meta[2]} <@!{target.id}>']
        if member:
            msg[0] += ' | ' + str(member)
        if reason:
            msg.append(f'\N{PENCIL} __Reason__: {reason}')
        else:
            msg.append('\N{PENCIL} ___No reason provided__')
        if action_id:
            msg.append(f'\N{HAMMER} __Action ID__: {action_id}')
        msg_final = '\n'.join(msg)
        for m in msg_meta[3]:
            channel = await self.bot.get_channel_by_name(m)
            await channel.send(msg_final)
