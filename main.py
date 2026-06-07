import discord
from discord.ext import commands
from discord import app_commands
import random
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Flask keep alive
app = Flask('')

@app.route('/')
def home():
    return "Bot Tài Xỉu đang chạy!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Data handling
DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

data = load_data()

def get_user(user_id):
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "balance": 1000,
            "history": [],
            "last_daily": None
        }
        save_data(data)
    return data["users"][uid]

def roll_dice():
    dice = [random.randint(1, 6) for _ in range(3)]
    total = sum(dice)
    result = "Tài" if total >= 11 else "Xỉu"
    return dice, total, result

@bot.event
async def on_ready():
    print(f"✅ Bot Tài Xỉu Xịnh đã online: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Đã sync {len(synced)} slash commands")
    except Exception as e:
        print(e)
    keep_alive()

# ==================== SLASH COMMANDS ====================

@bot.tree.command(name="taixiu", description="Đặt cược Tài Xỉu")
@app_commands.describe(amount="Số tiền muốn cược (tối thiểu 10)", choice="Chọn Tài hoặc Xỉu")
@app_commands.choices(choice=[
    app_commands.Choice(name="Tài", value="Tài"),
    app_commands.Choice(name="Xỉu", value="Xỉu")
])
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def taixiu(interaction: discord.Interaction, amount: int, choice: str):
    if amount < 10:
        return await interaction.response.send_message("❌ Số tiền tối thiểu là 10!", ephemeral=True)
    
    user = get_user(interaction.user.id)
    if amount > user["balance"]:
        return await interaction.response.send_message("❌ Bạn không đủ tiền!", ephemeral=True)

    dice, total, result = roll_dice()
    win = (result == choice)

    if win:
        user["balance"] += amount
        color = 0x00ff00
        msg = f"🎉 Bạn **THẮNG** +{amount} 💰"
    else:
        user["balance"] -= amount
        color = 0xff0000
        msg = f"😢 Bạn **THUA** -{amount} 💰"

    # Save history
    history_entry = {
        "time": datetime.now().strftime("%H:%M %d/%m"),
        "bet": amount,
        "choice": choice,
        "result": result,
        "total": total,
        "dice": dice,
        "win": win
    }
    user["history"].insert(0, history_entry)
    if len(user["history"]) > 15:
        user["history"].pop()

    save_data(data)

    embed = discord.Embed(title="🎲 KẾT QUẢ TÀI XỈU", color=color)
    embed.add_field(name="Xúc xắc", value=f"🎲 {dice[0]}  {dice[1]}  {dice[2]}   = **{total}**", inline=False)
    embed.add_field(name="Kết quả", value=f"**{result}**", inline=True)
    embed.add_field(name="Bạn chọn", value=f"**{choice}**", inline=True)
    embed.add_field(name="Số dư", value=f"**{user['balance']:,}** 💰", inline=False)
    embed.set_footer(text=msg)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="balance", description="Xem số dư của bạn")
async def balance(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    embed = discord.Embed(title="💰 SỐ DƯ CỦA BẠN", color=0x3498db)
    embed.add_field(name="Số dư", value=f"**{user['balance']:,}** 💰", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="top", description="Bảng xếp hạng người giàu nhất")
async def top(interaction: discord.Interaction):
    sorted_users = sorted(data["users"].items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
    
    embed = discord.Embed(title="🏆 TOP 10 NGƯỜI GIÀU NHẤT", color=0xffd700)
    for i, (uid, info) in enumerate(sorted_users, 1):
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except:
            name = f"User {uid}"
        embed.add_field(name=f"{i}. {name}", value=f"{info['balance']:,} 💰", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="history", description="Xem lịch sử cược gần nhất")
async def history_cmd(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    if not user.get("history"):
        return await interaction.response.send_message("❌ Bạn chưa có lịch sử cược nào.", ephemeral=True)

    embed = discord.Embed(title="📜 LỊCH SỬ CƯỢC GẦN NHẤT", color=0x9b59b6)
    for h in user["history"][:8]:
        emoji = "✅" if h["win"] else "❌"
        embed.add_field(
            name=f"{emoji} {h['time']}",
            value=f"Đặt **{h['bet']:,}** vào **{h['choice']}** → {h['result']} ({h['total']})",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="daily", description="Nhận thưởng hàng ngày (100-300 💰)")
async def daily(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    now = datetime.now()
    last = user.get("last_daily")
    
    if last:
        last_time = datetime.strptime(last, "%Y-%m-%d %H:%M")
        if now - last_time < timedelta(hours=20):
            return await interaction.response.send_message("⏳ Bạn đã nhận daily hôm nay rồi!", ephemeral=True)
    
    reward = random.randint(100, 300)
    user["balance"] += reward
    user["last_daily"] = now.strftime("%Y-%m-%d %H:%M")
    save_data(data)
    
    embed = discord.Embed(title="🎁 DAILY REWARD", color=0x2ecc71)
    embed.add_field(name="Phần thưởng", value=f"+{reward} 💰", inline=False)
    embed.add_field(name="Số dư hiện tại", value=f"**{user['balance']:,}** 💰", inline=False)
    await interaction.response.send_message(embed=embed)

# Admin commands
def is_admin(interaction: discord.Interaction):
    return interaction.user.id in ADMIN_IDS

@bot.tree.command(name="give", description="[ADMIN] Tặng tiền")
@app_commands.check(is_admin)
async def give(interaction: discord.Interaction, user: discord.Member, amount: int):
    target = get_user(user.id)
    target["balance"] += amount
    save_data(data)
    await interaction.response.send_message(f"✅ Đã tặng **{amount:,}** cho {user.mention}")

@bot.tree.command(name="reset", description="[ADMIN] Reset số dư về 1000")
@app_commands.check(is_admin)
async def reset(interaction: discord.Interaction, user: discord.Member):
    target = get_user(user.id)
    target["balance"] = 1000
    target["history"] = []
    save_data(data)
    await interaction.response.send_message(f"✅ Đã reset {user.mention}")

bot.run(TOKEN)