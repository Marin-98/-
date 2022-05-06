from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent, Message, MessageSegment
from models.group_member_info import GroupInfoUser
from utils.utils import get_message_text, is_number, UserBlockLimiter
from models.bag_user import BagUser
import random
from nonebot.permission import SUPERUSER
from nonebot.params import CommandArg
from plugins.nonebot_plugin_htmlrender import text_to_pic
from utils.utils import get_bot
# import plugins.cardrule as cr
import time

__zx_plugin_name__ = "唬牌"
__plugin_usage__ = """
usage：
    第一位玩家发起活动，唬牌
    接受21点赌局，指令：坐下
    人齐后开局，指令：开场
    1.使用“唬牌”开始游戏
    2.使用“坐下”参与游戏
    3.当入场满3人后使用“开场”建立对局
    4.第一个入场的玩家拥有出牌权，使用“出牌（牌编号）一个空格（牌编号）.... as (标牌)“命令出牌
    5.拥有出牌权的玩家可以使用as确定标牌，其他玩家只能跟随标牌出牌
    6.其他玩家使用“跟 （牌编号）空格（牌编号）....”命令跟牌，玩家可以出任意一张或多张牌（不超过6张），所跟的牌均视为当作标牌打出
    7.当玩家对上一玩家出牌是否使诈作出怀疑时，可使用“跟 check”进行查验，查验成功则获得出牌权，查验失败则将获得牌池中积累的牌,反之被查验的人得到牌权或获得牌池的牌
    8.当玩家无法出牌应对时，可使用“pass”命令，连续两次pass，将清空牌池，被pass的玩家获得出牌权
    9.当有一方出完所有的牌，并且无人check或check成功时获得胜利，游戏结束
""".strip()
__plugin_des__ = "真寻小赌场-唬牌"
__plugin_cmd__ = ["唬牌"]
__plugin_type__ = ("真寻小赌场",)
__plugin_version__ = 0.10
__plugin_author__ = "Marin"
__plugin_settings__ = {
    "level": 5,
    "default_status": True,
    "limit_superuser": False,
    "cmd": ["唬牌"],
}

startgame = on_command("唬牌", aliases={"唬牌"}, priority=5, block=True)
sit = on_command("坐下", priority=5, block=True)
loading = on_command("开场", priority=5, block=True)
chupai = on_command("出牌", priority=5, block=True)
follow = on_command("跟", priority=5, block=True)
################################################################################################
heap = []
cards = []


# 打印扑克牌带花色
def num2card(num):
    if num < 13:
        card = "♠"
    elif num < 26:
        card = "♥"
    elif num < 39:
        card = "♣"
    elif num < 52:
        card = "♦"
    if num > 51:
        card = "Joker"
    elif num % 13 == 0:
        card += "K"
    elif num % 13 == 1:
        card += "A"
    elif num % 13 == 11:
        card += "J"
    elif num % 13 == 12:
        card += "Q"
    elif num % 13 < 11 and num % 13 > 1:
        card += str(num % 13)
    return card


# 初始化扑克牌
def initcard():
    global heap
    for i in range(0, 13):
        for j in range(0, 4):
            heap.append(num2card(i * 4 + j))
    heap.append(num2card(52))
    heap.append(num2card(53))


# 洗牌
def shuffle():
    global cards
    import random
    for i in range(0, len(heap)):
        cards.append(heap[i])
    random.shuffle(cards)


head1 = []
head2 = []
head3 = []
head = []


# 发牌
def deal():
    global head1
    global head2
    global head3
    global head
    for i in range(0, 18):
        head1.append(cards[i])
    for i in range(18, 36):
        head2.append(cards[i])
    for i in range(36, 54):
        head3.append(cards[i])
    head.append(head1)
    head.append(head2)
    head.append(head3)


strshow = ""


# 打印扑克牌
async def print_heap():
    global strshow
    strshow = ""
    for i in range(0, len(head)):
        # 给每个玩家的牌按数字大小排序
        # head[i].sort(key=lambda x: x[1:])
        # head[i].sort()
        headshow = []
        strcard = "玩家%s:\n" % players[i]
        for j in range(0, len(head[i])):
            # strcard+="%d."%j+head[i][j]+"\n"
            headshow.append("%d." % j + head[i][j])
        headshow.sort(key=lambda x: x[::-1])
        for k in range(0, len(headshow)):
            strcard += headshow[k] + "\n"
        strcard += "\n剩余%d张牌" % len(head[i])
        strshow += "玩家{0}:剩余{1}张牌\n".format(players[i], len(head[i]))
        if len(head[i]) == 0:
            await loading.send("游戏结束，玩家%s获得胜利" % players[i])
            await gameover()
        bot = get_bot()
        img = await text_to_pic(strcard, None, 300)
        if i != get_last_player(cardright):
            await bot.send_private_msg(user_id=playersid[i], message=MessageSegment.image(img))
        # await bot.send_private_msg(user_id=playersid[i],message=strcard)
    # img=await text_to_pic(strshow, None, 300)
    # await loading.send(MessageSegment.image(img))


