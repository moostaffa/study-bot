import json
import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = "8064577987:AAEFJQNNbYtq8nPzsidrT4v7zJQaZpz5USI"

DAILY_FILE = "daily_data.json"
WEEKLY_FILE = "weekly_data.json"
MONTHLY_FILE = "monthly_data.json"

study_goals = {}
study_hours = {}
waiting_for_confirm = {}
rejection_timeout = 600  # 10 دقائق بالثواني

def load_data(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def add_hours(filename, user_id, hours=1):
    data = load_data(filename)
    data[str(user_id)] = data.get(str(user_id), 0) + hours
    save_data(filename, data)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحباً! لتحديد هدفك اليومي، اكتب:\n/setgoal عدد_الساعات\nمثال: /setgoal 5\n\n"
        "🧭 لعرض جميع الأوامر، اكتب /help"
    )

async def set_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args

    if len(args) != 1 or not args[0].isdigit():
        await update.message.reply_text(
            "يرجى كتابة الأمر بالشكل الصحيح، مثال:\n/setgoal 5\n\n"
            "🧭 لعرض جميع الأوامر، اكتب /help"
        )
        return

    goal = int(args[0])
    study_goals[user_id] = goal
    study_hours[user_id] = 0
    await update.message.reply_text(
        f"تم تحديد هدفك بـ {goal} ساعات دراسة. سأرسل لك رسالة كل ساعة لتتأكد من دراستك.\n\n"
        "🧭 لعرض جميع الأوامر، اكتب /help"
    )

async def check_study(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if user_id not in study_goals:
        await update.message.reply_text(
            "لم تحدد هدف دراسة بعد. اكتب /start للبدء.\n\n"
            "🧭 لعرض جميع الأوامر، اكتب /help"
        )
        return

    if user_id not in waiting_for_confirm:
        return

    if text == "تم":
        study_hours[user_id] += 1
        add_hours(DAILY_FILE, user_id)
        add_hours(WEEKLY_FILE, user_id)
        add_hours(MONTHLY_FILE, user_id)
        waiting_for_confirm.pop(user_id, None)

        goal = study_goals[user_id]
        done = study_hours[user_id]

        await update.message.reply_text(
            f"شكرًا لتأكيدك! عدد ساعات دراستك: {done} من {goal}.\n\n"
            "🧭 لعرض جميع الأوامر، اكتب /help"
        )

        if done >= goal:
            await update.message.reply_text(
                f"🎉 مبروك! أكملت هدفك الدراسي ({goal} ساعات). استمر هكذا!\n\n"
                "🧭 لعرض جميع الأوامر، اكتب /help"
            )
            del study_goals[user_id]
            del study_hours[user_id]
    else:
        await update.message.reply_text(
            "إذا درست، أرسل كلمة 'تم'.\n\n"
            "🧭 لعرض جميع الأوامر، اكتب /help"
        )

async def send_reminder(app):
    to_remove = []
    for user_id, timestamp in waiting_for_confirm.items():
        if datetime.now() > timestamp + timedelta(seconds=rejection_timeout):
            to_remove.append(user_id)
            # لا تحتسب له ساعة لأنه لم يرد بـ 'تم'
    for user_id in to_remove:
        waiting_for_confirm.pop(user_id)

async def send_hourly_check(context: ContextTypes.DEFAULT_TYPE):
    for user_id in list(study_goals.keys()):
        await context.bot.send_message(
            chat_id=user_id,
            text="⏰ هل درست الآن؟ أرسل 'تم' إذا درست.\n\n🧭 لعرض جميع الأوامر، اكتب /help"
        )
        waiting_for_confirm[user_id] = datetime.now()

async def show_top(update: Update, context: ContextTypes.DEFAULT_TYPE, filename, period_name):
    data = load_data(filename)
    if not data:
        await update.message.reply_text(
            f"لا توجد بيانات {period_name} بعد.\n\n"
            "🧭 لعرض جميع الأوامر، اكتب /help"
        )
        return

    sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
    top_10 = sorted_data[:10]
    message = f"🏆 أفضل 10 طلاب ({period_name}):\n"
    for i, (user_id, hours) in enumerate(top_10, start=1):
        message += f"{i}. معرف: {user_id} - {hours} ساعة\n"

    message += "\n🧭 لعرض جميع الأوامر، اكتب /help"
    await update.message.reply_text(message)

async def tday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_top(update, context, DAILY_FILE, "اليومي")

async def tweek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_top(update, context, WEEKLY_FILE, "الأسبوعي")

async def tmonth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_top(update, context, MONTHLY_FILE, "الشهري")

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_message = (
        "📚 أوامر البوت:\n\n"
        "/start - بدء استخدام البوت\n"
        "/setgoal عدد_الساعات - تحديد هدفك اليومي\n"
        "/tday - عرض أفضل الطلاب اليوم\n"
        "/tweek - عرض أفضل الطلاب هذا الأسبوع\n"
        "/tmonth - عرض أفضل الطلاب هذا الشهر\n"
        "أرسل كلمة 'تم' بعد كل ساعة دراسة للتأكيد.\n\n"
        "✅ مثال:\n/setgoal 5\n\n"
        "🧭 لعرض جميع الأوامر، اكتب /help"
    )
    await update.message.reply_text(help_message)

async def reset_daily_data():
    if os.path.exists(DAILY_FILE):
        os.remove(DAILY_FILE)
    print("✅ تم تصفير بيانات اليوم.")

async def daily_tasks(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    if now.hour == 0 and now.minute == 0:
        await reset_daily_data()

    await send_hourly_check(context)
    await send_reminder(context)

async def scheduler(app):
    while True:
        await asyncio.sleep(60)  # تحقق كل دقيقة
        await daily_tasks(app.job_queue)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setgoal", set_goal))
    app.add_handler(CommandHandler("tday", tday))
    app.add_handler(CommandHandler("tweek", tweek))
    app.add_handler(CommandHandler("tmonth", tmonth))
    app.add_handler(CommandHandler("help", show_help))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_study))

    async def main():
        await scheduler(app)

    print("✅ البوت شغال...")
    app.run_polling()
