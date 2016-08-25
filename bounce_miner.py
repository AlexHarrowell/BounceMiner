#! /usr/home/stlpartn/bounce_miner/bin/python

from email import message_from_string
from email.mime.multipart import MIMEMultipart, MIMEBase
from email import encoders
from urllib2 import URLError
import mimetypes
import re
import csv
import sys
import imaplib
import smtplib
from argparse import ArgumentParser
from time import clock

t = clock()

fnames = ('referring_customer', 'referred_customer', 'Phone', 'PA Phone', 'PA E-mail', 'IsASecretary')

# usage: python bounce_miner.py inbound_server user password -os outbound_server -ip inbound port -op outbound port -m mailbox -f filename -d destination - n searchpattern -x max_messages -y dryrun, don't delete anything 
# server, user, password are required, mailbox, filename, destination, and searchpattern are optional. outbound_server may be specified if different. -ip defaults to 993/SSL, -op to 465/SSL. if you pass -op 587 it will do STARTTLS. mailbox defaults to INBOX
# filename is a filename or path, defaulting to bounceminer.csv, destination an e-mail address, and searchpattern is an IMAP search pattern like so: ('SUBJECT "Lorem ipsum"'). max_messages tells bounce_miner how many e-mails to process in a batch, default is set to 500. -y is a flag determining whether to delete processed messages or not

argparser = ArgumentParser(description='Extracts contact information from a queue of e-mail')
argparser.add_argument('server', type=str)
argparser.add_argument('user', type=str)
argparser.add_argument('password', type=str)
argparser.add_argument('-os', '--outbound_server', type=str, default=None)
argparser.add_argument('-ip', '--inbound_port', type=int, default=None)
argparser.add_argument('-op', '--outbound_port', type=int, default=None)
argparser.add_argument('-m', '--mailbox', type=str, default='INBOX')
argparser.add_argument('-f', '--filename', type=str, default='./bounceminer.csv')
argparser.add_argument('-d', '--destination', type=str, default=None)
argparser.add_argument('-n', '--searchpattern', type=str, default='ALL')
argparser.add_argument('-x', '--max_messages', type=int, default=500)
argparser.add_argument('-y', '--dryrun', action="store_true", default=False)

phone_parser = re.compile('\+(?:[0-9] ?){6,14}[0-9]') #rough regex to extract phone numbers. doesn't validate them
phone_parser_NANP = re.compile('(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})') # US-style international
phone_parser_EPP = re.compile('\+[0-9]{1,3}\.[0-9]{4,14}(?:x.+)?') # EPP +CCC.NNNNNNNNNNxEEEE style
phone_parser_uk_stupid = re.compile('[0-9]{1,11}') # 11 digit UK phone no
phone_parser_another = re.compile('(\d{3})\D*(\d{3})\D*(\d{4})\D*(\d*)$') # diveintomark's version
email_parser = re.compile('[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}', re.IGNORECASE) 

#RFC-2822 validator regex from http://www.regular-expressions.info/email.html://www.regular-expressions.info/email.html

#this won't work if someone has a hardcoded IP addy in their e-mail address but how likely is that?

phone_hints = [phone_parser, phone_parser_NANP, phone_parser_EPP, phone_parser_uk_stupid, phone_parser_another]

def DetectPhone(payload):
	for parser in phone_hints:
		hits = re.findall(parser, payload) # regex search the body
		if hits == []:
			return None
		else:
			return hits[0]

def DetectSecretary(payload):
	for k in ('PA', 'secretary', 'assistant', 'Secretary', 'Assistant'):
		if k in payload:
			return True

def DetectEmail(payload):
	hits = re.findall(email_parser, payload)
	if hits == []:
		return None
	else:
		return hits[0]

def NotADuplicate(filename, email):
	fn = open(filename, 'r')
	cd = csv.DictReader(fn)
	d = dict([row["referring_customer"] for row in cd])
	fn.close()
	if email in d:
		return False
	else:
		return True
	
