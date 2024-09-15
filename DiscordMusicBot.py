import random
import tracemalloc
import asyncio
import yt_dlp
import discord
from discord.ext import commands

tracemalloc.start()

ffmpeg_options = {
    'options': '-vn',
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

queue = []
tokenstr = "MTEyNzk2MTIwNDA4NjgxMjY3Mg.GHTYu3.KhlhaKRntfhS7ijvdjL1GKEojFdLVvsXXmKawY"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

async def play_after(ctx):
    await after_play(ctx)

def extract_audio_url(url):
    ydl_opts = {'format': 'bestaudio/best', 'verbose': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        audio_url = info['url']
    return audio_url

@bot.command(name="hi")
async def test(ctx):
    await ctx.channel.send("hello")

@bot.command(name="play")
async def play(ctx, *, query):
    voice_channel = ctx.author.voice.channel if ctx.author.voice else None
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if not voice_channel:
        await ctx.send("You are not connected to a voice channel.")
        return

    if voice_client and voice_client.is_playing():
        queue.append(query)
        await ctx.send(f"Song request {query} added to the queue.", view=queuebutton())
        return

    await playsong(ctx, query)

async def playsong(ctx, query):
    if query[:4] == 'http':
        options = {'quiet': True}
        url = query
        with yt_dlp.YoutubeDL(options) as ydl:
            video_info = ydl.extract_info(url, download=False)
            video_title = video_info.get('title')
            duration = video_info.get('duration')
    else:
        search_results, video_title, duration = await search(query)
        if len(search_results) == 0:
            await ctx.send("No search results found.")
            return
        else:
            video_id = search_results['entries'][0]['id']
            url = f'https://www.youtube.com/watch?v={video_id}'

    voice_channel = ctx.author.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    if not voice_client.is_playing():
        audio_url = extract_audio_url(url)
        source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)
        voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_after(ctx), bot.loop))
        await ctx.send(f"Currently playing: {video_title} Duration: {int(duration)//60} minutes and {int(duration)%60} seconds", view=skipbutton())
    else:
        queue.append(query)
        await ctx.send(f"Song request {query} added to the queue.", view=queuebutton())

async def after_play(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if not voice_client.is_playing():
        await check_queue(ctx)

async def search(query: str):
    options = {
        'default_search': 'ytsearch1',
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'extract_flat': 'in_playlist',
        'quiet': True
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        search_results = ydl.extract_info(query, download=False)
    video_id = search_results['entries'][0]['id']
    duration = search_results['entries'][0]['duration']
    with yt_dlp.YoutubeDL(options) as ydl:
        video_info = ydl.extract_info(video_id, download=False)
    video_title = video_info['title']
    return search_results, video_title, duration

async def skipsearch(query: str, interaction):
    options = {
        'default_search': 'ytsearch1',
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'extract_flat': 'in_playlist',
        'quiet': True
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        search_results = ydl.extract_info(query, download=False)
        video_id = search_results['entries'][0]
        duration = search_results['entries'][0]['duration']
        video_title = video_id['title']
        await interaction.response.send_message(f"The song has been skipped to: {video_title}")
        return search_results, video_title, duration

async def check_queue(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if len(queue) > 0:
        next_song = queue.pop(0)
        await playsong(ctx, next_song)
    else:
        if voice_client and not voice_client.is_playing():
            await ctx.send("No songs in queue. Leaving.")
            await voice_client.disconnect()

async def songqueue(interaction):
    if len(queue) == 1:
        await interaction.response.send_message(f"Song in queue: {queue[0]}")
    elif len(queue) == 0:
        await interaction.response.send_message("No songs in the queue.")
    else:
        songs = ', '.join(queue)
        await interaction.response.send_message(f"Songs in queue: {songs}")

async def skip(interaction):
    voice_client = discord.utils.get(bot.voice_clients)

    if len(queue) == 0:
        await interaction.response.send_message("No songs in the queue.")
        return
    else:
        query = queue.pop(0)

        if query[:4] == 'http':
            options = {'quiet': True}
            url = query
            with yt_dlp.YoutubeDL(options) as ydl:
                video_info = ydl.extract_info(url, download=False)
                video_title = video_info.get('title')
                duration = video_info.get('duration')
        else:
            search_results, video_title, duration = await skipsearch(query, interaction)
            video_id = search_results['entries'][0]['id']
            url = f'https://www.youtube.com/watch?v={video_id}'

        voice_client.stop()
        audio_url = extract_audio_url(url)
        source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)
        await interaction.response.send_message(f"Now playing {video_title} Duration: {int(duration)//60} minutes and {int(duration)%60} seconds")
        voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_after(interaction), bot.loop))
        await after_play(interaction)

@bot.command(name="stop")
async def stop(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await voice_client.disconnect()

@bot.command(name="pause")
async def pause(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await ctx.send("Audio paused.")

@bot.command(name="resume")
async def resume(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await ctx.send("Audio resumed.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return ""
    if message.author.name == 'callyp53' or message.author.name=='alfie7489':
        callyp=['nerd','shut up','shush','didnt ask','be quiet please']
        await message.add_reaction("🤓")
        timer=random.randint(0,99)
        if str(timer)[1]=='7':
          picker=random.randint(0,len(callyp)-1)
          mention=message.author.mention
          await message.channel.send(f"{mention}"+" "+callyp[picker])
    if message.content == 'hey hey':
        await message.channel.send(f'Yo {message.author.name}')
    if message.author.name == "danie_is_alive" and message.content == "! it's hacking time":
        a = "".join(str(random.randint(0, 1)) for _ in range(100))
        await message.reply(a)
        await message.reply("https://www.reliasite.com/wp-content/uploads/2019/08/bigstock-Hacker-Using-Laptop-With-Binar-257453926-e1565109796243.jpg")
    await bot.process_commands(message)

class skipbutton(discord.ui.View):
    @discord.ui.button(label="Skip")
    async def on_button_click(self, interaction, button):
        await skip(interaction)

class queuebutton(discord.ui.View):
    @discord.ui.button(label="View Queue")
    async def on_button_click(self, interaction, button):
        await songqueue(interaction)

try:
    bot.run(tokenstr)
except:
    print("Error with token for discord")
