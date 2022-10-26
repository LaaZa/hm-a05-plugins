import nextcord.ui


class PlayerView(nextcord.ui.View):
    def __init__(self, musicplayer):
        super().__init__()
        self.musicplayer = musicplayer

    @nextcord.ui.button(label='▶', style=nextcord.ButtonStyle.primary)
    async def play(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        if self.musicplayer.has_permission(interaction, 'play', True):
            await self.musicplayer.subcommands['play'](interaction.message)
            await interaction.response.edit_message(content=f'[{interaction.user.name} pressed play]', view=self)
        else:
            await interaction.response.send_message('You don\'t have permissions for that!', ephemeral=True)

    @nextcord.ui.button(label='❚❚', style=nextcord.ButtonStyle.primary)
    async def pause(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        if self.musicplayer.has_permission(interaction, 'pause', True):
            await self.musicplayer.subcommands['pause'](interaction.message)
            await interaction.response.edit_message(content=f'[{interaction.user.name} paused]', view=self)
        else:
            await interaction.response.send_message('You don\'t have permissions for that!', ephemeral=True)

    @nextcord.ui.button(label='🞂🞂❙', style=nextcord.ButtonStyle.primary)
    async def next(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        if self.musicplayer.has_permission(interaction, 'next', True):
            await self.musicplayer.subcommands['next'](interaction.message)
            await interaction.response.edit_message(content=f'[{interaction.user.name} skipped]', view=self)
        else:
            await interaction.response.send_message('You don\'t have permissions for that!', ephemeral=True)
