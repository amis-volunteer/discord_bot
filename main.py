import discord
import os
from keep_alive import keep_alive
from dotenv import load_dotenv

import discord
from discord.ext import commands
from discord.ui import Button, View, Item
import asyncio
import supabase
from supabase import create_client, Client

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = commands.Bot(command_prefix="", intents=intents)

#1度の不正解でヒントボタンが増えるようにするか。
#クイズ送信の後、考えてから回答ではないか→ボタン表示用のコマンド必要か

#global変数を用いた。のちにエラーの温床になる可能性があるため要チェック
send_view = None
image_root = "http://drive.google.com/uc?export=view&id="
admin_id = ""
admin_channel_id = 1291644930141196350
admin_channel = None

LABEL_NAMES = {
    1: {"button1": "問題", "button2": "回答", "button3": "ヒント"},
    2: {"button1": "もんだい", "button2": "かいとう", "button3": "ひんと"},
    3: {"button1": "着いた", "button2": "回答", "button3": "---"},
    4: {"button1": "ついた", "button2": "かいとう", "button3": "---"},
    5: {"button1": "問題", "button2": "クリア!!", "button3": "---"},
    6: {"button1": "もんだい", "button2": "くりあ!!", "button3": "---"},
    7: {"button1": "問題", "button2": "回答", "button3": "---"},
    8: {"button1": "もんだい", "button2": "かいとう", "button3": "---"},
}


@bot.event
async def on_ready():
    global admin_channel
    admin_channel = bot.get_channel(admin_channel_id)
    print(admin_channel)

class UserNotFoundException(Exception):
    pass

