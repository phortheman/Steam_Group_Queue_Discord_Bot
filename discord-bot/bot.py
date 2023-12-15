import discord
from discord.ext import commands
from typing import List
from urllib.parse import urldefrag
import re
import os
from dotenv import load_dotenv
import asyncpg
from collections import defaultdict

URL_PATTERN = re.compile(r"(https?:\/\/store\.steampowered\.com\/app\S+)")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    load_dotenv()
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError(
        "Environment variable 'DISCORD_TOKEN' is not set. Please set it in the operating system or have it in a .env file"
    )

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "Environment variable 'DATABASE_URL' is not set. Please set it in the operating system or have it in a .env file"
    )


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.command()
async def ping(ctx: commands.Context):
    """Test if the bot is connected and reading messages"""
    await ctx.send("Pong")
    print(ctx.message.channel)


@bot.command(help="!add <URL> ...")
async def add(ctx: commands.Context):
    """Add all the URLs provided"""
    added_urls: List[str] = await parse_urls(ctx.message.content)
    result: int = await add_games(
        games=added_urls,
        user_name=str(ctx.author.global_name),
        game_list_name=str(ctx.channel.name),  # type: ignore
        server_id=int(ctx.guild.id),  # type: ignore
        server_name=str(ctx.guild.name),  # type: ignore
        channel_id=int(ctx.channel.id),  # type: ignore
    )
    await ctx.send(f"Adding {result} url(s)")


