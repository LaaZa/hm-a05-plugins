import nextcord

from modules.globals import Globals

from modules.pluginbase import PluginBase


class Plugin(PluginBase):
    # plugin specific

    def __init__(self):
        super().__init__()
        self.type = PluginBase.PluginType.UNCORE
        self.name = 'test'
        self.add_trigger('on_message', 'test', True, self.test)
        self.add_application_command(self.slashtest, name='testslash', guild_ids=Globals.pluginloader.get_slash_servers(__name__))
        self.add_application_command(self.slashtest2, guild_ids=Globals.pluginloader.get_slash_servers(__name__))
        self.add_application_command(self.usertest, cmd_type=nextcord.ApplicationCommandType.user, name='Mitäs vittua?', guild_ids=Globals.pluginloader.get_slash_servers(__name__))
        self.help = 'test'

    async def slashtest(self, interaction):
        await interaction.response.send_message("TEST!!!!")

    async def slashtest2(self, interaction):
        await interaction.response.send_message("TEST2!!!!")

    async def usertest(self, interaction, member):
        await interaction.response.defer(ephemeral=True)
        await member.send('No mitäs vittua, sehän toimii')

    async def test(self, message, trigger):
        pass
