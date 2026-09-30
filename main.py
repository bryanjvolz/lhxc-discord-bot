print("Script starting...")
import html
import os
import discord
import pytz
import logging
import requests
from io import BytesIO
from bs4 import BeautifulSoup
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, Button, Select
from dotenv import load_dotenv
from pathlib import Path

dotenv_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

import scraper
import database
from datetime import date, timedelta, datetime, time
from typing import List, Literal

# --- Logging Setup ---
logging.basicConfig(level=logging.ERROR, filename='discord-bot-errors.log', filemode='w', encoding='utf-8',
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Bot Setup ---
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.members = True
intents.message_content = True # Needed for message content

bot = commands.Bot(command_prefix='/', intents=intents)

database.create_tables()

# --- Views ---
class EventView(View):
    def __init__(self, event_id):
        super().__init__(timeout=None)
        self.event_id = event_id

    @discord.ui.button(label='Save', style=discord.ButtonStyle.green, custom_id='save_event')
    async def save_button(self, interaction: discord.Interaction, button: Button):
        if self.event_id:
            try:
                database.save_event(interaction.user.id, self.event_id)
                await interaction.response.send_message('Event saved!', ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f'Error saving event: {e}', ephemeral=True)

class SavedEventView(View):
    def __init__(self, event_id):
        super().__init__(timeout=None)
        self.event_id = event_id

    @discord.ui.button(label='Remove', style=discord.ButtonStyle.red, custom_id='remove_event')
    async def remove_button(self, interaction: discord.Interaction, button: Button):
        if self.event_id:
            try:
                database.remove_saved_event(interaction.user.id, self.event_id)
                await interaction.response.send_message('Event removed!', ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f'Error removing event: {e}', ephemeral=True)

class TimezoneView(View):
    def __init__(self):
        super().__init__(timeout=None)
        us_timezones = [
            ("Eastern", "US/Eastern"),
            ("Central", "US/Central"),
            ("Mountain", "US/Mountain"),
            ("Pacific", "US/Pacific"),
            ("Alaska", "US/Alaska"),
            ("Hawaii", "US/Hawaii"),
        ]
        options = [discord.SelectOption(label=name, value=tz) for name, tz in us_timezones]
        self.add_item(Select(placeholder='Choose your timezone (Default: Eastern)', options=options, custom_id='timezone_select'))

    @discord.ui.select(custom_id='timezone_select')
    async def select_timezone(self, interaction: discord.Interaction, select: Select):
        timezone = select.values[0]
        database.set_user_timezone(interaction.user.id, timezone)
        await interaction.response.send_message(f'Your timezone has been set to {timezone}.', ephemeral=True)


# --- Bot Events ---
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    bot.add_view(EventView(event_id=None))
    bot.add_view(SavedEventView(event_id=None))
    bot.add_view(TimezoneView())
    await bot.tree.sync()
    if not check_for_updates.is_running():
        check_for_updates.start()
    if not daily_notifications.is_running():
        daily_notifications.start()

@bot.event
async def on_command_error(ctx, error):
    logging.error(f'Error in command {ctx.command}: {error}', exc_info=True)
    await ctx.send('An error occurred. Please check the logs.')


# --- Helper Functions ---
def format_event_date(date_str):
    dt_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')

    day = dt_obj.day
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]

    return dt_obj.strftime(f'%B {day}{suffix}, %Y %-I:%M%p').lower()

def format_digest_message(events):
    if not events:
        return None

    first_event = events[0]
    first_image_url = first_event.get('image_url')

    embed = discord.Embed(
        title="Daily Hardcore Digest",
        description="Here are today's new and updated shows:",
        color=discord.Color.red()
    )

    if first_image_url:
        embed.set_thumbnail(url=first_image_url)

    for event in events:
        title_text = html.unescape(event.get('title') or 'No Title')
        permalink = event.get('permalink', '#')
        event_date = event.get('start_date')
        venue = event.get('venue') or 'TBA'
        event_id = event.get('id', 'N/A')

        event_details = f"Date: {format_event_date(event_date) if event_date else 'N/A'}\n"
        event_details += f"Venue: {venue}\n"
        event_details += f"ID: {event_id}"

        embed.add_field(name=f"[{title_text}]({permalink})", value=event_details, inline=False)

    return embed