async def add_games(
    games: list[str],
    user_name: str,
    game_list_name: str,
    server_name: str,
    server_id: int,
    channel_id: int,
) -> int:
    num_of_added_games: int = 0
    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO game_lists (
                        game_list_name, server_name, server_id, channel_id
                    )
                    VALUES (
                        $1, $2, $3, $4
                    )
                    ON CONFLICT (channel_id, server_id) WHERE active = true DO NOTHING;
                    """,
                    game_list_name,
                    server_name,
                    server_id,
                    channel_id,
                )

                for game in games:
                    result: asyncpg.Record = await connection.execute(
                        """
                        WITH list_id AS (
                            SELECT 
                                game_list_id 
                            FROM 
                                game_lists 
                            WHERE 
                                channel_id = $3 
                            AND 
                                server_id = $4 
                            AND 
                                active = true
                        )
                        INSERT INTO games (
                            user_name, game_url, game_list_id
                        ) VALUES (
                            $1, $2, (SELECT game_list_id FROM list_id)
                        )
                        ON CONFLICT (user_name, game_url, game_list_id) WHERE active = true DO NOTHING;
                        """,
                        user_name,
                        game,
                        channel_id,
                        server_id,
                    )
                    num_of_added_games += int(result.split()[-1])
    return num_of_added_games


@bot.command(name="rm", help="!rm <URL> ...")
async def remove(ctx: commands.Context):
    """Finds and removes the URLs specified"""
    remove_list = await parse_urls(ctx.message.content)
    result: int = await remove_urls(
        games=remove_list,
        user_name=str(ctx.author.global_name),
        server_id=int(ctx.guild.id),  # type: ignore
        channel_id=int(ctx.channel.id),  # type: ignore
    )
    await ctx.send(f"Removing {result} games from the list")


async def remove_urls(
    games: list[str], user_name: str, server_id: int, channel_id: int
) -> int:
    num_removed_games: int = 0
    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as connection:
            async with connection.transaction():
                for game in games:
                    result: asyncpg.Record = await connection.execute(
                        """
                        WITH list_id AS (
                            SELECT 
                                game_list_id 
                            FROM 
                                game_lists 
                            WHERE 
                                channel_id = $3 
                            AND 
                                server_id = $4 
                            AND 
                                active = true
                        )
                        UPDATE games
                        SET active = false
                        WHERE user_name = $1
                        AND game_url = $2
                        AND game_list_id = (select game_list_id from list_id)
                        AND active = true
                        ;
                        """,
                        user_name,
                        game,
                        channel_id,
                        server_id,
                    )
                    num_removed_games += int(result.split()[-1])
    return num_removed_games


@bot.command(help="!clear")
async def clear(ctx: commands.Context):
    """Clear the list for the session. Must be ran in a channel with a list"""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server")
        return

    result: int = await clear_games_from_list(
        channel_id=ctx.channel.id, server_id=ctx.guild.id
    )

    await ctx.send(f"Cleared {result} urls")


async def clear_games_from_list(channel_id: int, server_id: int):
    cleared_games: int = 0
    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as connection:
            async with connection.transaction():
                result: asyncpg.Record = await connection.execute(
                    """
                    WITH list_id AS (
                        SELECT 
                            game_list_id 
                        FROM 
                            game_lists 
                        WHERE 
                            channel_id = $1 
                        AND 
                            server_id = $2 
                        AND 
                            active = true
                    )
                    UPDATE games 
                    SET active = false
                    WHERE game_list_id = (SELECT game_list_id FROM list_id);
                    """,
                    channel_id,
                    server_id,
                )
                cleared_games = int(result.split()[-1])
    return cleared_games


@bot.command(name="list", help="!list [session]")
async def list_session_urls(ctx: commands.Context, *args):
    """List all of the URLs in the current session"""
    games = None
    if args:
        if not ctx.guild:
            await ctx.send("This command can only be used in a server")
            return
        thread_name = " ".join(args)
        for thread in ctx.guild.threads:
            if thread.name == thread_name:
                games = await list_specific_session_games(thread.guild.id, thread_name)
                break
        else:
            await ctx.send(f"I cannot find a thread with the name {thread_name}")
    else:
        games = await list_current_session_games(ctx.channel.id, ctx.guild.id)  # type: ignore

    if not games:
        # Something went wrong so there are no games listed
        await ctx.send("This channel doesn't have any lists tied to it")
        return
    elif isinstance(games, str):
        # If games is a string then it is an error message for the user
        await ctx.send(games)
        return
    elif len(games) < 1:
        await ctx.send("No games are in the list!")

    message: str = ""
    for index, (game, users) in enumerate(games.items(), 1):
        message += f"{index}:\t{game}\n\tRecommended by {', '.join(users)}\n"
    await ctx.send(message)


async def list_current_session_games(
    channel_id: int,
    server_id: int,
):
    games: dict[str, list[str]] = defaultdict(list)
    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as connection:
            async with connection.transaction():
                records = await connection.fetch(
                    """
                    WITH list_id AS (
                        SELECT 
                            game_list_id 
                        FROM 
                            game_lists 
                        WHERE 
                            channel_id = $1 
                        AND 
                            server_id = $2 
                        AND 
                            active = true
                    )
                    SELECT user_name, game_url FROM games
                    WHERE game_list_id = (SELECT game_list_id FROM list_id)
                    AND active = true;
                    """,
                    channel_id,
                    server_id,
                )
                for row in records:
                    games[row["game_url"]].append(row["user_name"])
    return games


async def list_specific_session_games(server_id: int, game_list_name: str):
    games: dict[str, list[str]] = defaultdict(list)
    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as connection:
            async with connection.transaction():
                game_list_ids: asyncpg.Record = await connection.fetch(
                    """
                    SELECT game_list_id FROM game_lists
                    WHERE server_id = $1
                    AND game_list_name = $2;
                    """,
                    server_id,
                    game_list_name,
                )
                if len(game_list_ids) > 1:
                    return f"Found {len(game_list_ids)} lists on this server with the same name! Please run this in the channel that the list was created in."
                elif len(game_list_ids) == 0:
                    return (
                        f"Cannot find a list matching '{game_list_name}' on this server"
                    )
                game_list_id = game_list_ids.pop()["game_list_id"]
                results = await connection.fetch(
                    """
                    SELECT user_name, game_url FROM games
                    WHERE game_list_id = $1
                    AND active = true;
                    """,
                    game_list_id,
                )
                for row in results:
                    games[row["game_url"]].append(row["user_name"])
    return games


@bot.command(help="!create <Thread Name>")
async def create(ctx: commands.Context, *args: str):
    """
    Create a thread and use that as a session. This allows
    the text channel to not be flooded with tons of commands
    """
    if isinstance(ctx.channel, discord.TextChannel):
        name = " ".join(args)
        try:
            thread: discord.Thread = await ctx.channel.create_thread(
                name=name,
                message=ctx.message,
                reason="New thread created for URL Queue",
                auto_archive_duration=10080,
            )
            if thread:
                result = await create_game_list(
                    game_list_name=name,
                    server_name=str(thread.guild.name),  # type: ignore
                    server_id=int(thread.guild.id),  # type: ignore
                    channel_id=int(thread.id),  # type: ignore
                )
                if result == 0:
                    await ctx.send(
                        f"Failed to create a new game list with the name '{name}'"
                    )
                    return
            else:
                await ctx.send(f"Failed to create a new thread with the name '{name}'")

            await ctx.send(f"Thread '{name}' created: {thread.mention}")
        except discord.Forbidden:
            await ctx.send("I do not have permission to create a thread")
    else:
        await ctx.send(
            f"This command can only be used in a text channel. {type(ctx.channel)}"
        )


async def create_game_list(
    game_list_name: str, server_name: str, server_id: int, channel_id: int
) -> int:
    result: asyncpg.Record
    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as connection:
            async with connection.transaction():
                result = await connection.execute(
                    """
                    INSERT INTO game_lists (
                        game_list_name, server_name, server_id, channel_id
                    )
                    VALUES (
                        $1, $2, $3, $4
                    )
                    ON CONFLICT (channel_id, server_id) WHERE active = true DO NOTHING;
                    """,
                    game_list_name,
                    server_name,
                    server_id,
                    channel_id,
                )
    return int(result.split()[-1]) if result else 0


@bot.event
async def on_thread_delete(thread: discord.Thread):
    print(
        f"Detected the thread '{thread.name}' was deleted. Seeing if that contains a session so we can remove the queue"
    )
    await remove_session(int(thread.id), int(thread.guild.id))


async def remove_session(channel_id: int, server_id: int):
    async with asyncpg.create_pool(DATABASE_URL) as pool:
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    UPDATE game_lists 
                    SET active = false 
                    WHERE 
                        channel_id = $1 
                    AND 
                        server_id = $2
                    """,
                    channel_id,
                    server_id,
                )


async def parse_urls(message: str) -> List[str]:
    matches = URL_PATTERN.findall(message)
    for i in range(len(matches)):
        matches[i], _ = urldefrag(matches[i])
    return matches


bot.run(DISCORD_TOKEN)
