# tconnectsync

![Python Package workflow](https://github.com/jwoglom/tconnectsync/actions/workflows/python-package.yml/badge.svg)
[![codecov](https://codecov.io/gh/jwoglom/tconnectsync/branch/master/graph/badge.svg)](https://codecov.io/gh/jwoglom/tconnectsync)

Tconnectsync synchronizes data one-way from the Tandem Diabetes t:connect web/mobile application to Nightscout.

If you have a t:slim X2 pump with the companion t:connect mobile Android or iOS app, this will allow your pump bolus and basal data to be uploaded to [Nightscout](https://github.com/nightscout/cgm-remote-monitor) automatically.
Together with a CGM uploader, such as [xDrip+](https://github.com/NightscoutFoundation/xDrip) or the official Dexcom mobile app plus Dexcom Share, this allows your CGM _and_ pump data to be automatically uploaded to Nightscout!

If you have an Android phone, you can use [tconnectpatcher](https://github.com/jwoglom/tconnectpatcher) to modify the t:connect Android app to upload more frequently. By default, pump data is uploaded to Tandem's servers every hour, but with tconnectpatcher the frequency can be brought down to **as low as every five minutes**! This allows for nearly real-time (albeit not fully instantaneous) pump data updates, almost like your pump uploads data directly to Nightscout!

## How It Works

At a high level, tconnectsync works by querying Tandem's undocumented APIs to receive basal and bolus data from t:connect, and then uploads that data as treatment objects to Nightscout. It contains features for checking for new Tandem pump data continuously, and updating that data along with the pump's reported IOB value to Nightscout whenever there is new data.

When you run the program with no arguments, it performs a single cycle of the following, and exits after completion:

* Queries for basal information via the t:connect ControlIQ API.
* Queries for bolus, basal, and IOB data via the t:connect non-ControlIQ API.
* Merges the basal information received from the two APIs. (If using ControlIQ, then basal information appears only on the ControlIQ API. If not using ControlIQ, it appears only on the legacy API.)
* Queries Nightscout for the most recently created Temp Basal object by tconnectsync, and uploads all data newer than that.
* Queries Nightscout for the most recently created Bolus object by tconnectsync, and uploads all data newer than that.

If run with the `--auto-update` flag, then the application performs the following steps:

* Queries an API endpoint used only by the t:connect mobile app which returns an internal event ID, corresponding to the most recent event published by the mobile app.
* Whenever the internal event ID changes (denoting that the mobile app uploaded new data to synchronize), perform all of the above mentioned steps to synchronize data.

## What Gets Synced

Tconnectsync is composed of individual so-called _synchronization features_, which are elements of data that can be
synchronized between t:connect data from the pump and Nightscout.
When setting up tconnectsync, you can choose to configure which synchronization features are enabled and disabled.

Here are a few examples of reasons why you might want to adjust the enabled synchronization features:

* If you currently input boluses into Nightscout manually with comments, then you may wish to _disable the `BOLUS` synchronization feature_ so that there are no duplicated boluses in Nightscout.
* If you want to see Sleep and Exercise Mode data appear in Nightscout, then you may with to _enable the `PUMP_EVENTS` synchronization feature_.

These synchronization features are enabled by default:

* `BASAL`: Basal data
* `BOLUS`: Bolus data

The following synchronization features can be optionally enabled:

* `PUMP_EVENTS`: Events reported by the pump. Includes support for the following:
  * Site/Cartridge Change (occurs for both a site change and a cartridge change)
  * Empty Cartridge/Pump Shutdown (from my investigation, occurs either when the cartridge runs out of insulin OR you hard-shut off the pump)
  * User Suspended (occurs when you manually disable insulin delivery)
  * Exercise Mode (in Nightscout, appears with a start and end time)
  * Sleep Mode (in Nightscout, appears with a start and end time)
* `IOB`: Insulin-on-board data. Only the most recent IOB entry is saved to Nightscout, as an "activity". The Nightscout UI does not currently display this information. In order to read this value, you need to query the Nightscout activity API endpoint. If you don't know what that means, then there is no reason to enable this option.

The following synchronization features are under development, [**but are not yet ready for use**](https://github.com/jwoglom/tconnectsync/issues/16):
* `BOLUS_BG`: Adds BG readings which are associated with boluses on the pump into the Nightscout treatment object. It will determine whether the BG reading was automatically filled via the Dexcom connection on the pump or was manually entered by seeing if the BG reading matches the current CGM reading as known to the pump at that time. Support for this is nearly complete.
* `CGM`: Adds Dexcom CGM readings from the pump to Nightscout as SGV (sensor glucose value) entries. This should only be used in a situation where xDrip/Dexcom Share/etc. is not used and the pump connection to the CGM will be the only source of CGM data to Nightscout. This requires additional testing before it should be considered ready.

To specify custom synchronization features, pass the names of the desired features to the `--features` flag, e.g.:

```bash
$ tconnectsync --features BASAL BOLUS PUMP_EVENTS
```

If you're using tconnectsync-heroku, see [this section in its README](https://github.com/jwoglom/tconnectsync-heroku#Updating-synchronization-features).

## Setup

The following setup instructions assume that you have a Linux, MacOS, or Windows (with WSL) machine that will run the application continuously.

If you've configured Nightscout before, you may be familiar with Heroku. [You can opt to run tconnectsync with Heroku by following these instructions.](https://github.com/jwoglom/tconnectsync-heroku)

**To get started,** you need to choose whether to install the application on your computer via
**Pip**, **Pipenv**, or **Docker**.

After that, you can choose to run the program continuously via **Supervisord**
or on a regular interval with **Cron**.

**NOTE:** If you fork the tconnectsync repository on GitHub, **do not commit your .env file**.
If pushed to GitHub, this will make your tconnect and Nightscout passwords publicly visible and put your data at risk.

## Installation

First, you need to create a file containing configuration values.
The name of this file will be `.env`, and its location will be dependent on which
method of installation you choose.
You should specify the following parameters:

```bash
# Your credentials for t:connect
TCONNECT_EMAIL='email@email.com'
TCONNECT_PASSWORD='password'

# Your pump's serial number (numeric)
PUMP_SERIAL_NUMBER=11111111

# URL of your Nightscout site
NS_URL='https://yournightscouturl/'
# Your Nightscout API_SECRET value
NS_SECRET='apisecret'

# Current timezone of the pump
TIMEZONE_NAME='America/New_York'
```

This file contains your t:connect username and password, Tandem pump serial number (which is utilized in API calls to t:connect), your Nightscout URL and secret token (for uploading data to Nightscout), and local timezone (the timezone used in t:connect). When specifying the timezone, enter a [TZ database name value](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

(Alternatively, these values can be specified via environment variables.)

### Installation via Pip

This is the easiest method to install.

First, ensure that you have **Python 3** with **Pip** installed:

* **On MacOS:** Open Terminal. Install [Homebrew](https://brew.sh/), and then run `brew install python3`
* **On Linux:** Follow your distribution's specific instructions.
  For Debian/Ubuntu based distros, `sudo apt install python3 python3-pip`
* **On Windows:** Install Ubuntu under the [Windows Subsystem for Linux](https://ubuntu.com/wsl).
  Open the Ubuntu Terminal, then run `sudo apt install python3 python3-pip`.
  Perform the remainder of the steps under the Ubuntu environment.

Now install the `tconnectsync` package with pip:

```
$ pip3 install tconnectsync
```

If the pip3 command is not found, run `python3 -m pip install tconnectsync` instead.

After this, you should be able to view tconnectsync's help with:
```
$ tconnectsync --help
usage: tconnectsync [-h] [--version] [--pretend] [-v] [--start-date START_DATE] [--end-date END_DATE] [--days DAYS] [--auto-update] [--check-login]
               [--features {BASAL,BOLUS,IOB,PUMP_EVENTS} [{BASAL,BOLUS,IOB,PUMP_EVENTS} ...]]

Syncs bolus, basal, and IOB data from Tandem Diabetes t:connect to Nightscout.

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --pretend             Pretend mode: do not upload any data to Nightscout.
  -v, --verbose         Verbose mode: show extra logging details
  --start-date START_DATE
                        The oldest date to process data from. Must be specified with --end-date.
  --end-date END_DATE   The newest date to process data until (inclusive). Must be specified with --start-date.
  --days DAYS           The number of days of t:connect data to read in. Cannot be used with --from-date and --until-date.
  --auto-update         If set, continuously checks for updates from t:connect and syncs with Nightscout.
  --check-login         If set, checks that the provided t:connect credentials can be used to log in.
  --features {BASAL,BOLUS,IOB,PUMP_EVENTS} [{BASAL,BOLUS,IOB,PUMP_EVENTS} ...]
                        Specifies what data should be synchronized between tconnect and Nightscout.
```

Move the `.env` file you created to the following folder:

* **MacOS:** `/Users/<username>/.config/tconnectsync/.env`
* **Linux:** `$HOME/.config/tconnectsync/.env`
* **Windows:** `$HOME/.config/tconnectsync/.env` (inside WSL)

```
$ tconnectsync --check-login
```

If you receive no errors, then you can move on to the **Running Tconnectsync Continuously** section.

### Installing with Pipenv

You can run the application using Pipenv.

First, ensure you have Python 3 and pip installed, then install pipenv with `pip3 install pipenv`.

Clone the Git repository for tconnectsync and cd into it with:
```
$ git clone https://github.com/jwoglom/tconnectsync
$ cd tconnectsync
```

Then install tconnectsync's dependencies with `pipenv install`.
Afterwards, you can launch the program with `pipenv run tconnectsync` so long as
you are inside the checked-out tconnectsync folder.

```bash
$ git clone https://github.com/jwoglom/tconnectsync && cd tconnectsync
$ pip3 install pipenv
$ pipenv install
$ pipenv run tconnectsync --help
usage: main.py [-h] [--version] [--pretend] [-v] [--start-date START_DATE] [--end-date END_DATE] [--days DAYS] [--auto-update] [--check-login]
               [--features {BASAL,BOLUS,IOB,PUMP_EVENTS} [{BASAL,BOLUS,IOB,PUMP_EVENTS} ...]]

Syncs bolus, basal, and IOB data from Tandem Diabetes t:connect to Nightscout.

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --pretend             Pretend mode: do not upload any data to Nightscout.
  -v, --verbose         Verbose mode: show extra logging details
  --start-date START_DATE
                        The oldest date to process data from. Must be specified with --end-date.
  --end-date END_DATE   The newest date to process data until (inclusive). Must be specified with --start-date.
  --days DAYS           The number of days of t:connect data to read in. Cannot be used with --from-date and --until-date.
  --auto-update         If set, continuously checks for updates from t:connect and syncs with Nightscout.
  --check-login         If set, checks that the provided t:connect credentials can be used to log in.
  --features {BASAL,BOLUS,IOB,PUMP_EVENTS} [{BASAL,BOLUS,IOB,PUMP_EVENTS} ...]
                        Specifies what data should be synchronized between tconnect and Nightscout.
```


Move the `.env` file you created earlier into the `tconnectsync` folder, and run:

```
$ pipenv run tconnectsync --check-login
```

If you receive no errors, then you can move on to the **Running Tconnectsync Continuously** section.

### Installing with Docker

First, [ensure that you have Docker running and installed](https://docs.docker.com/get-started/#download-and-install-docker).

To download and run the prebuilt Docker image from GitHub Packages:

```bash
$ docker pull ghcr.io/jwoglom/tconnectsync/tconnectsync:latest
$ docker run ghcr.io/jwoglom/tconnectsync/tconnectsync --help
```

Move the `.env` file you created earlier into the current folder, and run:

```
$ docker run tconnectsync --check-login
```

If you receive no errors, then you can move on to the **Running Tconnectsync Continuously** section.


#### Building Locally

To instead build the image locally and launch the project:

```bash
$ git clone https://github.com/jwoglom/tconnectsync
$ cd tconnectsync
$ docker build -t tconnectsync .
$ docker run tconnectsync --help
```

Move the `.env` file you created earlier into this folder, and run:
```
$ docker run --env-file=.env tconnectsync --check-login
```

**NOTE:** If using the `--env-file` option to `docker run`, you may need to remove all quotation marks (`'` and `"`s) around values in the `.env` file for Docker to propagate the variables correctly.

If you receive no errors, then you can move on to the **Running Tconnectsync Continuously** section.

## Running Tconnectsync Continuously

You most likely want tconnectsync to run either continuously (via the auto-update
feature) or on a regular interval (via cron).

The supervisord approach is recommended for simplicity.

### Running with Supervisord (recommended)
To configure tconnectsync to run continuously in the background using its `--auto-update` feature, you can use a tool such as Supervisord.

First, install supervisord via your Linux system's package manager.
(For example, for Ubuntu/Debian-based systems, run `sudo apt install supervisor`)

Supervisord is configured by creating a configuration file in `/etc/supervisor/conf.d`.

Here is an example `tconnectsync.conf` which you can place in that folder:

```
[program:tconnectsync]
command=/path/to/tconnectsync/run.sh
directory=/path/to/tconnectsync/
stderr_logfile=/path/to/tconnectsync/stderr.log
stdout_logfile=/path/to/tconnectsync/stdout.log
user=<your username>
numprocs=1
autostart=true
autorestart=true
```

In order to create a `run.sh` file, see the section below which aligns with your
choice of installation method.

After the configuration file has been created, ensure that Supervisor is running
and configured to start on boot:

```bash
$ sudo systemctl daemon-reload
$ sudo systemctl start supervisord
$ sudo systemctl enable supervisord
```

Then use the `supervisorctl` command to manage the status of the tconnectsync program:

```bash
$ sudo supervisorctl status
tconnectsync                     STOPPED
$ sudo supervisorctl start tconnectsync
$ sudo supervisorctl status
tconnectsync                     RUNNING   pid 18810, uptime 00:00:05
```

You can look at the `stderr.log` and `stdout.log` files to check that tconnectsync
is running and has started up properly:
```bash
$ tail -f /path/to/tconnectsync/stdout.log
Starting auto-update between 2021-09-30 00:06:39.942273 and 2021-10-01 00:06:39.942273
2021-10-01 00:06:39 DEBUG    Instantiating new AndroidApi
2021-10-01 00:06:39 DEBUG    Starting new HTTPS connection (1): tdcservices.tandemdiabetes.com:443
2021-10-01 00:06:40 DEBUG    https://tdcservices.tandemdiabetes.com:443 "POST /cloud/oauth2/token HTTP/1.1" 200 404
2021-10-01 00:06:40 INFO     Logged in to AndroidApi successfully (expiration: 2021-10-01T08:06:40.362Z, in 7 hours, 59 minutes)
```

#### With Pip Installation

In the `tconnectsync.conf`, you should set `/path/to/tconnectsync` to the folder
containing your `.env` file.

Create a `run.sh` file containing:

```bash
#!/bin/bash

tconnectsync --auto-update
```

#### With Pipenv Installation

In the `tconnectsync.conf`, you should set `/path/to/tconnectsync` to the folder
where you checked-out the GitHub repository.

An example `run.sh` which launches tconnectsync within its pipenv-configured virtual environment:

```bash
#!/bin/bash

PIPENV=/home/$(whoami)/.local/bin/pipenv
VENV=$($PIPENV --venv)

source $VENV/bin/activate

cd /path/to/tconnectsync
exec python3 -u main.py --auto-update
```

#### With Docker Installation

In the `tconnectsync.conf`, you should set `/path/to/tconnectsync` to the folder
where you checked-out the GitHub repository.

An example `run.sh` if you installed tconnectsync via the GitHub Docker Registry:

```bash
#!/bin/bash

docker run ghcr.io/jwoglom/tconnectsync/tconnectsync --auto-update
```

An example `run.sh` if you built tconnectsync locally:

```bash
#!/bin/bash

docker run tconnectsync --auto-update
```

### Running with Cron

If you choose not to run tconnectsync with `--auto-update` continuously,
you can instead run it at a periodic interval (i.e. every 15 minutes) by just
invoking tconnectsync with no arguments via cron.

If using Pipenv or a virtualenv, make sure that you either prefix the call to main.py with `pipenv run` or source the `bin/activate` file within the virtualenv, so that the proper dependencies are loaded. If not using any kind of virtualenv, you can instead just install the necessary dependencies as specified inside Pipfile globally.

An example configuration in `/etc/crontab` which runs every 15 minutes:

```bash
# m         h  dom mon dow user   command
0,15,30,45  *  *   *   *   root   /path/to/tconnectsync/run.sh
```

You can use one of the same `run.sh` files referenced above, but remove the `--auto-update` flag since you are handling the functionality for running the script periodically yourself.

## Tandem APIs

This application utilizes three separate Tandem APIs for obtaining t:connect data, referenced here by the identifying part of their URLs:

* [**controliq**](https://github.com/jwoglom/tconnectsync/blob/master/tconnectsync/api/controliq.py) - Contains Control:IQ related data, namely a timeline of all Basal events uploaded by the pump, separated by type (temp basals, algorithmically-updated basals, or profile-updated basals).
* [**android**](https://github.com/jwoglom/tconnectsync/blob/master/tconnectsync/api/android.py) - Used internally by the t:connect Android app, these API endpoints were discovered by reverse-engineering the Android app. Most of the API endpoints are used for uploading pump data, and tconnectsync uses one endpoint which returns the most recent event ID uploaded by the pump, so we know when more data has been uploaded.
* [**tconnectws2**](https://github.com/jwoglom/tconnectsync/blob/master/tconnectsync/api/ws2.py) - More legacy than the others, this seems to power the bulk of the main t:connect website. It is used to retrieve a CSV export of non-ControlIQ basal data, as well as bolus and IOB data. (I haven't found any mentions of bolus or IOB data in the Control:IQ-specific API.)

I have only tested tconnectsync with a Tandem pump set in the US Eastern timezone. Tandem's (to us, undocumented) APIs are [a bit loose with timezones](https://github.com/jwoglom/tconnectsync/blob/master/tconnectsync/parser.py#L15), so please let me know if you notice any timezone-related bugs.
## Backfilling t:connect Data

To backfill existing t:connect data in to Nightscout, you can use the `--start-date` and `--end-date` options. For example, the following will upload all t:connect data between January 1st and March 1st, 2020 to Nightscout:

```
python3 main.py --start-date 2020-01-01 --end-date 2020-03-01
```

In order to bulk-import a lot of data, you may need to use shorter intervals, and invoke tconnectsync multiple times. Tandem's API endpoints occasionally return invalid data if you request too large of a data window which causes tconnectsync to error out mid-way through.

One oddity when backfilling data is that the Control:IQ specific API endpoints return errors if they are queried before you updated your pump to utilize Control:IQ. This is [partially worked around in tconnectsync's code](https://github.com/jwoglom/tconnectsync/blob/d841c3811aeff3671d941a7d3ff4b80cce6a219e/main.py#L238), but you might need to update the logic if you did not switch to a Control:IQ enabled pump immediately after launch.