def CrunchMessage(rp):
	parsed = message_from_string(rp[1]) # parse the .eml
	output  = {}
	output.setdefault('referred_customer', '')
	output["referring_customer"] = parsed.get('From') # access headers
	if parsed.is_multipart() == True:
		pl = parsed.get_payload(0) # pull the message body
		payload = pl.get_payload(decode=True)
	else:
		payload = parsed.get_payload(decode=True)
	if payload != None:
		referred_email = parsed.get('Reply-To')
		email = referred_email
		parsed_email = DetectEmail(payload) # commence Microsoft dead chicken dance
		if parsed_email: # if the regex parse of the message body finds e-mail
			if referred_email != parsed_email: # we use that email if it's different from the reply-to
				email = parsed_email
		if email != None:
			if email not in output["referring_customer"]:
				p = DetectPhone(payload)
				if DetectSecretary(payload) == True: # heuristic to identify assistants
					output["PA E-mail"] = email
					output["IsASecretary"] = "Yes"
					if p != None:
						output["PA Phone"] = p
				else:
					output["referred_customer"] = email
					output["IsASecretary"] = "No"
					if p != None:
						output["Phone"] = p
				return output
					
		
def MakeMessage(user, destination, mailbox, searchpattern, filename):
	new_message = MIMEMultipart()
	new_message.set_unixfrom('bounce_miner')
	new_message['Subject'] = 'BounceMiner output for ' + mailbox + ', ' + searchpattern
	new_message['From'] = user
	new_message['To'] = destination
	new_message.preamble = 'Output attached in a CSV file.\n'
	ctype, encoding = mimetypes.guess_type(filename)
	maintype, subtype = ctype.split('/', 1)
	m = MIMEBase(maintype, subtype)
	fo = open(filename, 'r')
	m.set_payload(fo.read())
	encoders.encode_base64(m)
	m.add_header('Content-Disposition', 'attachment', filename=filename)
	new_message.attach(m)
	return new_message.as_string()

def SendEmailViaSMTP(user, password, destination, new_message):
	if config['outbound_server']:
		os = config['outbound_server']
	else:
		os = config['server']
	if config['outbound_port']:
		if config['outbound_port'] == 587:
			s = smtplib.SMTP(os, config['outbound_port'])
			s.starttls()
		else:
			s = smtplib.SMTP_SSL(os, config['outbound_port'])
	else:
		s = smtplib.SMTP_SSL(os) # smtplib defaults to 465
	s.login(user, password)
	s.sendmail(user, destination, new_message)
	s.quit()	
	return True

def DeleteProcessedMessages(imap_hookup, messages):
	f = imap_hookup.store(messages, '+FLAGS', r'(\Deleted)')
	imap_hookup.expunge()
	imap_hookup.close()

config = vars(argparser.parse_args())

if config['inbound_port']:
	conn = imaplib.IMAP4_SSL(config['server'], config['inbound_port'])
else:
	conn = imaplib.IMAP4_SSL(config['server']) # imaplib defaults to 993
conn.login(config['user'], config['password'])
conn.select(config['mailbox'])
if config['searchpattern']:
	m = conn.search(None, config['searchpattern'])
	ids = m[1].pop(0)
	messages = ids.split(' ')
	fetch_ids = ','.join(messages[0:config['max_messages']])

else:
	fetch_ids = '0:' + config['max_messages']
	
data = conn.fetch(fetch_ids, '(RFC822)')

output_queue = []
messages_to_delete = []

email = [d for d in data[1] if d not in ('\\r', '\\', ')')]

for rp in email:
	cm = CrunchMessage(rp)
	if cm:
		dupkiller = [oq['referring_customer'] + oq['referred_customer'] for oq in output_queue]
		msgno = rp[0].split(' ')
		messages_to_delete.append(msgno[0])
		if cm['referring_customer'] + cm['referred_customer'] not in dupkiller:	
			output_queue.append(cm)
		

f = open(config['filename'], 'w')
c = csv.DictWriter(f, fnames)

header = dict((n,n) for n in fnames)
c.writerow(header)
c.writerows(output_queue)
f.close()

if config['destination']:
	msg = MakeMessage(config['user'], config['destination'], config['mailbox'], config['searchpattern'], config['filename'])
	SendEmailViaSMTP(config['user'], config['password'], config['destination'], msg)

if config['dryrun'] is False:
	DeleteProcessedMessages(conn, ','.join(messages_to_delete))


t = clock() - t
print 'done in ', t, 'CPU seconds'
