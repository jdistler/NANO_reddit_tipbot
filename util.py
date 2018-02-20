import time
from functools import wraps
from socket import error as SocketError

import praw.exceptions
import requests


def handle_api_exceptions(max_attempts=1):
    """Return a function decorator that wraps a given function in a
    try-except block that will handle various exceptions that may
    occur during an API request to reddit. A maximum number of retry
    attempts may be specified.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_attempts:
                sleep_time = None
                error_msg = ""
                try:
                    return func(*args, **kwargs)
                # Handle and log miscellaneous API exceptions
                except praw.exceptions.PRAWException as e:
                    error_msg = "PRAW Exception \"{error}\" occurred: ".format(
                        error=e)
                except praw.exceptions.ClientException as e:
                    error_msg = "Client Exception \"{error}\" occurred: ".format(
                        error=e)
                except praw.exceptions.APIException as e:
                    error_msg = "API Exception \"{error}\" occurred: ".format(
                        error=e)
                except SocketError as e:
                    error_msg = "SocketError \"{error}\" occurred: ".format(
                        error=e)
                    args[0].log.error(error_msg)
                sleep_time = sleep_time or retries * 15
                args[0].log.error("{0} in {f}. Sleeping for {t} seconds. "
                                  "Attempt {rt} of {at}.".format(error_msg, f=func.__name__,
                                                                 t=sleep_time, rt=retries + 1, at=max_attempts))
                time.sleep(sleep_time)
                retries += 1

        return wrapper

    return decorator


# This method corrects an inconsistency in the current db state
# users were registered with different string casing accidentally i.e valentulus_menskr vs Valentulus_menskr
def find_user(user_id, logger, db):
    statement = 'SELECT * FROM user WHERE user_id="' + user_id + '" COLLATE NOCASE'
    size = 0
    target_row = None

    for row in db.query(statement):
        if size == 0:
            target_row = row
        else:
            logger.error("Multiple entries found")
        size += 1
    return target_row


def get_price():
    try:
        r = requests.get('https://api.coinmarketcap.com/v1/ticker/nano/')
        payload = r.json()[0]["price_usd"]
        result = float(payload)
    except:
        result = None

    return result
