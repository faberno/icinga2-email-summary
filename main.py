from config import (send_mail, icinga_host, icinga_apiuser, icinga_apipassword,
                    host_colors, service_colors, subject, from_addr, smtp_host,
                    smtp_port, smtp_username, smtp_password, log_file,
                    log_format, log_level)
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from icinga2apic.client import Client
from jinja2 import Environment, FileSystemLoader, select_autoescape
import logging
import os
from smtplib import SMTP


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


def setup():
    """Sets up the logging, the icinga2 client and the email body template"""
    logging.basicConfig(filename=log_file, filemode='w', format=log_format,
                        level=log_level)
    logging.info('Creating Icinga Email-Summary...')

    # set up the icinga2 client (https://github.com/TeraIT-at/icinga2apic)
    client = Client(icinga_host, icinga_apiuser, icinga_apipassword)

    # set up jinja2 template
    root = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(root, 'templates')
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape()
    )
    mail_template = env.get_template('email.html')

    return client, mail_template


def retrieve_and_clean_api_data(client):
    """
    Retrieves users, hosts, services from the Icinga API.
    Removes everything except the 'attrs' field.
    Tranforms users and hosts to dictionaries to get faster access.
    """
    user_attrs = ['email']
    users = client.objects.list('User', attrs=user_attrs)
    users = {user['name']: user['attrs'] for user in users}

    host_attrs = ['address', 'display_name', 'handled', 'last_check_result',
                  'last_hard_state_change', 'problem', 'vars']
    hosts = client.objects.list('Host', attrs=host_attrs)
    hosts = {host['name']: host['attrs'] for host in hosts}

    service_attrs = ['display_name', 'host_name', 'last_check_result',
                     'last_hard_state_change']
    services = client.objects.list('Service',
                                   filters='match("True", service.problem) && '
                                           'match("False", service.handled) && '
                                           'match("True", service.last_reachable)',
                                   attrs=service_attrs)
    services = [service['attrs'] for service in services]
    services = sorted(services, key=lambda d: d['last_hard_state_change'],
                      reverse=True)
    return users, hosts, services


def sorting(x):
    """
    Hosts are sorted by the change_time of their most recent service problem. If
    the host itself is down, its own change_time is used.
    """
    return x['services'][0]['change_time'] if len(x['services']) > 0 else x[
        'change_time']


def assign_services_to_hosts(services, hosts):
    """
    Hosts are reduced to their essential information, that is then recognized
    by the jinja2 template. Services are assigned to their corresponding host.
    """
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
        problem_hosts.setdefault(service_info['host_name'], default_host)[
            'services'].append(service)

    problem_hosts = list(problem_hosts.values())
    problem_hosts = sorted(problem_hosts, key=sorting, reverse=True)

    return problem_hosts


def assign_hosts_to_users(problem_hosts, users):
    """
    Creates a dictionary of all to be contacted email-addresses and their
    corresponding host problems.
    """
    # keys: user email address, value: hosts for which user should receive emails
    user_notifications = {}

    # assign each user its hosts
    for host in problem_hosts:
        recipients = host['recipients']
        if recipients:
            for recipient in recipients:
                emails = users[recipient].get('email').replace(' ', '').split(',')
                for mail_address in emails:
                    if mail_address:  # filter out empty strings
                        user_notifications.setdefault(mail_address, []).append(host)

    return user_notifications


def send_emails(smtp, user_notifications, mail_template, msg):
    """Creates the email body from the template and sends it."""
    for mail_address, host_list in user_notifications.items():
        try:
            msg['To'] = mail_address
            msg_body = mail_template.render(hosts=host_list,
                                            host_colors=host_colors,
                                            service_colors=service_colors,
                                            host_states=host_states,
                                            service_states=service_states)
            msg.attach(MIMEText(msg_body, 'html'))

            if send_mail:
                smtp.sendmail(from_addr, mail_address, msg.as_string())
        except Exception:
            logging.exception(f'Could not send email to {mail_address}')


def main():
    icinga2_client, mail_template = setup()
    with SMTP(smtp_host, smtp_port) as smtp:
        if smtp_username and smtp_password:
            smtp.login(smtp_username, smtp_password)

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_addr

        users, hosts, services = retrieve_and_clean_api_data(icinga2_client)
        problem_hosts = assign_services_to_hosts(services, hosts)
        user_notifications = assign_hosts_to_users(problem_hosts, users)

        send_emails(smtp, user_notifications, mail_template, msg)


if __name__ == "__main__":
    main()
