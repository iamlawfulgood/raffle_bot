# Raffle Bot

Super-simple bot that can be used to run raffles in Discord. 

## Usage

To create a raffle, use the `!raffle start` command. 
Only one raffle may be active at a time per guild.

Members enter by reacting to the message sent by the bot.

To pick a winner, use the `!raffle end` command.

The bot will enter in each user once (no matter how many times they reacted) and randomly select a winner.

Multiple winners can be drawn by providing an argument to the `end` command.  
e.g. `!raffle end 3` will select three unique winners from the entrant pool.  

If a winner needs to be re-drawn from an already-closed raffle, reply to the raffle creation message (from the bot) and use the `!raffle redo` command.  
This is mostly equivalent to the `end` command but you must specify which raffle's entrants to use for the new draw. 

Example usage:

![Example screenshot](https://i.imgur.com/X1BlPGJ.png)

## Data Storage and Usage

This bot stores as little data as possible.
The table schema should be clear about what is actually stored but to make it clear:

`raffles`:
- `guild_id` -- The Discord server ID
- `message_id` -- The actual message the bot sent to start the raffle

`past_wins`:
- `id` -- Simple auto-incrementing ID
- `guild_id` -- The Discord server ID
- `message_id` -- The message the bot sent to start the raffle
- `user_id` -- The winner of that particular raffle

Other than the user ID there is no personal information otherwise stored or logged.

For raffle fairness, past wins are stored and *never purged*. These are preserved even after leaving the server in order to prevent cheating by leaving and re-joining.
If you would like your past wins expunged, please contact the server owner. 

Still TODO is a consent flow that will only allow you to win raffles if you have agreed to these terms.

## Winner Selection

As a result of this being almost entirely stateless, the bot does nothing to weigh entrants based on past wins.   
Each raffle is distinct and all entrants have equal likelihood of being selected as the winner for every raffle.  

Also, number of times someone has reacted to the raffle message has no impact on final selection. Each person is only entered a single time.  

If a different winner is desired for any reason, use the `!raffle redo` command as described above under the **Usage** section.  

## Installation

First create a new `config.ini` file. 
```
$> mv config.ini.schema config.ini
```

Then add your bot account's token to the `config.ini`.

To build and install the bot, run
```
$> docker-compose build
$> docker-compose up -d
```

## Discord Server Setup

The "raffler" role will need to be created and assigned to any members that should be allowed to manage raffles.
