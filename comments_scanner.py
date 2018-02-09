import traceback

import praw.exceptions
import prawcore


class CommentsScanner:
    def __init__(self, reddit_client, subreddit, tipper, log):
        self.reddit_client = reddit_client
        self.subreddit = subreddit

        self.log = log

        self.tipper = tipper

    def scan_comments(self):
        subreddit_client = self.reddit_client.subreddit(self.subreddit)

        self.log.info('Tracking r/' + self.subreddit + ' Comments')

        try:
            for comment in subreddit_client.stream.comments():
                command = ['!tipxrb', '!tipnano']
                self.tipper.parse_comment(comment, command, False)

        except (praw.exceptions.PRAWException, prawcore.exceptions.PrawcoreException) as e:
            tb = traceback.format_exc()
            self.log.error("could not log in because: " + str(e))
            self.log.error(tb)

    def run_scan_loop(self):
        while 1:
            self.scan_comments()