def format_digest_text(events):
    """Return a simple text-only digest: title, price, date, venue for each event."""
    if not events:
        return "No events to display."

    lines = ["Daily Hardcore Digest:\n"]
    for event in events:
        title = html.unescape(event.get('title') or 'No Title')
        price = event.get('cost') or 'TBA'
        date_str = event.get('start_date') or 'N/A'
        # Format date to a readable string if possible
        try:
            date_val = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            date_formatted = date_val.strftime('%B %-d, %Y %-I:%M%p').lower()
        except Exception:
            date_formatted = date_str

        venue = event.get('venue') or 'TBA'
        if isinstance(venue, dict) and venue.get('name'):
            venue_text = venue.get('name')
        else:
            venue_text = venue

        lines.append(f"{title} — {price} — {date_formatted} — {venue_text}")

    return "\n".join(lines)

def create_event_embed(event):
    description_html = event.get('description') or event.get('excerpt') or ''
    description_text = BeautifulSoup(description_html, 'html.parser').get_text(separator='\n', strip=True)
    title_text = html.unescape(event.get('title') or 'No Title')
    embed = discord.Embed(
        title=title_text,
        url=event.get('permalink'),
        description=description_text,
        color=discord.Color.blue()
    )
    image_url = event.get('image_url')
    if image_url:
        embed.set_thumbnail(url=image_url)

    venue = event.get('venue')
    if venue and isinstance(venue, dict) and venue.get('name'):
        embed.add_field(name="Venue", value=venue['name'])

    if event.get('start_date'):
        embed.add_field(name="Date", value=format_event_date(event['start_date']))
    if event.get('cost'):
        embed.add_field(name="Cost", value=event['cost'])

    categories = event.get('categories')
    if categories and isinstance(categories, list):
        category_names = [cat['name'] for cat in categories if isinstance(cat, dict) and 'name' in cat]
        if category_names:
            embed.add_field(name="Categories", value=", ".join(category_names))

    embed.set_footer(text=f"Event ID: {event['id']}")

    return embed


# --- Slash Commands ---
@bot.tree.command(name='todays-shows', description="Displays all events scheduled for the current day.")
async def todays_shows(interaction: discord.Interaction):
    await interaction.response.defer()
    eastern = pytz.timezone('US/Eastern')
    today = datetime.now(eastern).strftime('%Y-%m-%d')
    events = scraper.get_events_by_date(today)
    if events:
        await interaction.followup.send("Today's Shows:")
        for event in events:
            embed = create_event_embed(event)
            view = EventView(event['id'])
            await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.followup.send("No shows found for today.")

