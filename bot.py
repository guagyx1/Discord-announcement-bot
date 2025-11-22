import discord
from discord import app_commands
from discord.ext import tasks
import asyncio
from datetime import datetime
import pytz
from database import Database
import os
from dotenv import load_dotenv

TIMEZONE_MAP = {
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "GMT": "Europe/London",
    "UTC": "UTC"
}


# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Create database instance
db = Database()

@client.event
async def on_ready():
  """when connects to Discord"""
  print(f"Logged in as {client.user}")
  print(f"Connected to {len(client.guilds)} servers")

  await tree.sync()
  print("Synced slash commands")

  if not check_scheduled_messages.is_running():
    check_scheduled_messages.start()

@tree.command(name="schedule", description="Schedule a message to be sent later")
@app_commands.default_permissions(administrator=True) #only allow administrators to use this command when first added to the server.
@app_commands.describe(channel_id="The channel to send the message in", message="The message to send", send_time="The time to send the message")
async def schedule_message(interaction: discord.Interaction, channel_id: str, message: str, send_time: str, timezone: str):
  """command to schedule message when provided channel id, message, and send time from a user"""

  if len(message) > 2000: #check if message is too long for discord API limit.
    await interaction.response.send_message(
        f"Message too long! Discord's limit is 2000 characters.\n"
        f"Your message is {len(message)} characters long.",
        ephemeral=True
    )
    return

  try:
    
    try:
      timezone_input = timezone.upper()
      if timezone_input in TIMEZONE_MAP:
        timezone = pytz.timezone(TIMEZONE_MAP[timezone_input])
      else:
        timezone = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
      await interaction.response.send_message(f"Invalid timezone '{timezone}'. Please use a valid timezone.\n"
      f"Available timezones: {', '.join(TIMEZONE_MAP.keys())}", ephemeral=True)
      return
    
    default_time = datetime.strptime(send_time, "%Y-%m-%d %H:%M")
    localized_time = timezone.localize(default_time)

    utc_time = localized_time.astimezone(pytz.utc)

    # check if scheduled time is in the future
    if utc_time <= datetime.now(pytz.utc):
      await interaction.response.send_message("The scheduled time must be in the future", ephemeral=True)
      return
    
    # check if channel id is valid
    target_channel = client.get_channel(int(channel_id))
    if not target_channel:
      await interaction.response.send_message("Invalid channel ID", ephemeral=True)
      return

    # add scheduled message to database
    db.add_scheduled_message(
      channel_id=channel_id,
      message_content=message,
      scheduled_time=utc_time,
      author_id=str(interaction.user.id)
    )

    await interaction.response.send_message(
      f"Message added\n"
      f"Channel: {target_channel.mention}\n"
      f"Scheduled time ({timezone.zone}): {localized_time.strftime('%Y-%m-%d %H:%M')}\n"
      f"Message: {message}",
      ephemeral=True
    )

  except ValueError:
    await interaction.response.send_message("Invalid channel ID or time format. Please use /channelid in the receiving channel to get the channel ID, and use YYYY-MM-DD HH:MM (24-hour format)\n Example: 2025-11-19 10:00", 
    ephemeral=True
    )
  
  except Exception as e:
    await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    print(f"Error scheduling message: {str(e)}")
  
@tree.command(name="getchannelid", description="Get the channel ID for the current channel")
async def get_channel_id(interaction: discord.Interaction):
  await interaction.response.send_message(f"Channel ID: {interaction.channel_id}\n Use this ID to schedule messages in this channel", ephemeral=True)

@tree.command(name="view_queue", description="View the queue of scheduled messages")
@app_commands.default_permissions(administrator=True) #only allow administrators to use this command when first added to the server.
async def view_queue(interaction: discord.Interaction):
  try:
    pending_messages = db.get_pending_messages()

    if not pending_messages:
      await interaction.response.send_message("No scheduled messages in the queue", ephemeral=True)
      return
    
    queue_message = "Scheduled Message Queue:\n\n"

    for message in pending_messages:
      message_id, channel_id, message_content, scheduled_time, author_id = message

      channel = client.get_channel(int(channel_id))
      channel_name = channel.mention if channel else f"Channel ID: {channel_id}"

      if isinstance(scheduled_time, str):
        scheduled_time = datetime.fromisoformat(scheduled_time)

      truncated_preview = message_content[:50] + "..." if len(message_content) > 50 else message_content

      queue_message += f"**Message ID:** {message_id}\n"
      queue_message += f"**Channel:** {channel_name}\n"
      queue_message += f"**Scheduled Time:** {scheduled_time.strftime('%Y-%m-%d %H:%M')} UTC\n"
      queue_message += f"**Message Preview:** {truncated_preview}\n\n"
      queue_message += f"**Author:** {author_id}\n\n"
    
    if len(queue_message) > 2000:
      queue_message = queue_message[:1997] + "..."

    await interaction.response.send_message(queue_message, ephemeral=True)
  
  except Exception as e:
    await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    print(f"Error viewing queue: {str(e)}")

@tree.command(name="delete_message", description="Delete a scheduled message from the queue")
@app_commands.default_permissions(administrator=True) #only allow administrators to use this command when first added to the server.
@app_commands.describe(message_id="The ID of the message to delete use /view_queue to find the message ID")
async def delete_message(interaction: discord.Interaction, message_id: int):
  try:
    pending_messages = db.get_pending_messages()
    message_exists = any(msg[0] == message_id for msg in pending_messages)

    if not message_exists:
      await interaction.response.send_message(f"Message with ID {message_id} not found in the queue", ephemeral=True)
      return

    success = db.delete_message(message_id)

    if success:
      await interaction.response.send_message(f"Message with ID {message_id} deleted from the queue", ephemeral=True)
    else:
      await interaction.response.send_message(f"Failed to delete message with ID {message_id}", ephemeral=True)
  
  except Exception as e:
    await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    print(f"Error deleting message: {str(e)}")

@tasks.loop(minutes=1)
async def check_scheduled_messages():
  """minutely background task to check for scheduled messages and send them"""
  current_time = datetime.now(pytz.utc)

  due_messages = db.get_due_messages(current_time)
  
  for message in due_messages:
    message_id, channel_id, message_content, scheduled_time, author_id = message
    try:
      #find channel by id
      target_channel = client.get_channel(int(channel_id))
      if target_channel:
        #send message to channel
        await target_channel.send(message_content)
        print(f"Sent message with id {message_id} to {target_channel.mention} at {scheduled_time}")
        #mark message as sent in database
        db.mark_message_as_sent(message_id)
      
      else:
        print(f"Channel {channel_id} not found for message with id {message_id}")

    except Exception as e:
      print(f"Error sending message {message_id}: {str(e)}")

@check_scheduled_messages.before_loop
async def before_check():
  """wait for bot to be ready"""
  await client.wait_until_ready()
  print("Bot is ready and scheduled message check is starting")

if __name__ == "__main__":
  load_dotenv()
  TOKEN = os.getenv("DISCORD_TOKEN")
  client.run(TOKEN)

  
    
