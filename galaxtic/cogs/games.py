import discord
from discord.ext import commands
from discord import app_commands
import random


class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="_", row=x)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        if view.finished:
            await interaction.response.send_message(
                "The game is already over!", ephemeral=True
            )
            return
        if interaction.user != view.current_player:
            await interaction.response.send_message(
                "It's not your turn!", ephemeral=True
            )
            return
        if self.disabled:
            await interaction.response.send_message(
                "This spot is already taken!", ephemeral=True
            )
            return
        # Mark the button
        self.label = view.player_mark[view.current_player]
        self.style = (
            discord.ButtonStyle.success
            if self.label == "X"
            else discord.ButtonStyle.danger
        )
        self.disabled = True
        view.board[self.x][self.y] = self.label
        # Check for win/draw
        winner = view.check_winner()
        if winner:
            view.finished = True
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(
                content=f"{view.player_mention[winner]} ({view.player_mark[winner]}) wins!",
                view=view,
            )
        elif view.is_draw():
            view.finished = True
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(content="It's a draw!", view=view)
        else:
            # Switch turn
            view.current_player = view.other_player(view.current_player)
            await interaction.response.edit_message(
                content=f"{view.player_mention[view.current_player]}'s turn ({view.player_mark[view.current_player]})",
                view=view,
            )


class TicTacToeView(discord.ui.View):
    def __init__(self, player1: discord.User, player2: discord.User):
        super().__init__(timeout=300)
        self.players = [player1, player2]
        random.shuffle(self.players)
        self.player_mark = {self.players[0]: "X", self.players[1]: "O"}
        self.player_mention = {
            self.players[0]: self.players[0].mention,
            self.players[1]: self.players[1].mention,
        }
        self.current_player = self.players[0]
        self.finished = False
        self.board = [[None for _ in range(3)] for _ in range(3)]
        for x in range(3):
            for y in range(3):
                self.add_item(TicTacToeButton(x, y))

    def other_player(self, player):
        return self.players[1] if player == self.players[0] else self.players[0]

    def check_winner(self):
        # Rows, columns, diagonals
        lines = self.board + [list(col) for col in zip(*self.board)]
        lines.append([self.board[i][i] for i in range(3)])
        lines.append([self.board[i][2 - i] for i in range(3)])
        for line in lines:
            if line[0] and all(cell == line[0] for cell in line):
                for player, mark in self.player_mark.items():
                    if mark == line[0]:
                        return player
        return None

    def is_draw(self):
        return (
            all(cell for row in self.board for cell in row) and not self.check_winner()
        )


class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="tictactoe", description="Play TicTacToe against another user!"
    )
    @app_commands.describe(opponent="Mention the user you want to play against")
    async def tictactoe(self, interaction: discord.Interaction, opponent: discord.User):
        if opponent.bot:
            await interaction.response.send_message(
                "You can't play against a bot!", ephemeral=True
            )
            return
        if opponent == interaction.user:
            await interaction.response.send_message(
                "You can't play against yourself!", ephemeral=True
            )
            return
        view = TicTacToeView(interaction.user, opponent)
        p1, p2 = view.players
        await interaction.response.send_message(
            f"TicTacToe: {p1.mention} (X) vs {p2.mention} (O)\n{view.player_mention[view.current_player]}'s turn ({view.player_mark[view.current_player]})",
            view=view,
        )

    async def cog_load(self):
        from galaxtic import settings

        test_guild_id = getattr(settings.DISCORD, "TEST_GUILD_ID", None)
        test_guild = discord.Object(id=test_guild_id) if test_guild_id else None
        self.bot.tree.add_command(self.tictactoe, guild=test_guild)


async def setup(bot):
    await bot.add_cog(Games(bot))
