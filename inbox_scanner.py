import sys
import traceback
from datetime import datetime

import praw.exceptions
import prawcore


class InboxScanner:

    def __init__(self, db, reddit_client, wallet_id, rest_wallet, subreddit, tipper, log):
        self.wallet_id = wallet_id
        self.db = db
        self.reddit_client = reddit_client
        self.rest_wallet = rest_wallet
        self.subreddit = subreddit
        self.log = log

        self.tipper = tipper

    def process_mention(self, item):
        comment = None
        command = ["/u/giftXRB", "u/giftXRB"]
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
            try:
                author = item.author.name.lower()
                if author != "reddit" and author != "xrb4u" and author != "raiblocks_tipbot" and author != "giftxrb" \
                        and author != "automoderator":

                    redditor = self.reddit_client.redditor(item.author.name)

                    created = redditor.created_utc

                    age = (datetime.utcnow() - datetime.fromtimestamp(int(created))).days

                    comment_karma = redditor.comment_karma

                    if age >= 10 and comment_karma >= 20:

                        self.log.info("Item is as follows:")
                        self.log.info((vars(item)))

                        self.log.info("Attribute - Item was comment: " + str(item.was_comment))

                        # Only care about mentions for the giveaway bot

                        if item.was_comment:
                            self.log.info("Comment subject: " + str(item.subject))
                            if item.subject == 'username mention':
                                self.process_mention(item)
                        else:
                            reply_message = 'Please do not send PMs to this bot. The main TipBot, /u/RaiBlocks_TipBot,' + \
                                            ' should be used for interaction via PM \n\nGo to the [wiki]' + \
                                            '(https://np.reddit.com/r/RaiBlocks_tipbot/wiki/giveaway) for more info'
                            item.reply(reply_message)
                    else:
                        reply_message = 'Sorry! I cannot gift an account less than 10 days old or with less than' \
                                        ' 20 comment karma\n\n This is to prevent bots from exploiting the RaiBlocks ' \
                                        'giveaway \n\nGo to the [wiki]' + \
                                        '(https://np.reddit.com/r/RaiBlocks_tipbot/wiki/giveaway) for more info'
                        item.reply(reply_message)
            except:
                reply_message = 'An error came up, your request could not be processed\n\n' + \
                                ' Paging /u/valentulus_menskr error id: ' + item.name + '\n\n'
                item.reply(reply_message)
                self.log.error("Unexpected error: " + str(sys.exc_info()[0]))
                tb = traceback.format_exc()
                self.log.error(tb)

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
