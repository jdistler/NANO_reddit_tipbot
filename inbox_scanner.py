import sys
import traceback

import praw.exceptions
import prawcore

import util


class InboxScanner:

    def __init__(self, db, reddit_client, wallet_id, rest_wallet, subreddit, tipper, log):
        self.wallet_id = wallet_id
        self.db = db
        self.reddit_client = reddit_client
        self.rest_wallet = rest_wallet
        self.subreddit = subreddit
        self.log = log

        self.tipper = tipper

    def transfer_funds(self, amount, item, send_address):
        try:
            user_data = util.find_user(item.author.name, self.log, self.db)
            user_address = user_data['xrb_address']
            data = {'action': 'account_balance', 'account': user_address}
            parsed_json = self.rest_wallet.post_to_wallet(data, self.log)
            data = {'action': 'rai_from_raw', 'amount': int(parsed_json['balance'])}
            rai_balance = self.rest_wallet.post_to_wallet(data, self.log)

            rai_send = float(amount) * 1000000  # float of total send
            raw_send = str(int(rai_send)) + '000000000000000000000000'
            # check amount left
            if int(rai_send) <= int(rai_balance['amount']):
                data = {'action': 'send', 'wallet': self.wallet_id, 'source': user_address, 'destination': send_address,
                        'amount': int(raw_send)}
                parsed_json = self.rest_wallet.post_to_wallet(data, self.log)
                reply_message = 'Sent %s to %s\n\n[Block Link](https://www.raiblocks.club/block/%s)' % (
                    amount, send_address, str(parsed_json['block']))
                item.reply(reply_message)
            else:
                reply_message = 'Not enough in your account to transfer\n\n'
                item.reply(reply_message)
        except:
            reply_message = 'Invalid amount : %s' % amount
            item.reply(reply_message)
            self.log.error("Unexpected error: " + str(sys.exc_info()[0]))
            tb = traceback.format_exc()
            self.log.error(tb)

    def prepare_send(self, commands, item):
        amount = commands[1]
        send_address = commands[2]
        data = {"action": "validate_account_number", "account": send_address}
        check_address = self.rest_wallet.post_to_wallet(data, self.log)
        if len(send_address) != 64 or send_address[:4] != "xrb_" or check_address['valid'] != '1':
            self.log.info('Invalid destination address')
            reply_message = 'Invalid destination address : %s' % send_address
            item.reply(reply_message)
        else:
            self.transfer_funds(amount, item, send_address)

    def get_balance(self, item):
        user_data = util.find_user(item.author.name, self.log, self.db)
        user_address = user_data['xrb_address']
        data = {'action': 'account_balance', 'account': user_address}
        parsed_json = self.rest_wallet.post_to_wallet(data, self.log)

        data = {'action': 'rai_from_raw', 'amount': int(parsed_json['balance'])}
        rai_balance = self.rest_wallet.post_to_wallet(data, self.log)
        self.log.info(rai_balance['amount'])
        xrb_balance = format((float(rai_balance['amount']) / 1000000.0), '.6f')
        rate = util.get_price()
        if rate is not None:
            usd = float(xrb_balance) * rate
            reply_message = 'Your balance is :\n\n %s XRB or $%s USD \n\nUSD conversion rate of $%s' % \
                            (xrb_balance, str(format(float(usd), '.3f')), str(format(float(rate), '.3f')))
        else:
            reply_message = 'Your balance is :\n\n %s XRB' % xrb_balance
        item.reply(reply_message)

    def register_account(self, item, user_table):
        # Generate address
        data = {'action': 'account_create', 'wallet': self.wallet_id}
        parsed_json = self.rest_wallet.post_to_wallet(data, self.log)
        self.log.info(parsed_json['account'])
        # Add to database
        record = dict(user_id=item.author.name, xrb_address=parsed_json['account'])
        self.log.info("Inserting into db: " + str(record))
        user_table.insert(record)
        # Reply
        explorer_link = 'https://www.raiblocks.club/account/' + parsed_json['account']
        reply_message = 'Thanks for registering, your deposit address is ' + parsed_json['account'] + \
                        ' and you can see your balance here ' + explorer_link + '\r\nFor more details reply with "help"'

        item.reply(reply_message)

    def process_mention(self, item):
        comment = None
        command = ["/u/RaiBlocks_TipBot", "u/RaiBlocks_TipBot", "/u/XRB4U", "u/XRB4U"]
        try:
            self.log.info("Mention Found")
            comment_parts = item.name.split("_")
            comment_id = comment_parts[len(comment_parts) - 1]
            self.log.info("Comment ID: " + comment_id)
            comment = self.reddit_client.comment(comment_id)

            submission_parts = comment.link_id.split("_")
            submission_id = submission_parts[len(submission_parts) - 1]
            submission = self.reddit_client.submission(submission_id)
            comment.link_author = submission.author.name

        except:
            reply_message = 'An error came up, your request could not be processed\n\n' + \
                            ' Paging /u/valentulus_menskr error id: ' + item.name + '\n\n'
            item.reply(reply_message)
            self.log.error("Unexpected error: " + str(sys.exc_info()[0]))
            tb = traceback.format_exc()
            self.log.error(tb)

        if comment is not None:
            self.tipper.parse_comment(comment, command, True)

    def parse_item(self, item):
        self.log.info("\n\n")
        self.log.info("New Inbox Received")
        message_table = self.db['message']

        if message_table.find_one(message_id=item.name):
            self.log.info('Already in db, ignore')
        else:
            user_table = self.db['user']

            self.log.info("Item is as follows:")
            self.log.info((vars(item)))

            self.log.info("Attribute - Item was comment: " + str(item.was_comment))
            if item.was_comment:
                self.log.info("Comment subject: " + str(item.subject))
                if item.subject == 'username mention':
                    self.process_mention(item)
            else:
                user_data = util.find_user(item.author.name, self.log, self.db)
                if user_data is not None:
                    self.log.info('Found Author ' + str(item.author.name))
                    commands = item.body.split(" ")
                    self.log.info(item.body)
                    if 'help' in item.body.lower():
                        reply_message = 'Help\n\n Reply with the command in the body of text:\n\n  balance - get' \
                                        + ' your balance\n\n  send <amount> <address> - send XRB to an external ' \
                                          'address\n\naddress - get your deposit address\n\nMore info: ' \
                                        + 'https://www.reddit.com/r/RaiBlocks_tipbot/wiki/start'
                        item.reply(reply_message)

                    elif 'address' in item.body.lower():
                        self.log.info(user_data['xrb_address'])
                        reply_message = 'Your deposit address is :\n\n%s' % user_data['xrb_address']
                        item.reply(reply_message)

                    elif 'balance' in item.body.lower():
                        self.log.info('Getting balance')
                        self.get_balance(item)

                    elif 'send' in item.body.lower():
                        self.log.info('Sending raiblocks')
                        if len(commands) > 2:
                            self.prepare_send(commands, item)
                        else:
                            reply_message = 'Sorry I could not parse your request.\n\nWhen making requests only put' + \
                                            ' one command in the message body with no other text\n\nTry the "help"' + \
                                            ' command\n\nMore info: ' \
                                            + 'https://www.reddit.com/r/RaiBlocks_tipbot/wiki/start'
                            item.reply(reply_message)

                    elif 'register' in item.body.lower():
                        self.log.info("Already Registered")
                        reply_message = 'Your account is already registered\n\nTry the "help" command\n\nMore info: ' \
                                        + 'https://www.reddit.com/r/RaiBlocks_tipbot/wiki/start'
                        item.reply(reply_message)

                    else:
                        self.log.info("Bad message")
                        reply_message = 'Sorry I could not parse your request.\n\nWhen making requests only put' + \
                                        ' one command in the message body with no other text\n\nTry the "help"' + \
                                        ' command\n\nMore info: ' \
                                        + 'https://www.reddit.com/r/RaiBlocks_tipbot/wiki/start'
                        item.reply(reply_message)
                else:
                    self.log.info(str(item.author.name) + ' Not in DB')
                    if 'register' in item.body.lower():
                        self.log.info('Registering account')
                        self.register_account(item, user_table)

                    else:
                        self.log.info("Could not parse message")
                        reply_message = 'Your account is not registered and I could not parse your command\n\n' + \
                                        ' Reply with "register" in the body of a private message to begin\n\n'
                        item.reply(reply_message)

            # Add message to database
            record = dict(user_id=item.author.name, message_id=item.name)
            self.log.info("Inserting into db: " + str(record))
            message_table.insert(record)

    def scan_inbox(self):
        self.log.info('Tracking Inbox')

        try:
            for item in self.reddit_client.inbox.stream():
                self.parse_item(item)

        except (praw.exceptions.PRAWException, prawcore.exceptions.PrawcoreException) as e:
            self.log.error("could not log in because: " + str(e))
            tb = traceback.format_exc()
            self.log.error(tb)

    def run_scan_loop(self):
        while 1:
            self.scan_inbox()
