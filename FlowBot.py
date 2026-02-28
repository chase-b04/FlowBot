import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp
import asyncio
from collections import deque

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# GUILD_ID = 
# MY_GUILD = discord.Object(id=GUILD_ID)

SONG_QUEUES = {}

async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_options):
    with yt_dlp.YoutubeDL(ydl_options) as ydl:
        return ydl.extract_info(query, download=False)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    # test_guild = discord.Object(id=GUILD_ID)
    # await bot.tree.sync(guild=test_guild)
    await bot.tree.sync()
    print(f"{bot.user} is online!")

# @bot.event
# async def on_message(msg):
#     print(msg.guild.id)

@bot.tree.command(name="play", description="Play a song or add it to the queue.")
@app_commands.describe(song_query="Search query")
async def play(interaction: discord.Interaction, song_query: str):
    await interaction.response.defer()

    voice_channel = interaction.user.voice.channel

    if voice_channel is None:
        await interaction.followup.send("You must be in a voice channel.")
    
    voice_client = interaction.guild.voice_client

    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)

    ydl_options = {
        "format": "bestaudio[adr<=96]/bestaudio", #Find all audios, no music videos. If it can't find audio only, it uses best audio
        "noplaylist": True, #self explanatory lol
        "youtube_include_dash_manifest": False, #Omit info from download that we arent interested in
        "youtube_include_hls_manifest": False,
    }

    query = "ytsearch1: " + song_query
    results = await search_ytdlp_async(query, ydl_options)
    tracks = results.get("entries", [])

    if tracks is None:
        await interaction.followup.send("No results found.")
        return
    
    first_track = tracks[0]
    audio_url = first_track["url"]
    title = first_track.get("title", "Untitled")

    guild_id = str(interaction.guild_id)
    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()

    SONG_QUEUES[guild_id].append((audio_url, title))

    if voice_client.is_playing() or voice_client.is_paused():
        await interaction.followup.send(f"Added to queue: **{title}**")
    else:
        await interaction.followup.send(f"Now playing: **{title}**")
        await play_next_song(voice_client, guild_id, interaction.channel)

     
    # ffmpeg_options = {
    #     "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", 
    #     "options": "-vn -c:a libopus -b:a 96k",
    # }

    # source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options, executable="bin\\ffmpeg.exe")
    # voice_client.play(source)


@bot.tree.command(name="skip", description="Skips the current song playing")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipped the current song.")
    else:
        await interaction.response.send_message("Not playing anything to skip.")


@bot.tree.command(name="pause", description="Pause the current song playing.")
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    if voice_client is None: 
        return await interaction.response.send_message("I'm not in a voice channel.")
    
    if not voice_client.is_playing(): #check is something actualy playing
        return await interaction.response.send_message("Nothing is currently playing.")
    
    voice_client.pause() #pause the track
    await interaction.response.send_message("Playback paused!")


@bot.tree.command(name="resume", description="Resume the current song playing.")
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    if voice_client is None: 
        return await interaction.response.send_message("I'm not in a voice channel.")
    
    if not voice_client.is_paused(): #check is something actualy playing
        return await interaction.response.send_message("I'm not paused right now.")
    
    voice_client.resume() #pause the track
    await interaction.response.send_message("Playback resumed!")


@bot.tree.command(name="stop", description="Stop playback and clear the queue.")
async def stop(interaction: discord.Interaction):
    await interaction.response.defer()
    voice_client = interaction.guild.voice_client

    if not voice_client or not voice_client.is_connected(): 
        await interaction.followup.send("I'm not connected to any voice channel.")
        return
    
    guild_id_str = str(interaction.guild_id)
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()

    if voice_client.is_playing() or voice_client.is_paused(): #if something is playing, stop it
        voice_client.stop()
    
    await interaction.followup.send("Stopped playback and disconnected!")
    await voice_client.disconnect() #disconnected from channel and display to user


async def play_next_song(voice_client, guild_id, channel):
    if SONG_QUEUES[guild_id]:
        audio_url, title = SONG_QUEUES[guild_id].popleft()

        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", 
            "options": "-vn -c:a libopus -b:a 96k",
        }

        source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options, executable="ffmpeg")

        def after_play(error):
            if error:
                print(f"Error playing {title}: {error}")
                return
            asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), bot.loop)

        voice_client.play(source, after=after_play)
        asyncio.create_task(channel.send(f"Now playing: **{title}** :3"))

    else:
        await voice_client.disconnect()
        SONG_QUEUES[guild_id] = deque()


bot.run(TOKEN)