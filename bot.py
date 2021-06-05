from __future__ import annotations
import configparser
import discord
from discord.ext import commands
from enum import Enum
import numpy
import os
import random
from src.DB import DB

description = "Manage raffles in Discord!"
intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!raffle ", description=description, intents=intents)

config = configparser.ConfigParser()
config.read(str(os.environ.get("CONFIG_PATH")))


@bot.event
async def on_command_error(ctx, error) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.channel.send(str(error), delete_after=5)
    await ctx.message.delete(delay=5)


class RaffleType(Enum):
    # Normal Raffle type. Most recent 6 winners are not eligible to win
    Normal = "normal"
    # No restrictions. Anyone can win. But win is still recorded.
    Anyone = "anyone"
    # Only people who have never won a raffle are eligible
    New = "new"


class SelectionType(Enum):
    # Default Raffle type. Lower odds of winning the more times you've won before
    Weighted = "weighted"
    # Completely random selection regardless of past wins
    Unweighted = "unweighted"


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
    selection_type: str = "weighted",
) -> None:
    """Closes an existing raffle and pick the winner(s)"""
    if not DB.get().has_ongoing_raffle(ctx.guild.id):
        raise Exception("There is no ongoing raffle! You need to start a new one.")

    num_winners = int(num_winners)
    if num_winners < 1:
        raise Exception("The number of winners must be at least 1.")

    raffle_message_id = DB.get().get_raffle_message_id(ctx.guild.id)
    if raffle_message_id is None:
        raise Exception("Oops! That raffle does not exist anymore.")

    await _end_raffle_impl(
        ctx, raffle_message_id, raffle_type, num_winners, selection_type
    )
    DB.get().close_raffle(ctx.guild.id)


@bot.command()
@commands.guild_only()
@commands.has_role("raffler")
async def redo(
    ctx: commands.Context,
    raffle_type: str = "normal",
    num_winners: int = 1,
    selection_type: str = "weighted",
) -> None:
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

    await _end_raffle_impl(
        ctx, raffle_message.id, raffle_type, num_winners, selection_type
    )


async def _end_raffle_impl(
    ctx: commands.Context,
    raffle_message_id: int,
    raffle_type: str,
    num_winners: int,
    selection_type: str,
) -> None:
    raffle_message = await ctx.fetch_message(raffle_message_id)
    if raffle_message is None:
        raise Exception("Oops! That raffle does not exist anymore.")

    # We annotate the raffle_type param above as `str` for a more-clear error message
    # This way it says it doesn't recognize the raffle type rather than fail param type conversion
    raffle_type = RaffleType(raffle_type)

    # We annotate the selection_type param above as `str` for the same reason
    selection_type = SelectionType(selection_type)

    if raffle_type == RaffleType.Normal:
        recent_raffle_winner_ids = DB.get().recent_winner_ids(ctx.guild.id)
        past_week_winner_ids = DB.get().past_week_winner_ids(ctx.guild.id)
        ineligible_winner_ids = recent_raffle_winner_ids.union(past_week_winner_ids)
    elif raffle_type == RaffleType.Anyone:
        ineligible_winner_ids = set()
    elif raffle_type == RaffleType.New:
        ineligible_winner_ids = DB.get().all_winner_ids(ctx.guild.id)
    else:
        raise Exception("Unimplemented raffle type")

    entrants = set()
    for reaction in raffle_message.reactions:
        users = await reaction.users().flatten()
        for user in users:
            if user.id not in ineligible_winner_ids:
                entrants.add(user)

    # Certain servers may only want you to be eligible for a raffle if you have
    # given role(s). These are checked as ORs meaning if you have at least one
    # of the configured roles you are eligible to win.
    eligible_role_ids = DB.get().eligible_role_ids(ctx.guild.id)
    if len(eligible_role_ids) > 0:
        for entrant in entrants.copy():
            if eligible_role_ids.intersection(_get_role_ids(entrant)) == set():
                entrants.remove(entrant)

    if len(entrants) == 0:
        await ctx.send("No one eligible entered the raffle so there is no winner.")
        return

    if selection_type == SelectionType.Weighted:
        winners = _choose_winners_weighted(list(entrants), num_winners)
    else:
        winners = _choose_winners_unweighted(list(entrants), num_winners)

    DB.get().record_win(ctx.guild.id, raffle_message_id, *winners)

    if len(winners) == 1:
        await ctx.send("{} has won the raffle!".format(winners[0].mention))
    else:
        await ctx.send(
            "Raffle winners are: {}!".format(
                ", ".join(map(lambda winner: winner.mention, winners))
            )
        )


def _choose_winners_unweighted(
    entrants: list[discord.Member], num_winners: int
) -> list[discord.Member]:
    if len(entrants) < num_winners:
        raise Exception("There are not enough entrants for that many winners.")

    winners = []
    while num_winners > 0:
        winner = random.choice(entrants)
        winners.append(winner)
        entrants.remove(winner)
        num_winners -= 1

    return winners