# 检查该出牌是否合法
def checkobject(num):
    list = {'A', 'K', 'J', 'Q', '10', '9', '8', '7', '6', '5', '4', '3', '2'}
    if num.strip() in list:
        return True
    else:
        return False


async def gameover():
    global cardright
    global objectcard
    global passtimes
    global heap
    global cards
    global head
    global head1
    global head2
    global head3
    global players
    global playersid
    global currentheap
    global lastcardarr
    cardright = 0
    objectcard = ''
    passtimes = 0
    heap.clear()
    cards.clear()
    head[0].clear()
    head[1].clear()
    head[2].clear()
    head1.clear()
    head2.clear()
    head3.clear()
    head.clear()
    players.clear()
    playersid.clear()
    currentheap.clear()
    lastcardarr.clear()
    await loading.send("数据已归零")
    await startgame.finish()
    await sit.finish()
    await loading.finish()
    await chupai.finish()
    await follow.finish()


def checkjoker(card1):
    if card1.strip() == 'Joker' and len(head[cardright]) > 1:
        return False
    return True


# 获取上一个玩家
def get_last_player(player):
    if player == 0:
        return 2
    else:
        return player - 1


# 获取下一个玩家
def get_next_player(player):
    if player == 2:
        return 0
    else:
        return player + 1


cardlist = []


def getcardlist(card, headd):
    global cardlist
    cardlist = []
    numlist = card.split(" ")
    numlist = [x.strip() for x in numlist if x.strip() != '']
    for i in range(0, len(numlist)):
        if numlist[i].isnumeric():
            if int(numlist[i]) < 0 or int(numlist[i]) > (len(headd) - 1):
                return False
            for j in range(i):
                if numlist[i] == numlist[j]:
                    return False
        else:
            return False
        cardlist.append(headd[int(numlist[i])])
    if len(numlist) == len(headd):
        if checkarr(objectcard, cardlist) == False:
            return False
    for i in range(0, len(cardlist)):
        if cardlist[i] not in headd:
            return False
    for i in range(0, len(cardlist)):
        headd.remove(cardlist[i])
    return True


# 检查一组牌是否合法
def checkarr(objectcard, cardlist):
    for i in range(0, len(cardlist)):
        if check(objectcard, cardlist[i]) == False:
            return False
    return True


# 检查
def check(objcard, card):
    if card == "Joker":
        return True
    elif objcard == str(card)[1:]:
        return True
    else:
        return False


players = []
cardright = 0
objectcard = ''
currentheap = []
passtimes = 0
lastcardarr = []
strplay = ""


# 玩家出牌
def play(card1):
    global currentheap
    global passtimes
    global cardright
    global lastcardarr
    global objectcard
    global strplay
    strplay = ""
    if card1.strip() == "check":
        strplay += "待check的牌为{0}\n".format(lastcardarr)
        if checkarr(objectcard, lastcardarr):
            if passtimes == 0:
                strplay += "玩家{0}出牌成功，玩家{1}check失败,获得池中所有牌\n".format(players[get_last_player(cardright)],
                                                                     players[cardright])
                head[cardright].extend(currentheap)
                currentheap.clear()
                cardright = get_last_player(cardright)
                strplay += "玩家{0}获得牌权".format(players[cardright])
            else:
                strplay += "玩家{0}出牌成功，玩家{1}check失败,获得池中所有牌\n".format(
                    players[get_last_player(get_last_player(cardright))], players[cardright])
                head[cardright].extend(currentheap)
                currentheap.clear()
                cardright = get_last_player(get_last_player(cardright))
                strplay += "玩家{0}获得牌权".format(players[cardright])
            passtimes = 0
            return True
        else:
            if passtimes == 0:
                strplay += "玩家{0}check成功，玩家{1}出牌失败,获得池中所有牌\n".format(players[cardright],
                                                                     players[get_last_player(cardright)])
                head[get_last_player(cardright)].extend(currentheap)
                currentheap.clear()
                strplay += "玩家{0}获得牌权".format(players[cardright])
            else:
                strplay += "玩家{0}check成功，玩家{1}出牌失败,获得池中所有牌\n".format(players[cardright], players[
                    get_last_player(get_last_player(cardright))])
                head[get_last_player(get_last_player(cardright))].extend(currentheap)
                currentheap.clear()
                strplay += "玩家{0}获得牌权".format(players[cardright])
            passtimes = 0
            return True
    elif card1.strip() == "pass":
        strplay += "玩家{0}pass".format(players[cardright])
        passtimes += 1
        if (passtimes < (len(players) - 1)):
            return False
        else:
            passtimes = 0
            cardright = get_next_player(cardright)
            strplay += "玩家{0}获得牌权".format(players[cardright])
            currentheap.clear()
            return True
    else:
        passtimes = 0
        # 检查手牌中是否有玩家出的牌
        if getcardlist(card1, head[cardright]):
            lastcardarr = cardlist
            if checkarr(objectcard, cardlist):
                strplay += "玩家{0}出牌{1}张{2}\n".format(players[cardright], len(cardlist), objectcard)
                currentheap.extend(cardlist)
            else:
                strplay += "玩家{0}出牌{1}张{2}\n".format(players[cardright], len(cardlist), objectcard)
                currentheap.extend(cardlist)
            return False
        else:
            strplay += "玩家{0}跟牌失败，请重新出牌\n".format(players[cardright])
            cardright = get_last_player(cardright)


