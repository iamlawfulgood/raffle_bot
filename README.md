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

There are only two attributes it (temporarily) stores per raffle: the server ID and the message ID (for the message the bot sent).  
These are only held on to for the duration of a raffle and once ended they are deleted.  

ZERO data about the people who entered the raffle is stored in any way.  
Raffle entrants are fetched only for the purpose of selecting a winner and then immediately discarded.  

The bot does not store information about past raffles nor does it keep any logs.

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
