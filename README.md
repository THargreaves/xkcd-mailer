# Daily XKCD Mailer

_A python script to scrape a list of all XKCD comics and mail a selection to a given email address_

Write-up can be found [here](http://ttested.com/xkcd-mailer)

## Introduction

This script scrapes the all comics table of explainxkcd.com to keep an up-to-date list of comics. Previous comic details are cached to minimise the number of requests and improve processing time. A selection of comics is then sent to a specified email address. The choosen comics are tracked so that the same comic is never sent twice. Once all comics have been viewed the script will warn the user.

The script is set up for use on GCP. See the README.md included in the project repository (github.com/THargreaves/xckd-mailer) for how to implement this using Google Cloud Functions, Storage, and Scheduler to have this script run every week at 9am (or any other frequency of your choosing). If you wish to use this script locally or on a different cloud platform, you will need to change the 3rd-party imports and any sections surrounding pickle.load()/pickle.dump().

I hope that this scripts acts as a template for similar projects (I'm thinking PHD comics for example). With a bit of knowledge of CSS and RegEx, it shouldn't be too hard to adapt this script for use on other data sources.

Features:

* Can be run from scratch and will scrape all previous comic information

* Will keep track of previously sent comics to avoid repetition

* Will avoid sending you a latter part of a multi-part comic without first

sending the former part(s)

* Will include a reminder link to previous parts when a new part is sent

* Will safely warn the user and exit when comic readership is up-to-date

* Handles repeated URLs by taking latest version

* Handles missing URLs by filling gaps with details of Null

## Integration with GCP

### Step 1 - Setup up a new Gmail account

* [Create a new Gmail account](https://accounts.google.com/signup), keeping track of the email and password

* [Allow less secure apps](https://myaccount.google.com/lesssecureapps) to access the account

### Step 2 - Setup GCP

* [Create an account with GCP](https://cloud.google.com/). No need to enable billing - the free plan will do just fine for this use (see write-up for more details)

* Setup the Cloud SDK by following [this link](https://cloud.google.com/sdk/docs/)

### Step 3 - Create a Cloud Function

* Create a directory on your local computer containing both the `main.py` and `requirements.txt` files.

* Open the Cloud SDK shell and `cd` to this directory

* Run `gcloud functions deploy xkcd-mailer --entry-point main --runtime python37 --trigger-resource mailer-topic --trigger-event google.pubsub.topic.publish --timeout 60s`

* NB: you are free to change the function name (`xkcd-mailer`) and topic name (`mailer-topic`) to anything you would like without needing to alter the script. The timeout can also be adjusted although 60 seconds is more than enough for this use case

### Step 4 - Create a Cloud Schedule

* Run `gcloud scheduler jobs create pubsub weekday_job --schedule "0 9 * * 1-5" --topic mailer-topic --message-body "run mailer script"`

* NB: You may need to enable the Cloud Schedule API for this to run. The console log will give you instructions on how to do this if necessary

* NB: As before, you are free to change the job name (`weekday_job`) and the message body. The topic must match the topic in the cloud function setup

* You may be prompted to create an App Engine. If so, agree to do this and choose a region of europe-west2 (London) (though any other will be fine too)

### Step 5 - Create a Cloud Storage Bucket

* [Visit here](https://console.cloud.google.com/storage/) and create a new bucket

* Name the bucket `mailer_storage` - another name is fine but you will have to change it in the script too

* Use a single region of europe-west2 (or somewhere near your App Engine region)

* Use standard storage class and uniform access controls. Do not change advanced settings

* Optional: upload an existing `details.p` file to the `mailer_storage` bucket to avoid an initial download of all comic information. You can also alter the `history.p` file and upload if you've already read certain comics or want to skip some.

### Step 6 - Test the Cloud Function

* [Visit here](https://console.cloud.google.com/functions/), navigate to the `xkcd_mailer` function, select the 'Testing' tab and click the 'Test the function' button

* If the output is 'OK' then great. Otherwise, you might have made a mistake earlier or the script no longer works. Either way, I'm sorry!