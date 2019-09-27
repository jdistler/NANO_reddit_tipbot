# NANO Reddit TipBot

## About
This project implements a reddit tipbot which provides users an abstraction for a NANO wallet. Users are given their own unique deposit address, and can send NANO to other Reddit users by commenting on posts. The receiving user can then register with the tipbot via Reddit private message, and redeem their funds.
The goal of this is to foster the exchange of the NANO cryptocurrency all throughout reddit.

## Installation
Edit settings.py.example with your own details for accessing the Reddit API and also the wallet ID for your NANO node then rename the file to settings.py

## Running
Use the `launchScanners.sh` script to kill existing python processes, and start the two bots in the background.
`inbox_scanner.py` reads all incoming reddit mail to the bot to answer queries, and `comments_scanner.py` scans the entire NANO subreddit for mentions using `!tipxrb` or `!tipnano`.

## Using
For more information check out the current active fork of this project - 
https://github.com/danhitchcock/nano_tipper_z