@bot.tree.command(name='this-weeks-shows', description="Displays all events for the current week (Monday to Sunday).")
async def this_weeks_shows(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    eastern = pytz.timezone('US/Eastern')
    today = datetime.now(eastern).date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    all_events = scraper.get_all_events() # Get all events
    events_this_week = []
    if all_events:
        for event in all_events:
            if event.get('start_date'):
                event_date = datetime.strptime(event['start_date'], '%Y-%m-%d %H:%M:%S').date()
                if start_of_week <= event_date <= end_of_week:
                    events_this_week.append(event)

    if not events_this_week:
        await interaction.followup.send("No shows found for this week.", ephemeral=True)
        return

    try:
        dm_channel = interaction.user.dm_channel or await interaction.user.create_dm()
        await dm_channel.send("This Week's Shows:")

        for event in events_this_week:
            embed = create_event_embed(event)
            view = EventView(event['id'])
            await dm_channel.send(embed=embed, view=view)

        await interaction.followup.send("I sent this week's shows to your DMs.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error sending this week's shows DM to user {interaction.user.id}: {e}", exc_info=True)
        await interaction.followup.send(
            "I couldn't send you a DM. Please make sure your privacy settings allow DMs from this bot.",
            ephemeral=True
        )

@bot.tree.command(name='list-shows-date', description="Lists all events on a specific date.")
@app_commands.describe(date_str='The date to search for (YYYY-MM-DD)')
async def list_shows_date(interaction: discord.Interaction, date_str: str):
    await interaction.response.defer()
    try:
        search_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        events = scraper.get_events_by_date(search_date.strftime('%Y-%m-%d'))
        if events:
            await interaction.followup.send(f"Shows on {date_str}:")
            for event in events:
                embed = create_event_embed(event)
                view = EventView(event['id'])
                await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(f"No shows found for {date_str}.")
    except ValueError:
        await interaction.followup.send("Invalid date format. Please use YYYY-MM-DD.")

@bot.tree.command(name='list-all-saved-shows', description="Shows you a list of all the events you have personally saved.")
async def list_all_saved_shows(interaction: discord.Interaction):
    saved_event_ids = database.get_saved_events(interaction.user.id)
    await interaction.response.defer(ephemeral=True)

    if not saved_event_ids:
        await interaction.followup.send("You have no saved shows.", ephemeral=True)
        return

    try:
        dm_channel = interaction.user.dm_channel or await interaction.user.create_dm()
        await dm_channel.send("Your saved shows:")

        found_events = False
        for event_id in saved_event_ids:
            event = scraper.get_event_by_id(event_id)
            if event:
                event = event[0]
                embed = create_event_embed(event)
                view = SavedEventView(event['id'])
                await dm_channel.send(embed=embed, view=view)
                found_events = True

        if not found_events:
            await dm_channel.send("No saved events could be retrieved from the API.")

        await interaction.followup.send("I sent your saved shows to your DMs.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error sending saved shows DM to user {interaction.user.id}: {e}", exc_info=True)
        await interaction.followup.send(
            "I couldn't send you a DM. Please make sure your privacy settings allow DMs from this bot.",
            ephemeral=True
        )

@bot.tree.command(name='list-upcoming-saved-shows', description="Shows you a list of all your upcoming saved events.")
async def list_upcoming_saved_shows(interaction: discord.Interaction):
    saved_event_ids = database.get_saved_events(interaction.user.id)
    await interaction.response.defer(ephemeral=True)

    if not saved_event_ids:
        await interaction.followup.send("You have no upcoming saved shows.", ephemeral=True)
        return

    upcoming_events = []
    for event_id in saved_event_ids:
        event = scraper.get_event_by_id(event_id)
        if event:
            event = event[0]
            event_date = datetime.strptime(event['start_date'], '%Y-%m-%d %H:%M:%S').date()
            if event_date >= date.today():
                upcoming_events.append(event)

    if not upcoming_events:
        await interaction.followup.send("You have no upcoming saved shows.", ephemeral=True)
        return

    try:
        dm_channel = interaction.user.dm_channel or await interaction.user.create_dm()
        await dm_channel.send("Your upcoming saved shows:")

        for event in upcoming_events:
            embed = create_event_embed(event)
            view = SavedEventView(event['id'])
            await dm_channel.send(embed=embed, view=view)

        await interaction.followup.send("I sent your upcoming saved shows to your DMs.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error sending upcoming saved shows DM to user {interaction.user.id}: {e}", exc_info=True)
        await interaction.followup.send(
            "I couldn't send you a DM. Please make sure your privacy settings allow DMs from this bot.",
            ephemeral=True
        )


@bot.tree.command(name='clear-saved', description="Removes all events from your personal saved list.")
async def clear_saved(interaction: discord.Interaction):
    database.clear_saved_events(interaction.user.id)
    await interaction.response.send_message("Your saved events have been cleared.")

@bot.tree.command(name='remove-saved', description="Removes a single event from your saved list.")
@app_commands.describe(event_id='The ID of the event to remove')
async def remove_saved(interaction: discord.Interaction, event_id: int):
    database.remove_saved_event(interaction.user.id, event_id)
    await interaction.response.send_message(f"Event {event_id} has been removed from your saved list.")

@bot.tree.command(name='set-timezone', description="Sets your personal time zone for daily event reminders.")
async def set_timezone(interaction: discord.Interaction):
    await interaction.response.send_message("Please select your timezone from the dropdown.", view=TimezoneView(), ephemeral=True)


# --- Admin Commands ---
@bot.tree.command(name='set-notification-channel', description="Designates a channel for event notifications.")
@app_commands.checks.has_permissions(administrator=True)
async def set_notification_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    database.set_notification_channel(interaction.guild.id, channel.id)
    await interaction.response.send_message(f"Notification channel set to {channel.mention}")

admin_group = app_commands.Group(name="admin", description="Admin-only commands")
bot.tree.add_command(admin_group)

@bot.tree.command(name='lhxc-admin-set-notifications', description="Configure how new event notifications are sent.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    mode="Choose notification mode: 'periodic' (immediate) or 'digest' (daily summary)",
    time_str="(Optional) Time for daily digest (HH:MM in 24-hour, e.g., 08:00). Required for digest mode."
)
async def set_notification_config(
    interaction: discord.Interaction,
    mode: Literal['periodic', 'digest'],
    time_str: str = None
):
    if mode == 'digest' and not time_str:
        await interaction.response.send_message("Digest mode requires a time (HH:MM).", ephemeral=True)
        return

    if time_str:
        try:
            # Validate time_str format
            datetime.strptime(time_str, '%H:%M')
        except ValueError:
            await interaction.response.send_message("Invalid time format. Please use HH:MM (e.g., 08:00).", ephemeral=True)
            return
        database.set_digest_time(interaction.guild.id, time_str)

    database.set_notification_mode(interaction.guild.id, mode)

    settings = database.get_notification_settings(interaction.guild.id)
    await interaction.response.send_message(
        f"Notification mode set to '{settings['notification_mode']}'. "
        f"Digest time: {settings['digest_time'] if settings['notification_mode'] == 'digest' else 'N/A'}.",
        ephemeral=True
    )

@admin_group.command(name="view-notification-config", description="View current new event notification settings.")
@app_commands.checks.has_permissions(administrator=True)
async def view_notification_config(interaction: discord.Interaction):
    settings = database.get_notification_settings(interaction.guild.id)
    await interaction.response.send_message(
        f"Current Notification Mode: '{settings['notification_mode']}'\n"
        f"Daily Digest Time: {settings['digest_time'] if settings['notification_mode'] == 'digest' else 'N/A'}",
        ephemeral=True
    )

@bot.tree.command(name='create-server-event', description='Creates a server event from an event ID.')
@app_commands.describe(event_id='The ID of the event to create a server event from')
@app_commands.checks.has_permissions(administrator=True)
async def create_server_event(interaction: discord.Interaction, event_id: int):
    try:
        event_data = scraper.get_event_by_id(event_id)
        if not event_data:
            await interaction.response.send_message("Event not found.", ephemeral=True)
            return

        event = event_data[0]

        eastern = pytz.timezone('US/Eastern')
        naive_start_time = datetime.strptime(event['start_date'], '%Y-%m-%d %H:%M:%S')
        start_time = eastern.localize(naive_start_time)

        # Set a default end time if not provided, e.g., 2 hours after start time
        end_time = start_time + timedelta(hours=2)

        image_bytes = None
        if event.get('image_url'):
            try:
                headers = {
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
                }
                response = requests.get(event['image_url'], headers=headers)
                response.raise_for_status()
                image_bytes = response.content
            except requests.exceptions.RequestException as e:
                logging.error(f"Error fetching image for event {event_id}: {e}")

        description_html = event.get('description') or event.get('excerpt') or ''
        description_text = BeautifulSoup(description_html, 'html.parser').get_text(separator='\n', strip=True)

        location_text = html.unescape(event.get('venue') or 'TBA')
        title_text = html.unescape(event.get('title') or 'No Title')

        await interaction.guild.create_scheduled_event(
            name=title_text,
            description=description_text,
            start_time=start_time,
            end_time=end_time, # end_time is required for external events
            entity_type=discord.EntityType.external,
            location=location_text,
            privacy_level=discord.PrivacyLevel.guild_only,
            image=image_bytes
        )
        await interaction.response.send_message("Server event created!", ephemeral=True)
    except AttributeError as e:
        logging.error(f"AttributeError in create-server-event for event_id {event_id}: {e}", exc_info=True)
        logging.error(f"Event data: {event_data}")
        await interaction.response.send_message(f"Error creating server event: {e}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error creating server event: {e}", ephemeral=True)
        logging.error(f'Error creating server event: {e}', exc_info=True)

@bot.tree.command(name='view-all-saved-shows', description="[Admin] View all saved shows and who saved them.")
@app_commands.checks.has_permissions(administrator=True)
async def view_all_saved_shows(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    saved_events = database.get_all_saved_events_with_users()

    if not saved_events:
        await interaction.followup.send("No shows have been saved by anyone.", ephemeral=True)
        return

    messages = []
    current_message = "**All Saved Shows & Events**:\n"

    for event_id, user_ids in saved_events.items():
        event_data = scraper.get_event_by_id(event_id)
        event_name = f"Event ID: {event_id} (Not Found)"
        if event_data:
            event_name = event_data[0]['title']

        entry = f"\n- **{html.unescape(event_name)}**\n"

        user_lines = []
        for user_id in user_ids:
            try:
                user = await bot.fetch_user(user_id)
                user_lines.append(f"  - {user.name}")
            except discord.NotFound:
                user_lines.append(f"  - *Unknown User ({user_id})*")

        entry += "\n".join(user_lines)

        if len(current_message) + len(entry) > 2000:
            messages.append(current_message)
            current_message = ""

        current_message += entry

    if current_message:
        messages.append(current_message)

    for i, msg in enumerate(messages):
        if i == 0:
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)

# --- Tasks ---
@tasks.loop(minutes=60)
async def check_for_updates():
    """Checks for new or updated events and posts them to the notification channel."""
    all_events = scraper.get_all_events()
    if not all_events:
        return

    notification_channels = database.get_all_notification_channels()
    if not notification_channels:
        return

    for guild_id, channel_id in notification_channels.items():
        channel = bot.get_channel(channel_id)
        if not channel:
            continue

        settings = database.get_notification_settings(guild_id)
        notification_mode = settings['notification_mode']

        for event in all_events:
            event_id = event['id']
            last_updated_from_api = event.get('modified_date', event['start_date'])
            last_posted = database.get_posted_event(event_id, guild_id)

            if not last_posted:
                # New event
                if notification_mode == 'periodic':
                    embed = create_event_embed(event)
                    view = EventView(event_id)
                    await channel.send("New show just announced!", embed=embed, view=view)
                    database.add_posted_event(event_id, guild_id, last_updated_from_api)
                elif notification_mode == 'digest':
                    database.add_digest_event(guild_id, event_id, event)
            elif last_posted < last_updated_from_api:
                # Event updated
                if notification_mode == 'periodic':
                    embed = create_event_embed(event)
                    view = EventView(event_id)
                    await channel.send("A show has been updated!", embed=embed, view=view)
                    database.add_posted_event(event_id, guild_id, last_updated_from_api)
                elif notification_mode == 'digest':
                    database.add_digest_event(guild_id, event_id, event)

notification_time = time(hour=8, minute=0, tzinfo=pytz.timezone('US/Eastern'))
@tasks.loop(hours=1)
async def daily_notifications():
    """Sends daily notifications to users about their saved events."""
    all_user_ids = database.get_all_users_with_saved_events()
    for user_id in all_user_ids:
        user = await bot.fetch_user(user_id)
        if not user:
            continue

        saved_event_ids = database.get_saved_events(user_id)
        if not saved_event_ids:
            continue

        # Get user's timezone, default to Eastern if not set
        user_timezone_str = database.get_user_timezone(user_id)
        user_timezone = pytz.timezone(user_timezone_str) if user_timezone_str else pytz.timezone('US/Eastern')
        now_in_user_tz = datetime.now(user_timezone)

        for event_id in saved_event_ids:
            event_data = scraper.get_event_by_id(event_id)
            if not event_data:
                continue

            event = event_data[0]
            event_start_date = datetime.strptime(event['start_date'], '%Y-%m-%d %H:%M:%S').date()

            if event_start_date == now_in_user_tz.date():
                notification_date = now_in_user_tz.date().isoformat()
                if database.has_user_notification(user_id, event_id, notification_date):
                    continue

                try:
                    embed = create_event_embed(event)
                    await user.send("You have a saved event today!", embed=embed)
                    database.add_user_notification(user_id, event_id, notification_date)
                except Exception as e:
                    logging.error(f"Error sending notification to user {user_id}: {e}", exc_info=True)

    # --- Daily Digest Logic ---
    eastern = pytz.timezone('US/Eastern')
    now_eastern = datetime.now(eastern)
    current_time_str = now_eastern.strftime('%H:%M')

    # Get all guilds with notification channels configured
    all_guild_notification_channels = database.get_all_notification_channels()
    for guild_id, channel_id in all_guild_notification_channels.items():
        channel = bot.get_channel(channel_id)
        if not channel:
            continue

        settings = database.get_notification_settings(guild_id)
        if settings['notification_mode'] == 'digest' and settings['digest_time'] == current_time_str:
            digest_events = database.get_digest_events(guild_id)
            if digest_events:
                try:
                    digest_text = format_digest_text(digest_events)
                    await channel.send(digest_text)
                    database.clear_digest_events(guild_id)
                except Exception as e:
                    logging.error(f"Error sending digest for guild {guild_id} to channel {channel_id}: {e}", exc_info=True)

# --- Run Bot ---
if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN not found in .env file.")
        print("Please create a .env file and add your bot token.")
        exit()
    bot.run(TOKEN)
