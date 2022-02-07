import sys

import nextcord

from modules.globals import Globals
from modules.pluginbase import PluginBase


class Plugin(PluginBase):
    # plugin specific

    def __init__(self):
        super().__init__()
        self.type = PluginBase.PluginType.UNCORE
        self.name = 'foobar'
        self.add_trigger('on_message', 'be', True, self.on_message)
       self.add_trigger('on_member_join', lambda member, **kwargs: True, False, self.on_member_join)
        self.help = 'just a test'

        self.expressions = {
            'shocked': 'expression_shock.png',
            'disoriented': 'expression_disoriented_anim.gif',
            'annoyed': 'expression_annoyed.png',
        }

    async def on_message(self, message, trigger):
        msg = self.Command(message)
        Globals.permissions.has_discord_permissions(message.author, ('manage_channels',), message.channel)
        if len(msg.parts) <= 1:
            return False
        expression = self.expressions.get(msg.parts[1], '')
        if expression:
            await Globals.disco.send(message.channel, nextcord.File(sys.path[0] + '/static/' + expression))
            return True
        else:
            return False

    async def on_member_join(self, member, trigger):
        await member.guild.default_channel.send(f'**Hello {member.name}-san!**')
        return True

    @Globals.disco.slash_command(
        name="test",
        description="test slash",
        guild_ids=[257256307000606731],
    )
    async def example2_command(interaction: nextcord.Interaction, arg1, arg2: int):
        # This command is a bit more complex, lets break it down:
        # 1: name= in the decorator sets the user-facing name of the command.
        # 2: description= sets the description that users will see for this command.
        # 3: arg1 was added, defaults to a string response.
        # 4: arg2 was added and typed as an int, meaning that users will only be able to give ints.
        await interaction.response.send_message(
            f"slash command, arg1: {arg1}, arg2: {arg2}"
        )