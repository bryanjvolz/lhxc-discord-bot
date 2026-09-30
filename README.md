# Louisville Hardcore Discord Bot

This bot is designed to keep your Discord server up-to-date with the latest Shows information from louisvillehardcore.com.

## Features

- **Event Notifications**: Automatically posts messages in an Admin designated channel when new events are added or existing events are updated on the website.
- **Event Information**: Allows users to look up shows for the current day, the upcoming week, or any specific date.
- **Personal Event Lists**: Users can save any events they are interested in, view their saved list, and receive reminders the day of show.
- **Server Event Creation**: Admins can easily create official Discord Server Events from the bot.

## Slash Commands

Here is a list of all available slash commands.

### User Commands

These commands are available to all users.

- **/todays-shows**
  - **Description**: Displays all events scheduled for the current day.

- **/this-weeks-shows**
  - **Description**: Displays all events for the current week (Monday to Sunday).

- **/list-shows-date `date`**
  - **Description**: Lists all events on a specific date in YYYY-MM-DD format.
  - **Example**: `/list-shows-date 2026-10-31`

- **/list-all-saved-shows**
  - **Description**: Shows you a list of all the events you have personally saved with the bot - this is separate from marking 'Interested' on a server event and is private to the user account.

- **/list-upcoming-saved-shows**
  - **Description**: Same as above but only shows that are scheduled to occur in the future.

- **/clear-saved**
  - **Description**: Removes all events from your personal saved list.

- **/remove-saved `event_id`**
  - **Description**: Removes a single event from your saved list. Uses the event ID included at the bottom of show/event posts
  - **Example**: `/remove-saved 9315`

- **/set-timezone**
  - **Description**: Sets your personal time zone for daily event reminders.

### Admin-Only Commands

These commands can only be used by server administrators.

- **/set-notification-channel `channel`**
  - **Description**: Designates a specific channel where the bot will post notifications about new and updated events.
  - **Example**: `/set-notification-channel #general`

- **/create-server-event `event_id`**
  - **Description**: Creates an official Discord Server Event from a show ID.
  - **Example**: `/create-server-event 9315`

- **/view-all-saved-shows**
  - **Description**: Displays a list of all shows that have been saved by users, and which users have saved them.

- **/lhxc-admin-set-notifications `mode` `time_str?`**
  - **Description**: Configure how the bot posts new/updated shows for the server. `mode` must be either `periodic` (post each new/updated show as it is discovered) or `digest` (collect shows and post a single daily digest).
  - **Options**:
    - `mode`: `'periodic'` or `'digest'`
    - `time_str` (optional): required when `mode` is `digest`; the daily digest time in `HH:MM` (24-hour) format, e.g. `08:00`.
  - **Examples**:
    - `/lhxc-admin-set-notifications periodic`
    - `/lhxc-admin-set-notifications digest 08:00`
  - **Notes**: When `digest` is selected the bot will send one plain-text digest message to the configured notification channel at the specified time. The digest format is simple text (no featured image) and lists each show as: `Title — Price — Date — Venue`.

## Setup and Running the Bot

Follow these steps to set up and run the bot for the first time on a new server.

### 1. Prerequisites

Make sure you have Python 3 installed. You can check this by running:
```bash
python3 --version
```

### 2. Get the Code

Place the bot's files on your server. If you're using git, you can clone the repository.

### 3. Create and Activate Virtual Environment

It's recommended to run the bot in a virtual environment.

```bash
# Navigate to the bot's directory
cd /path/to/discord-bot

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate
```

### 4. Install Dependencies

Install the required Python packages using pip and the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

### 5. Configure the Bot Token

Create a `.env` file in the bot's directory and add your Discord bot token.

```
echo "DISCORD_TOKEN='YOUR_BOT_TOKEN_HERE'" > .env
```

Replace `'YOUR_BOT_TOKEN_HERE'` with your actual bot token.

### 6. Configure the source for your shows

In the `.env` file, add the following line to configure the source for your shows (this is just an example, not a working URL) - note that the schema expects something close to the output from The Events Calendar but any API that returns similar data should work.

```
API_BASE_URL='https://louisvillehardcore.com/events-api-v1/'
```

### 7. Run the Bot

Now you can start the bot. Make sure the virtual environment is activated.

```bash
python main.py
```

## Running as a Service (Linux with systemd)

To ensure the bot runs continuously, even after you log out of your server, you should run it as a `systemd` service.

### 1. Create a Service File

Create a new service file for your bot:

```bash
sudo nano /etc/systemd/system/discord-bot.service
```

### 2. Add the Service Configuration

Paste the following configuration into the file. Make sure to replace `/root/discordbot` with the actual path to your bot's directory if it's different.

```ini
[Unit]
Description=Discord Bot for Louisville Hardcore
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/root/discordbot
ExecStart=/root/discordbot/venv/bin/python main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Save the file and exit the editor (in `nano`, press `Ctrl+X`, then `Y`, then `Enter`).

### 3. Manage the Service

Now you can use `systemctl` to manage your bot's service.

```bash
# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the bot to start on boot
sudo systemctl enable discord-bot.service

# Start the bot immediately
sudo systemctl start discord-bot.service

# Check the bot's status
sudo systemctl status discord-bot.service

# Stop the bot
sudo systemctl stop discord-bot.service

# Restart the bot
sudo systemctl restart discord-bot.service
```

### 4. View Logs

### Troubleshooting

**Error: `No such file or directory: '.../venv/bin/python'`**

If you get an error message like this, it means the Python virtual environment may be corrupted or has incorrect paths. To fix this, recreate the virtual environment:

```bash
# Make sure you are in the project directory
cd /path/to/discord-bot

# Deactivate if you are in a broken environment
deactivate

# Remove the old virtual environment
rm -rf venv

# Create a new one
python3 -m venv venv

# Activate the new environment
source venv/bin/activate

# Re-install the dependencies
pip install -r requirements.txt

# Now, run the bot again
python main.py
```
