#!/usr/bin/python

"""Scrape explainxkcd.com for XKCD comic information and email a selection.

Script produced as part of the project described at ttested.com/xkcd-mailer

This script scrapes the all comics table of explainxkcd.com to keep an 
up-to-date list of comics. Previous comic details are cached to minimise
the number of requests and improve processing time. A selection of comics
is then sent to a specified email address. The choosen comics are tracked
so that the same comic is never sent twice. Once all comics have been viewed
the script will warn the user.

The script is set up for use on GCP. See the README.md included in the project
repository (github.com/THargreaves/xckd-mailer) for how to implement this using
Google Cloud Functions, Storage, and Scheduler to have this script run
every week at 9am (or any other frequency of your choosing). If you wish to use
this script locally or on a different cloud platform, you will need to change
the 3rd-party imports and any sections surrounding pickle.load()/pickle.dump().

Features:
  * Can be run from scratch and will scrape all previous comic information
  * Will keep track of previously sent comics to avoid repetition
  * Will avoid sending you a latter part of a multi-part comic without first
    sending the former part(s)
  * Will include a reminder link to previous parts when a new part is sent
  * Will safely warn the user and exit when comic readership is up-to-date
  * Handles repeated URLs by taking latest version
  * Handles missing URLs by filling gaps with details of Null
"""

# imports
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import pickle
import random
import re
import smtplib
import ssl
import sys

from bs4 import BeautifulSoup
from google.cloud import exceptions, storage
import requests

# authorship information
__author__ = "Tim Hargreaves"
__license__ = "MIT"
__version__ = "1.0"

# script parameters
base_url = 'https://www.explainxkcd.com/wiki/index.php/'
receiver_email = 'fill_me_in'
num_per_day = 5
port = 465
sender_email = 'fill_me_in'
password = 'fill_me_in'

# for the optimists who expected the script to run without configuration
if any(x == 'fill_me_in' for x in (receiver_email, sender_email, password)):
	raise ValueError('make sure you fill in the script parameters')

# precompile regex for speed
r = re.compile(r'\s?[\-\:]\sPart\s(\d+)$')

def main(data, context):
    # setup storage handler
    storage_client = storage.Client()
    bucket = storage_client.get_bucket('mailer_storage')

    # load comic choice history
    try:
        blob = bucket.blob('history.p')
        blob.download_to_filename('/tmp/history.p')
        with open('/tmp/history.p', 'rb') as f:
            history = pickle.load(f)
    except exceptions.NotFound as e:
        history = [None]

    # load previous scraped comic details
    try:
        blob = bucket.blob('details.p')
        blob.download_to_filename('/tmp/details.p')
        with open('/tmp/details.p', 'rb') as f:
            details = pickle.load(f)
    except exceptions.NotFound as e:
        details = [None]

    # make a request for latest comics list
    res = requests.get(base_url + 'List_of_all_comics')
    latest_soup = BeautifulSoup(res.content, 'html.parser')

    # extract latest comic number
    latest_url = latest_soup.find_all('tr')[1].find('td').text.strip()
    latest_id = int(re.search(r'(\d+)', latest_url).group(1))

    # update history
    history.extend([False] * (latest_id - (len(history)-1)))

    # update details
    for i in [500*r for r in range((len(details)-1)//500, ((latest_id-1)//500))]:
        res = requests.get(base_url + 'List_of_all_comics' + f'_({i+1}-{i+500})')
        legacy_soup = BeautifulSoup(res.content, 'html.parser')
        details = update_details(details, legacy_soup)

    details = update_details(details, latest_soup, count=latest_id-len(details)+1)

    # save details
    blob = bucket.blob('details.p')
    with open('/tmp/details.p', 'wb') as f:
        pickle.dump(details, f)
    blob.upload_from_filename('/tmp/details.p')

    # make choices
    unread = [i for i, h in enumerate(history[1:]) if not h and not h is None]
    if unread:
        choices = random.sample(unread, min(len(unread), num_per_day))
    else:
		# no more comics to read - don't send an email
        sys.exit(0)
    caught_up = len(unread) <= num_per_day

    # propagate through previous to find first unread comic
    content = []
    for i, c in enumerate(choices):
        n = c
        while details[n]['prev'] and not history[details[n]['prev']]:
            n = details[n]['prev']
		# set details to be used for each email item
        content.append(
            details[n]
        )
        # update history
        history[n] = True
        content[i]['hist'] = []
        while (details[n]['prev']):
            n = details[n]['prev']
            content[i]['hist'].append(details[details[n]['prev']]['url'])

    # convert contents to text/HTML message
    text = ["Your daily XKCD comics are here!\r\n\r\n"]
    html = ["<html><body><h2>Your daily XKCD comics are here!</h2>"]
    for i, c in enumerate(content):
        title = c['title']
        id = c['id']
        text.append(f"Comic {i+1}: {title} ({id})\r\n")
        html.append(f"<h3>Comic {i+1}: {title} ({id})</h3>")

        html.append("<p>")

        url = c['url']
        date = c['date']
        text.append(f"URL: {url}\r\nDate: {date}\r\n")
        html.append(f"URL: <a href={url}>{url}</a><br>Date: {date}<br>")

        if c['prev']:
            text.append("Previous: " +
                        ' '.join(c['hist'][::-1]) +
                        "\r\n")
            html.append("Previous: " +
                        ' '.join([f"<a href={p}>Part {i+1}</a>"
                                 for i, p in enumerate(c['hist'][::-1])]) +
                        "<br>")

        if caught_up:
            text.append("You are now up-to-date on XKCD comics!\r\n")
            html.append("You are now up-to-date on XKCD comics!<br>")

        text.append("\r\n")
        html.append("</p>")

    html.append("</body></html>")

    # setup mailer and send email
    message = MIMEMultipart("alternative")
    message["Subject"] = f"Your XKCD comics for {datetime.date.today()}"
    message["From"] = sender_email
    message["To"] = receiver_email
    message.attach(MIMEText(''.join(text), "plain"))
    message.attach(MIMEText(''.join(html), "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())

    # save history
    blob = bucket.blob('history.p')
    with open('/tmp/history.p', 'wb') as f:
        pickle.dump(history, f)
    blob.upload_from_filename('/tmp/history.p')


def update_details(details, soup, count=500):
    for tr in soup.find_all('tr')[count:0:-1]:
        text = [td.find('a').text.strip() if td.find('a') else td.text.strip()
            for td in tr.find_all('td')]
        dets = {
            'id': int(re.search(r'(\d+)', text[0]).group(1)),
            'url': text[0],
            'title': text[1],
            'date': text[4],
            'base': re.sub(r, '', text[1])
        }
        base = dets['base']
        if dets['title'] != base and \
                int(re.search(r, text[1]).group(1)) > 1 :
            for p in range(dets['id']-1, 0, -1):
                if details[p]['base'] == base:
                    dets['prev'] = p
                    break
        else:
            dets['prev'] = None
        if dets['id'] >= len(details):
            details.extend([None] * (dets['id'] - len(details)))
            details.append(dets)
        else:
            details[dets['id']] = dets
    return details


if __name__ == '__main__':
    main('data', 'context')