class RootButtonView(View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.user_clicked = asyncio.Future()

    try:
        @discord.ui.button(label="コース1", style=discord.ButtonStyle.primary)
        async def button1(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            await create_user(self.ctx, course=1)
            self.user_clicked.set_result(True)

        @discord.ui.button(label="コース2", style=discord.ButtonStyle.primary)
        async def button2(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            await create_user(self.ctx, course=2)
            self.user_clicked.set_result(True)

        @discord.ui.button(label="コース3", style=discord.ButtonStyle.primary)
        async def button3(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            await create_user(self.ctx, course=3)
            self.user_clicked.set_result(True)
    except Exception as e:
        print("上手く作成できませんでした。")
        raise e
        

class BasicButtonView(View):
    def __init__(self, ctx, ptn):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.is_on_ans = False

        ptn = int(ptn)
        labels = LABEL_NAMES.get(ptn)
        self.button1.label = labels["button1"]
        self.button2.label = labels["button2"]
        self.button3.label = labels["button3"]

    @discord.ui.button(label="問題", style=discord.ButtonStyle.primary)
    async def button1(self, interaction: discord.Integration, button: discord.ui.Button):
        await interaction.response.defer()
        await send_quiz(self.ctx)
        user_progress = get_user_progress(self.ctx.channel.id)
        quiz_record = await get_user_quiz_record(self.ctx, user_progress)
        await show_buttons(self.ctx, quiz_record[0][int(user_progress["quiz_prog"])]["label"])
    
    @discord.ui.button(label="回答", style=discord.ButtonStyle.success)
    async def button2(self, interaction: discord.Integration, button: discord.ui.Button):
        await interaction.response.defer()
        user_progress = get_user_progress(self.ctx.channel.id)
        quiz_record = await get_user_quiz_record(self.ctx, user_progress)
        correct_ans = quiz_record[0][user_progress["quiz_prog"]]["answer"]

        if correct_ans:
            #print(">>> 回答を送信してください")
            #await self.ctx.send("回答を送信してください。")
            self.is_on_ans = True

            def check(m):
                return m.author == interaction.user and m.channel == interaction.channel
            print(len(correct_ans[0]))
            if len(correct_ans[0]) != 0:
                try:
                    msg = await bot.wait_for("message", check=check, timeout=120.0)
                    await accept_answer(await bot.get_context(msg), msg.content)
                except asyncio.TimeoutError:
                    await interaction.channel.send("タイムアウトしました。やり直してください。")
                    self.is_on_ans = False
                except Exception as e:
                    self.is_on_ans = False
                    raise e
            else:
                try:
                    msg = await bot.wait_for("message", check=check, timeout=120.0)
                except asyncio.TimeoutError:
                    await interaction.channel.send("タイムアウトしました。やり直してください。")
                    self.is_on_ans = False
                except Exception as e:
                    self.is_on_ans = False
                    raise e
                print(">>> 大正解!!!")
                if user_progress["quiz_prog"] + 1 == len(quiz_record[0]):
                    print(">>> クリア!!!")
                    await send_pict(self.ctx, user_progress, quiz_record[3])
                    await send_admin_channel(self.ctx, user_progress['name'], "クリアしました。")
                    update_user_progress(self.ctx, user_progress, user_progress["quiz_prog"] + 1, 0)
                else:
                    await send_pict(self.ctx, user_progress, quiz_record[1])
                    await send_admin_channel(self.ctx, user_progress['name'], f"{user_progress['quiz_prog'] + 1}個目の問題に正解しました。")
                    update_user_progress(self.ctx, user_progress, user_progress["quiz_prog"] + 1, 0)
                    await show_buttons(self.ctx, quiz_record[0][int(user_progress["quiz_prog"])]["label"])
        else:
            print(">>> 大正解!!!")
            if user_progress["quiz_prog"] + 1 == len(quiz_record[0]):
                print(">>> クリア!!!")
                await send_pict(self.ctx, user_progress, quiz_record[3])
                await send_admin_channel(self.ctx, user_progress['name'], "クリアしました。")
                update_user_progress(self.ctx, user_progress, user_progress["quiz_prog"] + 1, 0)
            else:
                await send_pict(self.ctx, user_progress, quiz_record[1])
                await send_admin_channel(self.ctx, user_progress['name'], f"{user_progress['quiz_prog'] + 1}個目の問題に正解しました。")
                update_user_progress(self.ctx, user_progress, user_progress["quiz_prog"] + 1, 0)
                await show_buttons(self.ctx, quiz_record[0][int(user_progress["quiz_prog"])]["label"])

    @discord.ui.button(label="ヒント", style=discord.ButtonStyle.danger)
    async def button3(self, interaction: discord.Integration, button: discord.ui.Button):
        await interaction.response.defer()
        await send_hint(self.ctx)



##引数不足時のエラーハンドリング
#supabaseクライアント作成
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

#画像URLもここに格納
#文章にする際は、特別に書き直す
#回答が""：なんでも正解
#回答が空：ボタン押下だけで正解

#30分コース
QUIZZES1 = [
    {"question" : "1JncrFYpi3zlNfSjNuYnHv77ltYx-VWTp" , "answer" : [""], "hints" : ["1T29ioGgdvACv70LdIXX82S8fkEzQ8ppt"], "label" : 1}, #M1
    {"question" : "1IIgbkxG5pbLjZ2YlCOuvsfmXT9VOKEvx" , "answer" : [""], "hints" : ["1wwIWCoFLyCTnm7pzSIa_FKWaFWolvAiu"], "label" : 1}, #M2
    {"question" : "1vz8AcNC8Sv-IyblCmfi_i1SlzjX9e8UX" , "answer" : [""], "hints" : [], "label" : 7}, #M3
    {"question" : "1qOwgC7vWyhgYvNQ9slnu3GXPjT45x8GT" , "answer" : [""], "hints" : [], "label" : 7}, #M4
    {"question" : "1REP9kJoxxxEUO8YAdjRnfeR2NKhqnfYW" , "answer" : [""], "hints" : [], "label" : 7}, #M5
    {"question" : "1krFAljErwcUsMyKVVwbDJARxGxNeUbcv" , "answer" : ["3", "３", "三"], "hints" : [], "label" : 1}, #Q1
    {"question" : "1nvrtEWsBsemfUVM6Hxl1pMbaTmJAnyzV" , "answer" : [], "hints" : [], "label" : 5}, #M6
    {"question" : "1kzY0DpMTa1RMW-1Sb4ckeYlgxG2p7w8P" , "answer" : ["ひなん", "避難", "ヒナン"], "hints" : [], "label" : 7}, #Q2
    {"question" : "1wnsAz7Z_v4LEc6PhF7c9glITi3ts7woO" , "answer" : ["リハ"], "hints" : [], "label" : 7}, #M7
    {"question" : "1zWniqWkuUjL575H7LrRKlvI53k-JEghT" , "answer" : ["なみだ", "涙", "ナミダ"], "hints" : [], "label" : 7}, #M8
    {"question" : "1Kx47074Sk8T-fnziR1RqsK8yVWgaYzFq" , "answer" : ["3", "３", "三"], "hints" : [], "label" : 7}, #Q3
    {"question" : "1K63ytgqxSXv1JniIsH29bzfjINrKcpRl" , "answer" : ["リハ"], "hints" : [], "label" : 7}, #Q4
    {"question" : "1mflOP6PJRFoW5h9FQHuq1XJHI7cg7QOH" , "answer" : ["西山橋"], "hints" : [], "label" : 7}, #Q5
    {"question" : "1LZHSrjBIdV11oXzVAnejZelN2WY-ab_G" , "answer" : ["1", "１", "一"], "hints" : [], "label" : 7}, #Q6
    {"question" : "1KnZPjacxebDFPcGK9C8QFKk9OTS_0uty" , "answer" : ["リハ"], "hints" : [], "label" : 7}, #Q7
    {"question" : "1SKBoxCxA-WeLUCSIJaGjBoXoE3_VPnql" , "answer" : ["5", "５", "五"], "hints" : [], "label" : 7}, #Q8
    {"question" : "1I9Uy8ocN1iyZ5AxW-hSLXNEOYZxyD7sa" , "answer" : ["リハ"], "hints" : [], "label" : 7}, #Q9
    {"question" : "1_-WBFIDiLlfLL6HHZhL160YRpiExFwXz" , "answer" : ["もくせい", "モクセイ"], "hints" : [], "label" : 7}, #Q10
    {"question" : "14dUBjAitZV7JPQ_Fen5pkPoyUeS5tPA7" , "answer" : ["大崎西部集会所"], "hints" : [], "label" : 7}, #Q11
    {"question" : "1ifqJy0yvYIh3IGIW07CEXTYv2Dm0oC4-" , "answer" : ["おめでとう", "omedeto", "omedetou", "オメデトウ"], "hints" : [], "label" : 7}, #M9
]

#10分コース
QUIZZES2 = [
    {"question" : "1TXvDk1VlJYpW18ZmLXaOLbFBb2m02Mwf" , "answer" : [""], "hints" : ["15PhsPbz_3cj3tkU48wqjGXCW1dKzNjC4"], "label" : 2},#M1
    {"question" : "1lVDnoQYhsx6YsMISDJkL7AO6p7QzLIlV" , "answer" : [""], "hints" : ["1CPbT6XbBQJTdlJ9i-BzNfLmERbwNAoKN"], "label" : 2},#M2
    {"question" : "1fV2MKc6INOi0v0E2C4fedIRANF3vb_Ou" , "answer" : ["未定"], "hints" : [], "label" : 8},#M3
    {"question" : "1SBqLqVAbcb68kQF2llLkH9FemeztKn5j" , "answer" : ["未定"], "hints" : [], "label" : 8},#M4
    {"question" : "1AMKsu2cbyQUL_Gj606HYMQiM1GCINtWh" , "answer" : ["未定"], "hints" : [], "label" : 8},#M5
    {"question" : "1VQe15rWk7kcyk-CJ6mwT3yAXe4tFjtjk" , "answer" : ["3", "３", "三"], "hints" : [], "label" : 8},#Q1
    {"question" : "1cwgLOLZqBggBvNkUXfpEZYq1VTQEZQ7h" , "answer" : [], "hints" : [], "label" : 6},#M6
    {"question" : "1xdPMfNZktCyEdlHMjHJMEffeJlI2F246" , "answer" : ["ひなん", "避難", "ヒナン"], "hints" : [], "label" : 8},#Q2
    {"question" : "1sF1hyIrZY_XpG5BJnpRKq0W6jlp9QmA4" , "answer" : ["ほくとう", "北東", "ホクトウ"], "hints" : ["13hWHCbhECxvibCCKag_W6Cvko7Ml3ZbO"], "label" : 2},#Q3
    {"question" : "1OCzIrVKDmma8egfzgD_E0OvUks7CInev" , "answer" : ["竹林", "たけばやし", "タケバヤシ"], "hints" : ["1KbGILkj4on_nGB8vmbhc7VACqCh8VO05"], "label" : 2},#Q4
    {"question" : "1Q24q0PngVaUd0Loq7kpdcgnHwEu5Aob3" , "answer" : ["おめでとう", "omedeto", "omedetou", "オメデトウ"], "hints" : [], "label" : 4},#M7
]

QUIZZES3 = [
    {"question" : "-" , "answer" : "1", "hints" : ["-", "-"]},
    {"question" : " -" , "answer" : "1", "hints" : ["-", "-"]},
    {"question" : "-" , "answer" : "1", "hints" : ["-", "-"]}
]


#userの送信に対して対処
@bot.command(name="admin")
async def send_admin_direct(ctx, msg):
    user = bot.get_channel(ctx.channel.id)
    if str(ctx.author.id) != admin_id:    
        await send_admin_channel(ctx, user, msg, True)
    else:
        raise commands.CommandNotFound


#自動送信されるものの対処
async def send_admin_channel(ctx, user, msg, is_error=False):
    if is_error:
        color = discord.Color.red()
    else:
        color = discord.Color.blue()
    
    embed = discord.Embed(
        title=user,
        description=msg,
        color=color  # 任意の色を設定
    )
    
    if admin_channel:
        await admin_channel.send(embed=embed)
    else:
        await ctx.send("adminチャンネルが見つかりません。")


#prog系は配列数ではなく、個数で表記している点に注意
def get_user_progress(user_id: str) -> list:
    response = supabase.table("user_prog").select("*").eq("user_id", user_id).execute()
    if response.data:
        print(response.data[0])
        return response.data[0]
    else:
        raise UserNotFoundException


#user進捗更新
def update_user_progress(ctx, user_progress, quiz_prog=None, hint_prog=None) -> list:
    updates = {}
    user_id = str(ctx.channel.id)
    if quiz_prog is not None:
        user_progress["quiz_prog"] = quiz_prog
        updates["quiz_prog"] = quiz_prog
    if hint_prog is not None:
        user_progress["hint_prog"] = hint_prog
        updates["hint_prog"] = hint_prog
    supabase.table("user_prog").update(updates).eq("user_id", user_id).execute()
    print(updates)
    return user_progress


#courseに該当するクイズを取得
async def get_user_quiz_record(ctx, user_progress):
    try:
        course = user_progress["course"]
        if course == 1:
            quiz = [QUIZZES1, "1lzWqWX00jc2rApJAmV6VG1Ckgy0udrI1", "", "1sclQysw1wpOuPTlcXwbuZz_pghfrxv3_"]
            return quiz
        elif course == 2:
            quiz = [QUIZZES2, "1EajpGkY0HRf2U7ZbmTzkgRFCidDlJQD1", "", "13Zc0l8yvf0Qwgqlxbw29GIWirofU9iRz"]
            return quiz
        elif course == 3:
            quiz == [QUIZZES3, "", "",""]
            return quiz
        else:
            await ctx.send("不正なコース名です。運営にご連絡を。")
            print(">>> 不正なコース名です。運営にご連絡を")
    except IndexError:
        print(">>> course名が未登録です。")
        await ctx.send("course名が未登録です。")
        send_admin_channel(ctx, user_progress["name"], "course名が未登録です。")
    except Exception as e:
        raise e


#画像送信
async def send_pict(ctx, user_progress, path):
    try:
        await ctx.send(image_root + path)
    except FileExistsError:
        await ctx.send("ファイルが見つかりません!!")
        send_admin_channel(ctx, user_progress["name"], "course名が未登録です。")
    except Exception as e:
        raise e


#クイズ開始
@bot.command(name="スタート")
async def start_quiz(ctx):
    user_id =  str(ctx.channel.id)
    print(user_id)
    view = RootButtonView(ctx)
    await ctx.send(view=view)
    try:
        await view.user_clicked
    except Exception as e:
        raise e
    else:
        await ctx.send(f"your id is {user_id}")
        user_progress = get_user_progress(user_id)
        quiz_record = await get_user_quiz_record(ctx, user_progress)
        await show_buttons(ctx, quiz_record[0][int(user_progress["quiz_prog"])]["label"])


#user作成
@bot.command(name="make")
async def create_user(ctx, course):
    user_id = str(ctx.channel.id)
    channel_name = bot.get_channel(ctx.channel.id)
    user_prog = {"user_id": user_id, "name" : str(channel_name), "course" : course, "quiz_prog": 0, "hint_prog": 0}
    try:
        supabase.table('user_prog').insert(user_prog).execute()
    except Exception as e:
        raise e
    else:
        print(user_prog)
        print(">>> userを作成しました。")
        await ctx.send("userを作成しました")
        await send_admin_channel(ctx, channel_name, "userを作成しました。")


#userリセット用
@bot.command(name="リセット")
async def delete_user(ctx):
    user_id = str(ctx.channel.id)
    try:
        supabase.table('user_prog').delete().eq("user_id", user_id).execute()
    except Exception as e:
        raise e
    else:
        print(">>> userを削除しました。")
        await ctx.send("userを削除しました。")

#手動判定時の正解用
@bot.command(name="正解")
async def check_ans_correct(ctx):
    user_id = str(ctx.channel.id)
    check_admin_id = str(ctx.author.id)
    if True:
    #if check_admin_id == admin_id:
        try:
            user_progress = get_user_progress(user_id)
            quiz_record = await get_user_quiz_record(ctx, user_progress)
            correct_ans = quiz_record[0][user_progress["quiz_prog"]]["answer"]
        except IndexError:
            print(">>> クリアしています!!!")
            await ctx.send("クリアしています!!!")
        except Exception as e:
            raise e
        else: 
            print(">>> 大正解!!!")
            if user_progress["quiz_prog"] + 1 == len(quiz_record[0]):
                print(">>> クリア!!!")
                await send_pict(ctx, user_progress, quiz_record[3])
                await send_admin_channel(ctx, user_progress['name'], "クリアしました。")
                update_user_progress(ctx, user_progress, user_progress["quiz_prog"] + 1, 0)
            else:
                await send_pict(ctx, user_progress, quiz_record[1])
                await send_admin_channel(ctx, user_progress['name'], f"{user_progress['quiz_prog'] + 1}個目の問題に正解しました。")
                update_user_progress(ctx, user_progress, user_progress["quiz_prog"] + 1, 0)
                #正解とともに次の問を表示するとする。
                await send_quiz(ctx)
                await show_buttons(ctx, quiz_record[0][int(user_progress["quiz_prog"])]["label"])
    else:
        raise commands.CommandNotFound


#手動確認の不正解用
@bot.command(name="不正解")
async def check_ans_discorrect(ctx):
    check_admin_id = str(ctx.author.id)
    if check_admin_id == admin_id:
        print(">>> もう一度試してみよう!!!")
        await ctx.send("もう一度試してみよう!!!")
        user_progress = get_user_progress(ctx, ctx.channel.id)
        quiz_record = await get_user_quiz_record(ctx, user_progress)
        await show_buttons(ctx, quiz_record[0][int(user_progress["quiz_prog"])]["label"])
    else:
        raise commands.CommandNotFound
    

#クイズ送信
@bot.command(name="クイズ")
async def send_quiz(ctx):
    user_id = str(ctx.channel.id)
    try:
        user_progress = get_user_progress(user_id)
        quiz_record = await get_user_quiz_record(ctx, user_progress)
        quiz = quiz_record[0][user_progress["quiz_prog"]]["question"]
    except IndexError:
        print(">>> クリアしています!!!")
        await ctx.send("クリアしています!!!")
    except Exception as e:
        raise e
    else:
        await send_pict(ctx, user_progress, quiz)
        await send_admin_channel(ctx, user_progress['name'], f"{user_progress['quiz_prog'] + 1}個目の問題を始めました。")


#クイズ回答
@bot.command(name="回答")
async def accept_answer(ctx, ans):
    user_id = str(ctx.channel.id)
    try:
        user_progress = get_user_progress(user_id)
        quiz_record = await get_user_quiz_record(ctx, user_progress)
        correct_ans = quiz_record[0][user_progress["quiz_prog"]]["answer"]
    except IndexError:
        print(">>> クリアしています!!!")
        await ctx.send("クリアしています!!!")
    except Exception as e:
        raise e
    else: 
        if ctx.message.attachments:
            await send_admin_channel(ctx, user_progress['name'], "画像が送信されました。", True)
        else:
            if ans in correct_ans:
                print(">>> 大正解!!!")
                if user_progress["quiz_prog"] + 1 == len(quiz_record[0]):
                    print(">>> クリア!!!")
                    await send_pict(ctx, user_progress, quiz_record[3])
                    await send_admin_channel(ctx, user_progress['name'], "クリアしました。")
                    update_user_progress(ctx, user_progress, user_progress["quiz_prog"] + 1, 0)
                else:
                    await send_pict(ctx, user_progress, quiz_record[1])
                    await send_admin_channel(ctx, user_progress['name'], f"{user_progress['quiz_prog'] + 1}個目の問題に正解しました。")
                    update_user_progress(ctx, user_progress, user_progress["quiz_prog"] + 1, 0)
                    await show_buttons(ctx, quiz_record[0][int(user_progress["quiz_prog"])]["label"])
            else:
                print(">>> 不正解!!!")
                await ctx.send("不正解!!!")
                await send_pict(ctx, user_progress, quiz_record[2])
                print(user_progress)
                await show_buttons(ctx, quiz_record[0][int(user_progress["quiz_prog"])]["label"])
    global send_view
    send_view.is_on_ans = False


#ヒント送信
@bot.command(name="ヒント")
async def send_hint(ctx):
    user_id = str(ctx.channel.id)
    try:
        user_progress = get_user_progress(user_id)
        quiz_record = await get_user_quiz_record(ctx, user_progress)
    except Exception as e:
        raise e
    else:
        if user_progress["quiz_prog"] == len(quiz_record[0]):
            print(">>> クリアしているので、ヒントはありません")
            await ctx.send("クリアしているので、ヒントはありません")
        else:
            try:
                hint = quiz_record[0][user_progress["quiz_prog"]]["hints"][user_progress["hint_prog"]]
            except IndexError:
                print(">>>ヒントはもうありません!!!")
                await ctx.send("ヒントはもうありません!!!")
            except Exception as e:
                raise e
            else:
                print(f">>> {hint}")
                await send_pict(ctx, user_progress, hint)
                update_user_progress(ctx, user_progress, None, user_progress["hint_prog"] + 1)
            await show_buttons(ctx, quiz_record[0][int(user_progress["quiz_prog"])]["label"])


#危機回避用にコマンドは残しておく
#ボタンptnを引数として受け取る。(クイズレコードの末尾)
@bot.command(name="test")
async def show_buttons(ctx, ptn=1):
    global send_view
    send_view = BasicButtonView(ctx, ptn)
    await ctx.send(view=send_view)


#エラーハンドリング
@bot.event
async def on_command_error(ctx, error):
    global send_view
    
    if isinstance(error, commands.CommandInvokeError):
        if ctx.author.id == bot.user.id or admin_id:
            pass
        elif send_view is not None and send_view.is_on_ans:
            pass
        else:
            error = error.original

    if isinstance(error, commands.CommandNotFound):
        if ctx.author.id == bot.user.id or admin_id:
            pass
        elif send_view is not None and send_view.is_on_ans:
            pass
        else:
            print(f">>> そのコマンドはありません")
            await ctx.send(f"そのコマンドはありません")
            user_progress = get_user_progress(str(ctx.channel.id))
            quiz_record = await get_user_quiz_record(ctx, user_progress)
            await show_buttons(ctx, quiz_record[0][int(user_progress["quiz_prog"])]["label"])
    elif isinstance(error, UserNotFoundException):
            if ctx.author.id == bot.user.id or admin_id:
                pass
            elif send_view is not None and send_view.is_on_ans:
                pass
            else:
                user_progress = get_user_progress(ctx.channel.id)
                print(">>> userが上手く作成されていません。")
                await ctx.send("userが上手く作成されていません。")
                await send_admin_channel(ctx, user_progress['name'], f"エラーが発生しました。\n{error}", True)
                quiz_record = await get_user_quiz_record(ctx, user_progress)
                await show_buttons(ctx, quiz_record[0][int(user_progress["quiz_prog"])]["label"])
    elif isinstance(error, commands.MissingRequiredArgument):
        print(">> コマンドの後に必要な文字が欠けています")
        await ctx.send("コマンドの後に必要な文字が欠けています。")
        user_progress = get_user_progress(str(ctx.channel.id))
        quiz_record = await get_user_quiz_record(ctx, user_progress)
        await show_buttons(ctx, quiz_record[0][int(user_progress["quiz_prog"])]["label"])
    else:
        user_progress = get_user_progress(ctx.channel.id)
        print(f">>> エラーが発生しました。{error}")
        await ctx.send(f"エラーが発生しました。{error}")
        await send_admin_channel(ctx, user_progress['name'], f"エラーが発生しました。\n{error}", True)
        quiz_record = await get_user_quiz_record(ctx, user_progress)
        await show_buttons(ctx, quiz_record[0][int(user_progress["quiz_prog"])]["label"])

TOKEN = os.getenv("DISCORD_TOKEN")
keep_alive()
bot.run(TOKEN)