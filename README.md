# BounceMiner
Consumes a queue of bounced e-mail, extracting alternative contact details
The business purpose of this application is to consume bounced e-mail and extract alternative contact details for the individuals identified by the e-mail address in the To: header, so that they can be updated in Salesforce. It consists of a Python script that logs into a specified e-mail account via IMAP4 and retrieves e-mail from a specified folder path, optionally filtering by a search string. It consumes the e-mail and tries to identify alternative e-mail addresses and phone numbers and assistants’ contact details. It then sends e-mail to a specified address containing a CSV file with this information. Usage is via the command line. An example invocation would be:

python /usr/home/stlpartn/bounce_miner/bounce_miner.py outlook.office365.com firstname.lastname@stlpartners.com passwordymcpasswordface -m INBOX/bounces -f bouncedemails.csv -d tim.cook@stlpartners.com 

This would retrieve bounced e-mail from the folder “bounces” in Firstname Lastname’s e-mail account, process it, send the results as a file called bouncedemails.csv to Tim’s address, and delete all successfully processed messages. You can send the e-mail via a different server using different ports and crypto options, specify file names, filter the e-mail by a search string (which can be quite powerful – google “IMAP search pattern”), specify how many messages to process in each batch (useful if the results are overwhelming), and choose whether to delete the messages once processed. You must specify at least the server, user name, and password for it to run at all. 

By default, it uses Office 365’s preferred settings, retrieves from Inbox, processes batches of 500, and deletes processed e-mail. So don’t run the defaults against your inbox.

(that was a design mistake, come to think of it)

When it was operational, I set up the web server to run this command once a week, on Sundays, at 11.05pm. You can do this from the command line by issuing “crontab -e”, or you can use the Web server admin console (look under “advanced” in the left column). The cron job would look like this (i.e. that’s what you’d type into crontab/into the admin web form)

5 23 * * 7 python /usr/home/stlpartn/bounce_miner/bounce_miner.py outlook.office365.com firstname.lastname@stlpartners.com passwordymcpasswordface -m INBOX/bounces -f bouncedemails.csv -d tim.cook@stlpartners.com 

(i.e, five minutes past the 23rd hour, any day of the month, any month, on the seventh day of the week. It’s traditional not to schedule cron jobs for the top of the hour so as not to have too many going off at the same time. Note that anyone with access to crontab will see the password.) 

The full command line interface is given below:

#usage: python bounce_miner.py inbound_server user password -os outbound_server -ip inbound port -op outbound port -m mailbox -f filename -d destination - n searchpattern -x max_messages -y dryrun
#server, user, password are required, mailbox, filename, destination, and searchpattern are optional. outbound_server may be specified if different. -ip defaults to 993/SSL, -op to 465/SSL. if you pass -op 587 it will do STARTTLS. mailbox defaults to INBOX
# filename is a filename or path, defaulting to bounceminer.csv, destination an e-mail address, and searchpattern is an IMAP search pattern like so: ('SUBJECT "Lorem ipsum"'). max_messages tells bounce_miner how many e-mails to process in a batch, default is 500. -y is a flag determining whether to delete processed messages or not and defaults to delete
