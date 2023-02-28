import asyncio
import os
import time
import traceback
import aiocqhttp
import pytz
import aiofiles
import httpx
from aiocqhttp import CQHttp, Event, Message
import ujson
import yaml
import datetime

bot = CQHttp(message_class=Message)

replay2mode = {
    "classic": "FFA",
    "2v2": "2v2",
    "1v1": "1v1",
    "custom": "custom"
}

mode2rank = {
    "FFA": "ffa",
    "2v2": "2v2",
    "1v1": "duel"
}

if os.path.exists("data.yml"):
    with open("data.yml", "r") as f:
        data = yaml.load(f, yaml.CLoader)
else:
    data = {'enabled-groups': {701924646: {'enabled': True}, 865047476: {'enabled': True}}, 'followed-users': {
        '-Sheou-': {'enabled': True, 'last-seen': 1677389229137, 'rank': {'1v1': 0, '2v2': 0, 'FFA': 0},
                    'star': {'1v1': 0.0, '2v2': 0.0, 'FFA': 0.0}},
        'VVQ3R': {'enabled': True, 'last-seen': 1677590586940, 'rank': {'1v1': 0, '2v2': 0, 'FFA': 0},
                  'star': {'1v1': 0.0, '2v2': 0.0, 'FFA': 0.0}},
        'vvq3r': {'enabled': True, 'last-seen': 1677582598144, 'rank': {'1v1': 0, '2v2': 0, 'FFA': 0},
                  'star': {'1v1': 0.0, '2v2': 0.0, 'FFA': 0.0}}}, 'super-users': [1259435707]}


async def get_replays(username: str) -> list:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://generals.io/api/replaysForUsername?u={username}&offset=0&count=200")
    return ujson.loads(resp.content)


async def get_stars_and_ranks(username: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://generals.io/api/starsAndRanks?u={username}")
    return ujson.loads(resp.content)


async def is_validate_username(username: str) -> bool:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://generals.io/api/validateUsername?u={username}")
    return resp.content == b'true'


async def is_supporter(username: str) -> bool:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://generals.io/api/isSupporter?u={username}")
    return resp.content == b'true'


def is_user_followed(username):
    user = data["followed-users"].get(username)
    if not user:
        return False
    return user["enabled"]


def is_group_enabled(group_id):
    group = data["enabled-groups"].get(group_id)
    if not group:
        return False
    return group["enabled"]


async def render(username, replay_json):
    start_time = datetime.datetime.fromtimestamp(replay_json[0]["started"] // 1000, tz=pytz.timezone("Etc/GMT-8"))
    mode = replay2mode[replay_json[0]["type"]]
    replay_id = replay_json[0]["id"]
    end_time = datetime.datetime.fromtimestamp(int(time.time()), tz=pytz.timezone("Etc/GMT-8"))
    used_time = end_time - start_time
    message = ""
    message += f"{username}刚刚结束了一场对局\n"
    message += f"模式: {mode}\n"
    if mode != "custom":
        r = await get_stars_and_ranks(username)

        now_star = round(float(r['stars'][mode2rank[mode]] or 0), 1)
        now_rank = r['ranks'][mode2rank[mode]] or 0

        if now_rank < data["followed-users"][username]["rank"][mode]:
            rank_icon = "🔼"
        elif now_rank == data["followed-users"][username]["rank"][mode]:
            rank_icon = "⏹"
        else:
            rank_icon = "🔽"

        if now_star > data["followed-users"][username]["star"][mode]:
            star_icon = "🔼"
        elif now_star == data["followed-users"][username]["star"][mode]:
            star_icon = "⏹"
        else:
            star_icon = "🔽"
        data["followed-users"][username]["rank"][mode] = now_rank
        data["followed-users"][username]["star"][mode] = now_star
        message += f"⭐  {now_star} &#91;{star_icon}&#93; 🏆 #{now_rank} &#91;{rank_icon}&#93;\n"

    message += f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    message += f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    message += f"用时: {used_time}\n"
    message += f"回放: https://generals.io/replays/{replay_id}"
    return message


async def send_all(message):
    for group, group_data in data["enabled-groups"].items():
        if group_data["enabled"]:
            # try:
            await bot.send_group_msg(group_id=group, message=message)
            # except aiocqhttp.exceptions.ApiNotAvailable:
            #     pass


async def poll_user(name):
    while is_user_followed(name):
        try:
            r = await get_replays(name)
            bot.logger.debug(r[0]["started"], data["followed-users"][name]["last-seen"])
            if r[0]["started"] != data["followed-users"][name]["last-seen"]:
                msg = await render(name, r)
                await send_all(message=msg)
                data["followed-users"][name]["last-seen"] = r[0]["started"]
        except:
            traceback.print_exc()


# @bot.on_message('private')
# async def priv(event: Event):
#     print(event.message)
#     print(event.user_id)
#     await bot.send_private_msg(user_id=event.user_id, message=event.message)


@bot.on_message('group')
async def pub(event: Event):
    if is_group_enabled(event.group_id):
        message = str(event.message)
        if message.startswith("follow") and len(message) > 7:
            username = message[7:]
            if username in data["followed-users"]:
                data["followed-users"][username]["enabled"] = True
                bot.loop.create_task(poll_user(username))
                await bot.send(event, message="关注成功")
            else:
                user_exist = await is_validate_username(username)
                if user_exist:
                    replay = await get_replays(username)
                    if len(replay) > 0:
                        data["followed-users"][username] = {'enabled': True, 'last-seen': 0,
                                                            'rank': {'1v1': 0, '2v2': 0, 'FFA': 0},
                                                            'star': {'1v1': 0.0, '2v2': 0.0, 'FFA': 0.0}}
                        bot.loop.create_task(poll_user(username))
                        await bot.send(event, message="关注成功")
                    else:
                        await bot.send(event, "用户不存在或已改名")
                else:
                    await bot.send(event, message="用户不存在或已改名")
        elif message.startswith("unfollow") and len(message) > 9:
            username = message[9:]
            if username in data["followed-users"]:
                data["followed-users"][username]["enabled"] = False
                await bot.send(event, message="取关成功")
            else:
                await bot.send(event, message="未关注该用户")


# @bot.on_message('group')
# async def publ(event: Event):
#     print(event.message)
#     print(event.user_id)
#     await bot.send_private_msg(user_id=event.user_id, message=event.message)

async def main_coroutine():
    pass


async def save_data():
    while True:
        await asyncio.sleep(1)
        async with aiofiles.open("data.yml", "w") as f:
            await f.write(yaml.dump(data, Dumper=yaml.CDumper))


@bot.on_websocket_connection
async def start_up(event):
    loop = bot.loop
    loop.create_task(main_coroutine())
    loop.create_task(save_data())
    for user in data["followed-users"]:
        loop.create_task(poll_user(user))


bot.run("127.0.0.1", 8080)