#######################################################################################

@startgame.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg: Message = CommandArg()):
    global cardright
    global objectcard
    global passtimes
    global heap
    global cards
    global head
    global head1
    global head2
    global head3
    global players
    global playersid
    global currentheap
    global lastcardarr
    if event.sender.nickname in players:
        cardright = 0
        objectcard = ''
        passtimes = 0
        heap.clear()
        cards.clear()
        head[0].clear()
        head[1].clear()
        head[2].clear()
        head.clear()
        players.clear()
        playersid.clear()
        currentheap.clear()
        lastcardarr.clear()
        await startgame.finish("数据已重置，请坐下等候开场")
    if len(players) == 0:
        players.append(event.sender.nickname)
        playersid.append(event.user_id)
        await startgame.send("{0}已经发起游戏，请等待其他人入座".format(event.sender.nickname))


players = []
playersid = []


@sit.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg: Message = CommandArg()):
    if event.sender.nickname in players:
        await sit.send("{0}你已经在游戏中了".format(event.sender.nickname))
    else:
        if len(players) > 2:
            await sit.finish("人数已满，请等待下一局")
        elif len(players) == 2:
            players.append(event.sender.nickname)
            playersid.append(event.user_id)
            strsit = "{0}已经加入游戏，请等待其他人入座\n".format(event.sender.nickname)
            strsit += "人数已满，请开场"
            await sit.finish(strsit)
        elif len(players) == 1:
            players.append(event.sender.nickname)
            playersid.append(event.user_id)
            await sit.send("{0}已经加入游戏，请等待其他人入座".format(event.sender.nickname))


@loading.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg: Message = CommandArg()):
    global players
    if len(head) == 0 and len(players) == 3:
        strloading = "开场成功\n"
        strloading += "{0}即将开始对局\n".format(players)
        strloading += "请玩家{0}出牌\n".format(players[cardright])
        initcard()
        shuffle()
        deal()
        await print_heap()
        strloading += strshow
        img = await text_to_pic(strloading, None, 300)
        await loading.send(MessageSegment.image(img))
    else:
        await loading.finish("已经开场，请勿重复开场")


cardright = 0


@chupai.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg: Message = CommandArg()):
    global cardright
    global players
    global objectcard
    global lastcardarr
    objectcard = ""
    if event.sender.nickname == players[cardright]:
        card1 = arg.extract_plain_text()
        if "as" in str(card1):
            liecard = card1.split("as")
            objectcard = liecard[1].strip()
            if checkobject(liecard[1]) and getcardlist(str(liecard[0]), head[cardright]):
                stras = "玩家{0}出牌{1}张{2}\n".format(players[cardright], len(cardlist), liecard[1].strip())
                lastcardarr = cardlist
                currentheap.extend(cardlist)
                objectcard = liecard[1].strip()
                stras += "标牌为：%s\n" % objectcard
                cardright = get_next_player(cardright)
                stras += "请玩家{0}跟牌".format(players[cardright])
                img = await text_to_pic(stras, None, 300)
                await print_heap()
                await loading.send(MessageSegment.image(img))
            else:
                await loading.send("玩家{0}出牌错误".format(players[cardright]))
        else:
            await loading.send("玩家{0}出牌失败，请使用as重新出牌".format(players[cardright]))
    else:
        await chupai.send("当前牌权位于{0}".format(players[cardright]))


@follow.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg: Message = CommandArg()):
    global cardright
    global passtimes
    global objectcard
    if event.sender.nickname == players[cardright]:
        if play(arg.extract_plain_text()):
            passtimes = 0
            strstart = strplay
            strstart += "\n"
            await print_heap()
            strstart += strshow
            strstart += "牌权交换，玩家{0}拿到牌权\n请玩家{0}出牌".format(players[cardright])
            img = await text_to_pic(strstart, None, 300)
            await follow.send(MessageSegment.image(img))
        else:
            strstart = strplay
            cardright = get_next_player(cardright)
            await print_heap()
            strstart += "标牌为：%s\n" % objectcard
            strstart += "passtimes:%d\n" % passtimes
            strstart += "牌池中有%d张牌\n" % len(currentheap)
            strstart += strshow
            strstart += "请玩家{0}跟牌".format(players[cardright])
            img = await text_to_pic(strstart, None, 300)
            await follow.send(MessageSegment.image(img))
    else:
        await follow.finish("当前牌权位于{0}".format(players[cardright]))

