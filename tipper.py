import math
import sys
import traceback

import praw.exceptions

import util


class Tipper:
    def __init__(self, db, reddit_client, wallet_id, rest_wallet, log):
        self.wallet_id = wallet_id
        self.db = db
        self.reddit_client = reddit_client
        self.rest_wallet = rest_wallet
        self.log = log

    @util.handle_api_exceptions(max_attempts=3)
    def comment_reply(self, comment, reply_text):
        self.log.info("BOT MAKING COMMENT REPLY:")
        self.log.info(reply_text)
        comment.reply(reply_text)

    @staticmethod
    def is_usd(amount):
        if amount.startswith("$"):
            return True
        return False

    def send_tip(self, comment, amount, sender_user_address, receiving_address, receiving_user, prior_reply_text):
        try:
            rate = util.get_price()
            if rate is None:
                raise ValueError('Could not retrieve rate')

            formatted_rate = str(format(float(rate), '.3f'))
            formatted_amount = amount
            if self.is_usd(amount):
                amount = amount[1:]
                usd = amount
                formatted_usd = usd
                amount = float(amount) / rate
                formatted_amount = str(format(float(amount), '.6f'))
            else:
                usd = float(amount) * rate
                formatted_usd = str(format(float(usd), '.3f'))

            self.log.info("Sending amount: " + str(amount) + "XRB, $" + str(usd))
            data = {'action': 'account_balance',
                    'account': sender_user_address}
            post_body = self.rest_wallet.post_to_wallet(data, self.log)
            data = {'action': 'rai_from_raw', 'amount': int(
                post_body['balance'])}
            rai_balance = self.rest_wallet.post_to_wallet(data, self.log)

            # float of total send
            float_amount = float(amount)
            if float_amount > 0:
                rai_send = float_amount * 1000000
                raw_send = str(int(rai_send)) + '000000000000000000000000'
                self.log.info("Current rai balance: " + str(rai_balance['amount']))

                # Add prior reply text to new
                reply_text = ""

                if prior_reply_text is not None:
                    reply_text = prior_reply_text + "\n\n"

                # check amount left
                if int(rai_send) <= int(rai_balance['amount']):
                    self.log.info('Tipping now')
                    data = {'action': 'send', 'wallet': self.wallet_id, 'source': sender_user_address,
                            'destination': receiving_address, 'amount': int(raw_send)}
                    post_body = self.rest_wallet.post_to_wallet(data, self.log)
                    reply_text = reply_text + \
                                 'Tipped %s XRB or $%s to /u/%s\n\nUSD conversion rate of $%s per XRB from [Coin Market Cap](https://coinmarketcap.com/currencies/raiblocks/)\n\n[Block Link](https://www.nanode.co/block/%s)' \
                                 % (formatted_amount, formatted_usd, receiving_user, formatted_rate,
                                    str(post_body['block']))
                    reply_text = reply_text + "  \n\nGo to the [wiki]" + \
                                 "(https://np.reddit.com/r/NANO_tipbot/wiki/start) for more info"
                else:
                    reply_text = reply_text + 'Not enough in your account to tip'

                self.comment_reply(comment, reply_text)
        except TypeError as e:
            reply_message = 'An error came up, your request could not be processed\n\n' + \
                            ' Paging /u/valentulus_menskr error id: ' + comment.fullname + '\n\n'
            self.comment_reply(comment, reply_message)
            tb = traceback.format_exc()
            self.log.error(e)
            self.log.error(tb)
        except:
            reply_message = 'An error came up, your request could not be processed\n\n' + \
                            ' Paging /u/valentulus_menskr error id: ' + comment.fullname + '\n\n'
            self.comment_reply(comment, reply_message)
            self.log.error("Unexpected error in send_tip: " + str(sys.exc_info()[0]))
            tb = traceback.format_exc()
            self.log.error(tb)

    def process_tip(self, amount, comment, receiving_user):
        if receiving_user.lower() == 'giftnano':
            receiving_user = 'giftxrb'
        user_table = self.db['user']
        comment_table = self.db['comments']

        # See if we have an author xrb address and a to xrb address, if not invite to register
        self.log.info("Looking for sender " + "'" + comment.author.name + "'" + " in db")

        sender_user_data = util.find_user(comment.author.name, self.log, self.db)

        if sender_user_data is not None:
            self.log.info('Sender in db')
            # Author registered
            sender_user_address = sender_user_data['xrb_address']

            reply_text = None

            user_data = util.find_user(receiving_user, self.log, self.db)
            if user_data is not None:
                receiving_address = user_data['xrb_address']
            else:
                self.log.info("Receiving User " + "'" + receiving_user + "'" + " Not in DB - registering")
                # Generate address
                data = {'action': 'account_create',
                        'wallet': self.wallet_id}
                post_body = self.rest_wallet.post_to_wallet(data, self.log)
                self.log.info("Receiving User new account: " + str(post_body['account']))

                # Add to database
                record = dict(user_id=receiving_user, xrb_address=post_body['account'])
                self.log.info("Inserting into db: " + str(record))
                user_table.insert(record)
                receiving_address = post_body['account']

                reply_text = str(receiving_user) \
                             + ' isn\'t registered, so I made an account for them. ' \
                             + 'They can access it by messaging the bot.'

            self.send_tip(comment, amount, sender_user_address, receiving_address, receiving_user, reply_text)

        else:
            self.log.info('Sender NOT in db')
            reply_text = 'Hi /u/' + str(comment.author.name) + ', please register with the bot by sending it a' \
                         + ' private message with the text "register" in the body of the message.  \n\nGo to the [wiki]' + \
                         "(https://np.reddit.com/r/NANO_tipbot/wiki/start) for more info"

            self.comment_reply(comment, reply_text)

        # Add to db
        record = dict(
            comment_id=comment.fullname, to=receiving_user, amount=amount, author=comment.author.name)
        self.log.info("Inserting into db: " + str(record))
        comment_table.insert(record)
        self.log.info('DB updated')

    @staticmethod
    def isfloat(value):
        try:
            if len(value) > 0 and value.startswith("$"):
                value = value[1:]

            float_val = float(value)
            if not math.isnan(float_val):
                return True
        except ValueError:
            return False
        return False

    @staticmethod
    def parse_user(user):
        if user.startswith('/u/'):
            user = user[3:]
        return user

    def user_exists(self, user):
        exists = True
        try:
            self.reddit_client.redditor(user).fullname
        except praw.exceptions.PRAWException:
            self.log.error("User '" + user + "' not found")
            exists = False
        except:
            self.log.error("Unexpected error in send_tip: " + str(sys.exc_info()[0]))
            tb = traceback.format_exc()
            self.log.error(tb)
            exists = False
        return exists

    def invalid_formatting(self, comment, mention):
        comment_table = self.db['comments']
        self.log.info('Invalid formatting')
        if comment.author.name.lower() != 'raiblocks_tipbot' and comment.author.name.lower() != 'nano_tipbot' and comment.author.name.lower() != 'nano4u':
            if mention:
                self.comment_reply(comment, 'Was I mentioned? I could not parse your request  \n\nGo to the [wiki]' +
                                   '(https://np.reddit.com/r/NANO_tipbot/wiki/start) to learn how to tip with' +
                                   ' NANO')
            else:
                self.comment_reply(comment,
                                   'Tip command is invalid. Tip with any of the following formats:  \n\n' +
                                   '`!tipxrb <username> <amount>`  \n\n`/u/NANO_TipBot <username> <amount>`  \n\n'
                                   + '`/u/XRB4U <username> <amount>`  \n\nGo to the [wiki]' +
                                   '(https://np.reddit.com/r/NANO_tipbot/wiki/start) for more commands')
        record = dict(
            comment_id=comment.fullname, to=None, amount=None, author=comment.author.name)
        self.log.info("Inserting into db: " + str(record))
        comment_table.insert(record)
        self.log.info('DB updated')

    def process_command(self, comment, receiving_user, amount):
        # parse reddit username
        receiving_user = self.parse_user(receiving_user)
        self.log.info("Receiving user: " + receiving_user)
        self.process_tip(amount, comment, receiving_user)

    def validate_double_parameter_tip(self, parts_of_comment, command_index):
        receiving_user = parts_of_comment[command_index + 1]
        amount = parts_of_comment[command_index + 2]
        passing = False
        if self.isfloat(amount):
            # valid amount input
            # parse reddit username
            receiving_user = self.parse_user(receiving_user)
            # check if that is a valid reddit
            if self.user_exists(receiving_user):
                passing = True

        return passing

    def validate_single_parameter_tip(self, parts_of_comment, command_index):
        # check that index+1 is a float before proceeding to extract receiving_user
        amount = parts_of_comment[command_index + 1]
        if self.isfloat(amount):
            return True
        return False

    def process_single_parameter_tip(self, comment, amount):
        # Is this a root comment?
        is_root = comment.is_root
        self.log.info("Root comment? " + str(comment.is_root))
        if is_root:
            receiving_user = comment.link_author
        else:
            # Get parent
            parent = comment.parent()
            receiving_user = parent.author.name
            self.log.info("Parent: ")
            self.log.info(vars(parent))

        self.process_command(comment, receiving_user, amount)

    def parse_tip(self, comment, parts_of_comment, command_index, mention):
        # get a reference to the table 'comments'
        comment_table = self.db['comments']

        # Save the comment id in a database so we don't repeat this
        if comment_table.find_one(comment_id=comment.fullname):
            self.log.info('Already in db, ignore')
        else:
            author = comment.author.name.lower()
            try:
                subreddit_name = comment.subreddit.display_name;
            except:
                subreddit_name = ''

            if author != "reddit" and author != "xrb4u" and author != "raiblocks_tipbot" and author != "giftxrb" \
                    and author != "automoderator" and author != "giftnano" and author != "nano_tipbot" and author != "nano4u" and subreddit_name.lower() != "cryptocurrency":
                length = len(parts_of_comment)
                passing = False

                # check that index+2 exists in array
                if command_index + 2 < length:
                    # check for both tip formats
                    # !tipxrb <user> <amount>
                    # !tipxrb <amount>
                    receiving_user = parts_of_comment[command_index + 1]
                    amount = parts_of_comment[command_index + 2]
                    if self.validate_double_parameter_tip(parts_of_comment, command_index):
                        self.process_command(comment, receiving_user, amount)
                        passing = True
                    elif self.validate_single_parameter_tip(parts_of_comment, command_index):
                        amount = parts_of_comment[command_index + 1]
                        self.process_single_parameter_tip(comment, amount)
                        passing = True

                elif command_index + 1 < length:
                    # check for one tip format
                    # !tipxrb <amount>
                    if self.validate_single_parameter_tip(parts_of_comment, command_index):
                        amount = parts_of_comment[command_index + 1]
                        self.process_single_parameter_tip(comment, amount)
                        passing = True

                if not passing:
                    # invalid command
                    self.invalid_formatting(comment, mention)
            else:
                # Add to db
                record = dict(
                    comment_id=comment.fullname, to=None, amount=None, author=comment.author.name)
                self.log.info("Inserting into db: " + str(record))
                comment_table.insert(record)
                self.log.info('DB updated')

    def parse_comment(self, comment, commands, mention):
        comment_split_newlines = comment.body.lower().splitlines()
        found = False
        for line in comment_split_newlines:
            parts_of_comment = line.split(" ")
            for command in commands:
                command = command.lower()
                if command in parts_of_comment and not found:
                    found = True
                    self.log.info('\n\n')
                    self.log.info('Found tip reference in comments')
                    self.log.info("Comment is as follows:")
                    self.log.info((vars(comment)))

                    command_index = parts_of_comment.index(command)
                    self.parse_tip(comment, parts_of_comment, command_index, mention)