def _choose_winners_weighted(
    guild_id: int, entrants: list[discord.Member], num_winners: int
) -> list[discord.Member]:
    """
    Purpose of this algorithm is to choose winners in a way that actually lowers
    their chances the more raffles they've won in the past.
    Conceptually, can think of it as giving out more raffle "tickets" to those that have not won as often.

    Each raffle win lowers your relative odds of winning by 25%.
    So someone who has won once is 0.75x as likely to win as someone who has never won.
    Someone who's won twice is 0.5625x (0.75^2) as likely as someone who has never won.
    And so on.

    Here's how it works.

    We start by fetching the past wins of everyone in the guild.
    Then, of the current raffle entrants, we start with the person who's won the most times.
    Going from that win count -> 0 we figure out the ticket distribution factor for each bucket of win counts.
    Then we figure out how many tickets they should get for each bucket based on that distribution factor.
    That then gives us the relative probability array that gets fed into random.choice

    Here's an example.

    Say we have the following entrants:
    8 people who've won 0 times
    5 people who have won 1 time
    2 people who have won 2 times
    1 person who has won 4 times

    Highest win count is 4 wins so we start there.
    That bucket awards 1 ticket and then we calculate the fewer-win bucket tickets:
    4 wins -> 1 ticket
    3 wins -> 4/3 (~1.3) tickets
    2 wins -> 16/9 (~1.8) tickets
    1 win -> 64/27 (~2.4) tickets
    0 wins -> 256/81 (~3.16) tickets

    This way: 4 wins gets 0.75x as many tickets as 3 wins,
    3 wins gets 0.75x as many tickets as 2 wins, and so on.

    Total tickets given out is the sum of each bucket's tickets the number of entrants:
    8 entrants * 256/81 tickets
    + 5 * 64/27
    + 2 * 16/9
    + 0 * 4/3
    + 1 * 1
    = ~41.7 tickets

    Now, the p-list values should all sum up to 1. So we treat those tickets as
    portions of a "single ticket" and give out those portions.
    We do that by taking the reciprocal, so 1/41.7 = 0.0239857862

    0.0239857862 now is the chance of winning if you were given one "ticket".
    Then we divvy out those tickets according to the number awarded per win bucket.

    So then we end with:
    8 people get 256/81 * 0.0239857862 = 0.07580692922 "tickets"
    5 people get 64/27 * 0.0239857862 = 0.05685519692 tickets
    2 people get 16/9 * 0.0239857862 = 0.04264139769 tickets
    1 person gets 1 * 0.0239857862 = 0.0239857862 tickets

    As a check, if we add all those up, it should equal 1.
    0.07580692922 * 8 + 0.05685519692 * 5 + 0.04264139769 * 2 + 0.0239857862 = 0.9999999999

    So then for our p-list, our resultant structure is:
    [0.07580692922, 0.07580692922, 0.07580692922, ..., 0.04264139769, 0.04264139769, 0.0239857862]

    And we sort the corresponding entrants list by their win counts ascending so the two lists line up.
    [0-wins entrant, 0-wins entrant, 0-wins entrant, ..., 2-wins entrant, 2-wins entrant, 4-wins entrant]

    Then we let numpy.random.choice work its magic.
    """
    if len(entrants) < num_winners:
        raise Exception("There are not enough entrants for that many winners.")

    # Just to add even more randomness
    random.shuffle(entrants)
    random.shuffle(entrants)
    random.shuffle(entrants)

    past_winner_win_counts = DB.get().win_counts(guild_id)
    entrants = sorted(
        entrants, key=lambda entrant: past_winner_win_counts.get(entrant.id, 0)
    )

    total_win_counts = {}
    for entrant in entrants:
        entrant_past_wins = past_winner_win_counts.get(entrant.id, 0)
        if entrant_past_wins not in total_win_counts:
            total_win_counts[entrant_past_wins] = 1
        else:
            total_win_counts[entrant_past_wins] += 1

    tickets_per_win_bucket = {}
    highest_entrant_wins = max(total_win_counts.keys())
    for i in range(highest_entrant_wins, -1, -1):
        tickets_per_win_bucket[i] = (4 / 3) ** (highest_entrant_wins - i)

    total_tickets = 0
    for win, tickets in tickets_per_win_bucket.items():
        total_tickets += total_win_counts.get(win, 0) * tickets

    value_of_one_ticket = 1 / total_tickets
    for win, multiplier in tickets_per_win_bucket.copy().items():
        tickets_per_win_bucket[win] = multiplier * value_of_one_ticket

    p_list = []
    for win, tickets in reversed(tickets_per_win_bucket.items()):
        for i in range(0, total_win_counts.get(win, 0)):
            p_list.append(tickets)

    return numpy.random.choice(entrants, num_winners, replace=False, p=p_list)


def _get_role_ids(member: discord.Member) -> set[int]:
    return set(map(lambda role: role.id, member.roles))


bot.run(config["Discord"]["Token"])
