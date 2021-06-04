import configparser
import discord
from discord.ext import commands
from enum import Enum
import os
import random
from src.DB import DB

description = "Manage raffles in Discord!"
intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!raffle ", description=description, intents=intents)

config = configparser.ConfigParser()
config.read(os.environ.get("CONFIG_PATH"))


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.channel.send(str(error), delete_after=5)
    await ctx.message.delete(delay=5)


class RaffleType(Enum):
    # Normal Raffle type. Most recent 5 winners are not eligible to win
    Normal = "normal"
    # No restrictions. Anyone can win. But win is still recorded.
    Anyone = "anyone"
    # Only people who have never won a raffle are eligible
    New = "new"


@bot.command()
@commands.guild_only()
@commands.has_role("raffler")
async def start(ctx: commands.Context):
    """Creates a brand new raffle"""
    if DB.get().has_ongoing_raffle(ctx.guild.id):
        raise Exception("There is already an ongoing raffle!")

    raffle_message = await ctx.send(
        "Raffle time! React to this message to enter. The winner(s) will be randomly chosen."
    )

    DB.get().create_raffle(ctx.guild.id, raffle_message.id)


@bot.command()
@commands.guild_only()
@commands.has_role("raffler")
async def end(
    ctx: commands.Context,
    raffle_type: str = "normal",
    num_winners: int = 1,
):
    """Closes an existing raffle and pick the winner(s)"""
    if not DB.get().has_ongoing_raffle(ctx.guild.id):
        raise Exception("There is no ongoing raffle! You need to start a new one.")

    num_winners = int(num_winners)
    if num_winners < 1:
        raise Exception("The number of winners must be at least 1.")

    raffle_message_id = DB.get().get_raffle_message_id(ctx.guild.id)
    if raffle_message_id is None:
        raise Exception("Oops! That raffle does not exist anymore.")

    await _end_raffle_impl(ctx, raffle_message_id, raffle_type, num_winners)
    DB.get().close_raffle(ctx.guild.id)


@bot.command()
@commands.guild_only()
@commands.has_role("raffler")
async def redo(
    ctx: commands.Context,
    raffle_type: str = "normal",
    num_winners: int = 1,
):
    """
    Picks new winner(s) from a past raffle.
    Make sure to reply to the original raffle message when invoking this command.
    """
    original_raffle = ctx.message.reference
    if original_raffle is None:
        raise Exception(
            "You must invoke this by replying to the original raffle message."
        )

    original_raffle_id = original_raffle.message_id
    if original_raffle_id is None:
        raise Exception("Could not find the referenced raffle.")

    num_winners = int(num_winners)
    if num_winners < 1:
        raise Exception("The number of winners must be at least 1.")

    raffle_message = await ctx.fetch_message(original_raffle_id)
    if raffle_message is None:
        raise Exception("Oops! That raffle does not exist anymore.")

    # We need to reset the past winners if we're re-doing a raffle draw
    # otherwise it'd be unfairly counted against them
    DB.get().clear_wins(ctx.guild.id, raffle_message.id)

    await _end_raffle_impl(ctx, raffle_message.id, raffle_type, num_winners)


async def _end_raffle_impl(
    ctx: commands.Context,
    raffle_message_id: int,
    raffle_type: str,
    num_winners: int,
):
    raffle_message = await ctx.fetch_message(raffle_message_id)
    if raffle_message is None:
        raise Exception("Oops! That raffle does not exist anymore.")

    # We annotate the raffle_type param above as `str` for a more-clear error message
    # This way it says it doesn't recognize the raffle type rather than fail param type conversion
    raffle_type = RaffleType(raffle_type)

    if raffle_type == RaffleType.Normal:
        ineligible_winner_ids = DB.get().recent_winners(ctx.guild.id)
    elif raffle_type == RaffleType.Anyone:
        ineligible_winner_ids = []
    elif raffle_type == RaffleType.New:
        ineligible_winner_ids = DB.get().all_winners(ctx.guild.id)
    else:
        raise Exception("Unimplemented raffle type")

    entrants = []
    for reaction in raffle_message.reactions:
        users = await reaction.users().flatten()
        for user in users:
            if user not in entrants and user.id not in ineligible_winner_ids:
                entrants.append(user)

    if len(entrants) > 0:
        winners = _choose_winners(entrants, num_winners)
        DB.get().record_win(ctx.guild.id, raffle_message_id, *winners)
        if len(winners) == 1:
            await ctx.send("{} has won the raffle!".format(winners[0].mention))
        else:
            await ctx.send(
                "Raffle winners are: {}!".format(
                    ", ".join(map(lambda winner: winner.mention, winners))
                )
            )
    else:
        await ctx.send("No one eligible entered the raffle so there is no winner.")


def _choose_winners(entrants, num_winners):
    if len(entrants) < num_winners:
        raise Exception("There are not enough entrants for that many winners.")

    winners = []
    while num_winners > 0:
        winner = random.choice(entrants)
        winners.append(winner)
        entrants.remove(winner)
        num_winners -= 1

    return winners


bot.run(config["Discord"]["Token"])
