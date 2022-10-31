# icinga2-email-summary


<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

This Python script uses the Icinga2 API to retrieve all problematic hosts and services and bundles
this information in one email, that can then be sent to the assigned users. The native Icinga2
emails in contrast, are sent individually for every configured event (e.g. a host goes down).

<!-- GETTING STARTED -->
## Getting Started

### Prerequisites
Make sure that Python3 and pip are installed on your machine.

### Installation

To get started first clone this repository to the wanted location
```sh
git clone https://github.com/faberno/icinga2-email-summary.git
cd icinga2-email-summary
```

Install the required packages 
* [icinga2apic](https://github.com/TeraIT-at/icinga2apic): An Icinga2 client to handle the API requests
* [Jinja2](https://jinja.palletsprojects.com/): A templating engine to automatically create the html for the email
```sh
pip install -r requirements.txt
```

<!-- USAGE EXAMPLES -->
## Usage

### Configuration
Rename config.py.sample to config.py and configure it to your needs
* send_mail (boolean): If false, no emails will be sent (recommended for testing)
* use_whitelist (boolean): If true, only addresses that have been specified in the whitelist.txt can receive emails (recommended for testing).  
whitelist.txt should contain one address per row.
```text
user1@example.com
user2@example.com
```
* <strong>icinga_host</strong> (string): URL of the Icinga2 host.
* <strong>icinga_apiuser</strong> (string): Name of API User, which the client will use. Ideally, this user should have read rights only.
* <strong>icinga_apipassword</strong> (string): Password of the API User.
* <strong>subject</strong> (string): The subject of the sent emails.
* <strong>from_addr</strong> (string): The email address the messages are sent from.
* <strong>smtp_host</strong> (string): URL of the SMTP server ('localhost' if on the same server).
* <strong>smtp_port</strong> (integer): Port of the SMTP host (0 if host is 'localhost').: Username for the SMTP server (not needed if running )
* <strong>smtp_username</strong> & <strong>smtp_password</strong> (string): Credentials of the SMTP user (not needed íf this script runs on the SMTP server)
* <strong>log_file</strong> (string): Path to the log file.
* <strong>log_format</strong> (string): Formatting of the log messages (see [here](https://docs.python.org/3/library/logging.html#logrecord-attributes) for details)
* <strong>log_level</strong> (level): [Logging level](https://docs.python.org/3/library/logging.html#logging-levels) provided by the built-in logging library.

As can be seen above, it makes sense to have Icinga, SMTP and this script running on the same machine.

### Execution

After making sure main.py has execution permissions, it can be executed by 
```sh
python3 path/to/main.py
```

To schedule an automatic execution, you could use crontab. The below example will execute the script Monday to Friday at 8 and 16 o'clock.
```text
0 8,16 * * 1-5 python3 path/main.py
```


<!-- LICENSE -->
## License




<!-- CONTACT -->
## Contact

