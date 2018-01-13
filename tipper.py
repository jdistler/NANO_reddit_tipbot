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

    def send_tip(self, comment, amount, sender_user_address, receiving_address, receiving_user, prior_reply_text,
                 rai_balance):
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
                    self.log.info('Gifting now')
                    giveaway_xrb = float(rai_balance['amount']) / 1000000.0
                    redditors_left = giveaway_xrb / 0.0001

                    data = {'action': 'send', 'wallet': self.wallet_id, 'source': sender_user_address,
                            'destination': receiving_address, 'amount': int(raw_send)}
                    post_body = self.rest_wallet.post_to_wallet(data, self.log)
                    reply_text = reply_text + \
                                 'Congratulations! /u/%s has been gifted %s XRB or $%s \n\nUSD conversion rate of $%s per XRB from [Coin Market Cap](https://coinmarketcap.com/currencies/raiblocks/)\n\n[Block Link](https://www.raiblocks.club/block/%s)' \
                                 % (receiving_user, formatted_amount, formatted_usd, formatted_rate,
                                    str(post_body['block']))
                    reply_text = reply_text + "  \n\nAn account with the RaiBlocks_TipBot has been registered"
                    reply_text = reply_text + "  \n\nThe GiveAway balance is %s, so I can gift %s more redditors!" % (
                        str(giveaway_xrb), str(int(redditors_left)))
                    reply_text = reply_text + "  \n\nGo to the [GiveAway Wiki]" + \
                                 "(https://np.reddit.com/r/RaiBlocks_tipbot/wiki/giveaway) for more info"
                else:
                    reply_text = reply_text + 'The GiveAway bot is all out of gifts! Consider tipping this bot ' \
                                              'to replenish its gifts'
                    reply_text = reply_text + "  \n\nGo to the [GiveAway Wiki]" + \
                                 "(https://np.reddit.com/r/RaiBlocks_tipbot/wiki/giveaway) for more info"

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
        user_table = self.db['user']
        comment_table = self.db['comments']

        # See if we have an author xrb address and a to xrb address, if not invite to register
        self.log.info("Looking for sender " + "'" + comment.author.name + "'" + " in db")

        comment.author.name = "giftxrb"

        sender_user_data = util.find_user(comment.author.name, self.log, self.db)

        if sender_user_data is not None:
            self.log.info('Sender in db')
            # Author registered
            sender_user_address = sender_user_data['xrb_address']

            reply_text = None

            user_data = util.find_user(receiving_user, self.log, self.db)
            if user_data is not None:
                # reply that registered users cannot be gifted
                reply_message = "The user /u/" + receiving_user + " cannot be gifted because they are already" + \
                                " registered with the TipBot\n\n Pass the gift to all newcomers to RaiBlocks!" + \
                                "\n\n For more info on the giveaway, check out the" + \
                                " [GiveAway Wiki](https://np.reddit.com/r/RaiBlocks_tipbot/wiki/giveaway)"

                self.comment_reply(comment, reply_message)
            else:
                self.log.info("Receiving User " + "'" + receiving_user + "'" + " Not in DB - registering")
                # ONLY REGISTER IF THE BOT HAS ENOUGH MONEY TO TIP

                data = {'action': 'account_balance',
                        'account': sender_user_address}
                post_body = self.rest_wallet.post_to_wallet(data, self.log)
                data = {'action': 'rai_from_raw', 'amount': int(
                    post_body['balance'])}
                rai_balance = self.rest_wallet.post_to_wallet(data, self.log)
                float_amount = float(amount)
                if float_amount > 0:
                    rai_send = float_amount * 1000000

                    # check amount left
                    if int(rai_send) <= int(rai_balance['amount']):

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

                        self.send_tip(comment, amount, sender_user_address, receiving_address, receiving_user,
                                      reply_text, rai_balance)
                    else:
                        reply_text = 'The GiveAway bot is all out of gifts! Consider tipping this bot ' \
                                     'to replenish its gifts'
                        reply_text = reply_text + "  \n\nGo to the [GiveAway Wiki]" + \
                                     "(https://np.reddit.com/r/RaiBlocks_tipbot/wiki/giveaway) for more info"
                        self.comment_reply(comment, reply_text)

        else:
            self.log.info('Sender NOT in db')
            reply_text = 'Hi /u/' + str(comment.author.name) + ', please register with the bot by sending it a' \
                         + ' private message.  \n\nGo to the [wiki]' + \
                         "(https://np.reddit.com/r/RaiBlocks_tipbot/wiki/index) for more info"

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
            # Maximum tip per command is 5 XRB (currently valued $150)
            # This is to prevent mistaken tips of large sums
            if 0 < float_val < 5 and not math.isnan(float_val):
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
        if comment.author.name != 'RaiBlocks_tipbot':
            if mention:
                self.comment_reply(comment, 'Was I mentioned? I could not parse your request  \n\nGo to the [wiki]' +
                                   '(https://np.reddit.com/r/RaiBlocks_tipbot/wiki/index) to learn how to tip with' +
                                   ' RaiBlocks')
            else:
                self.comment_reply(comment,
                                   'Tip command is invalid. Tip with any of the following formats:  \n\n' +
                                   '`!tipxrb <username> <amount>`  \n\n`\u\RaiBlocks_TipBot <username> <amount>`  \n\n'
                                   + '`\u\XRB4U <username> <amount>`  \n\n  Amount must be greater than 0'
                                   + ' and less than 5  \n\nGo to the [wiki]' +
                                   '(https://np.reddit.com/r/RaiBlocks_tipbot/wiki/index) for more commands')
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
        # Get parent
        parent = comment.parent()
        receiving_user = parent.author.name
        self.log.info("Parent: ")
        self.log.info(vars(parent))

        if receiving_user is not None and receiving_user.lower() != "giftxrb":
            self.process_command(comment, receiving_user, amount)
        else:
            self.comment_reply(comment, 'Was I mentioned? I could not parse your request  \n\nGo to the [wiki]' +
                               '(https://np.reddit.com/r/RaiBlocks_tipbot/wiki/giveaway) to learn about '
                               'the GiveAway program')

    def parse_tip(self, comment):
        # get a reference to the table 'comments'
        comment_table = self.db['comments']

        # Save the comment id in a database so we don't repeat this
        if comment_table.find_one(comment_id=comment.fullname):
            self.log.info('Already in db, ignore')
        else:
            amount = "0.0001"
            self.process_single_parameter_tip(comment, amount)

    def parse_comment(self, comment, commands, mention):
        try:
            self.parse_tip(comment)
        except:
            self.log.error("Unexpected error in send_tip: " + str(sys.exc_info()[0]))
            tb = traceback.format_exc()
            self.log.error(tb)
            reply_message = "I'm sorry an error occurred. Paging /u/valentulus_menskr"
            self.comment_reply(comment, reply_message)
