import nextcord.ui


class PlayerView(nextcord.ui.View):
    def __init__(self, musicplayer):
        super().__init__()
        self.musicplayer = musicplayer

    @nextcord.ui.button(label='Play', style=nextcord.ButtonStyle.green)
    async def play(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await self.musicplayer.subcommands['play'](interaction.message)
        embed = await self.musicplayer.get_infocard(interaction.message)
        await interaction.response.edit_message(embed=embed,view=self)

    @nextcord.ui.button(label='Pause', style=nextcord.ButtonStyle.red)
    async def pause(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await self.musicplayer.subcommands['pause'](interaction.message)
        embed = await self.musicplayer.get_infocard(interaction.message)
        await interaction.response.edit_message(embed=embed, view=self)

    @nextcord.ui.button(label='Next', style=nextcord.ButtonStyle.grey)
    async def next(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await self.musicplayer.subcommands['next'](interaction.message)
        embed = await self.musicplayer.get_infocard(interaction.message)
        await interaction.response.edit_message(embed=embed, view=self)