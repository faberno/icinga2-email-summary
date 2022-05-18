from config import (send_mail, icinga_host, icinga_apiuser, icinga_apipassword, host_colors,
                    service_colors, smtp_host, from_addr, log_file, log_format, log_level)
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from icinga2apic.client import Client
from jinja2 import Environment, FileSystemLoader, select_autoescape
import logging
import os
import smtplib


def get_attrs(object_list, to_dict=True):
    """Retrieve 'attrs' field from every object and, if wanted, convert to a dictionary"""
    if to_dict:
        new_dict = {}
        for object in object_list:
            new_dict[object['name']] = object['attrs']
        return new_dict
    new_list = []
    for object in object_list:
        new_list.append(object['attrs'])
    return new_list


def notifications_recipients(host):
    """Retrieve all users of a host, that want to receive emails"""
    vars = host.get('vars', {})
    if vars is None:
        return None
    return vars.get('notification', {}).get('mail', {}).get('users')


def timestamp2str(timestamp):
    """Convert Unix timestamp to a string"""
    time = datetime.fromtimestamp(timestamp)
    time_format = "%H:%M" if time.date() == datetime.today().date() else "%d-%b-%y"
    return time.strftime(time_format)


host_states = {0: "UP",
               1: "UP",
               2: "DOWN",
               3: "DOWN"}

service_states = {0: "OK",
                  1: "WARNING",
                  2: "CRITICAL",
                  3: "UNKNOWN"}

# set up logging
logging.basicConfig(filename=log_file, filemode='w', format=log_format, level=log_level)
logging.info('Creating Icinga Email-Summary...')

# set up jinja2 template
root = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(root, 'templates')
env = Environment(
    loader=FileSystemLoader(templates_dir),
    autoescape=select_autoescape()
)
mail_template = env.get_template('email.html')

# set up smtp connection and message
if send_mail:
    smtp = smtplib.SMTP(smtp_host)
msg = MIMEMultipart('alternative')
msg['Subject'] = "Icinga Summary"
msg['From'] = from_addr

# set up the icinga2 client (https://github.com/TeraIT-at/icinga2apic)
client = Client(icinga_host, icinga_apiuser, icinga_apipassword)

# retrieve users, hosts, services from the Icinga API
# remove everything except the 'attrs' field
# transform users and hosts to dictionaries to get faster access
users = client.objects.list('User')
users = get_attrs(users)

hosts = client.objects.list('Host')
hosts = get_attrs(hosts)

services = client.objects.list('Service',
                               filters='match("True", service.problem) && '
                                       'match("False", service.handled) && '
                                       'match("True", service.last_reachable)')
services = get_attrs(services, to_dict=False)
services = sorted(services, key=lambda d: d['last_hard_state_change'], reverse=True)

# hosts are reduced to their essential information, that is then recognized by the jinja2 template
# services are assigned to their corresponding host
problem_hosts = {}
for host_name, host_info in hosts.items():
    if host_info['problem'] and not host_info['handled']:
        timestamp = host_info['last_hard_state_change']
        time_str = timestamp2str(timestamp)
        problem_hosts[host_name] = {'name': host_name,
                                    'address': host_info['address'],
                                    'state': host_info['last_check_result']['state'],
                                    'recipients': notifications_recipients(host_info),
                                    'change_time': timestamp,
                                    'change_time_str': time_str,
                                    'output': host_info['last_check_result']['output'],
                                    'services': []}
for service_info in services:
    service_host = hosts[service_info['host_name']]
    timestamp = service_info['last_hard_state_change']
    time_str = timestamp2str(timestamp)
    service = {'name': service_info['display_name'],
               'state': service_info['last_check_result']['state'],
               'change_time': timestamp,
               'change_time_str': time_str,
               'output': service_info['last_check_result']['output'],
               'services': []}
    default_host = {'name': service_host['display_name'],
                    'address': service_host['address'],
                    'state': service_host['last_check_result']['state'],
                    'recipients': notifications_recipients(service_host),
                    'change_time_str': timestamp2str(service_host['last_hard_state_change']),
                    'output': None,
                    'services': []}
    # if host does not exist yet in host_problems, create a new one and add the service
    problem_hosts.setdefault(service_info['host_name'], default_host)['services'].append(service)


# transform problem_hosts to a list and sort them
# hosts are sorted by the change_time of their most recent service problem
# if the host itself is down, its own change_time is used
def sorting(x):
    return x['services'][0]['change_time'] if len(x['services']) > 0 else x['change_time']


problem_hosts = list(problem_hosts.values())
problem_hosts = sorted(problem_hosts, key=sorting, reverse=True)

# keys: user email address, value: hosts for which user should receive emails
user_notifications = {}

# assign each user its hosts
for host in problem_hosts:
    host_name = host['name']
    recipients = host['recipients']
    if recipients:
        for recipient in recipients:
            emails = users[recipient].get('email').replace(' ', '').split(',')
            for mail_address in emails:
                if mail_address:  # filter out empty strings
                    user_notifications.setdefault(mail_address, []).append(host)

# send emails
for mail_address, host_list in user_notifications.items():
    try:
        msg['To'] = mail_address
        msg_body = mail_template.render(hosts=host_list, host_colors=host_colors,
                                        service_colors=service_colors, host_states=host_states,
                                        service_states=service_states)
        msg.attach(MIMEText(msg_body, 'html'))

        if send_mail:
            smtp.sendmail(from_addr, mail_address, msg.as_string())
    except Exception as e:
        logging.exception(f'Could not send email to {mail_address}')

if send_mail:
    smtp.quit()
