import asyncio
import random
import sqlite3
import logging
import math
import os
import html
from datetime import datetime, timedelta
from pathlib import Path

# ==================== ЖУРНАЛ ДЕЙСТВИЙ ====================
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
(LOG_DIR / f"{datetime.now():%Y-%m-%d}.txt").touch(exist_ok=True)

def log_player_action(user, action: str):
    """Append one player action to the current daily log."""
    if not user:
        return
    game_user = get_user(user.id)
    game_nick = game_user.get("nickname") if game_user else None
    game_nick = game_nick or "не зарегистрирован"
    tg_name = " ".join(part for part in (user.first_name, user.last_name) if part) or "без имени"
    tg_username = f"@{user.username}" if user.username else "без username"
    timestamp = datetime.now().strftime("%H:%M:%S")
    safe_action = str(action).replace("\r", " ").replace("\n", " ")
    with (LOG_DIR / f"{datetime.now():%Y-%m-%d}.txt").open("a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] uid={user.id} | TG: {tg_name} ({tg_username}) | Игровой ник: {game_nick} | Действие: {safe_action}\n")


from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile,
    LabeledPrice, PreCheckoutQuery, TelegramObject
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ==================== НАСТРОЙКИ ====================
TOKEN = "9281302778:AAE242bivJ0H_FqANZjw7ha_Udzzv0B2AWQ"
IMAGES = Path("images")
ADMINS = [1301236413]
logging.basicConfig(level=logging.INFO)

# ==================== БАЗА ДАННЫХ ====================
conn = sqlite3.connect("game.db")
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, money INTEGER DEFAULT 1000, last_work TEXT DEFAULT '')")
cur.execute("PRAGMA table_info(users)")
columns = [info[1] for info in cur.fetchall()]

new_columns = {
    "business": "TEXT DEFAULT 'none'", "last_business_collect": "TEXT DEFAULT ''",
    "energy_drinks": "INTEGER DEFAULT 0", "armor": "INTEGER DEFAULT 0",
    "jail_time": "TEXT DEFAULT ''", "hospital_time": "TEXT DEFAULT ''",
    "dealers": "INTEGER DEFAULT 0", "last_dealer_collect": "TEXT DEFAULT ''",
    "last_daily_bonus": "TEXT DEFAULT ''", "car": "TEXT DEFAULT 'none'",
    "house": "TEXT DEFAULT 'none'", "last_house_collect": "TEXT DEFAULT ''",
    "clan_id": "INTEGER DEFAULT 0", "btc": "INTEGER DEFAULT 0",
    "eth": "INTEGER DEFAULT 0", "gold": "INTEGER DEFAULT 0",
    "nickname": "TEXT DEFAULT ''", "real_name": "TEXT DEFAULT ''",
    "gender": "TEXT DEFAULT ''", "registered": "INTEGER DEFAULT 0",
    "health": "INTEGER DEFAULT 100", "hunger": "INTEGER DEFAULT 0",
    "license_mvd": "INTEGER DEFAULT 0", "license_mchs": "INTEGER DEFAULT 0", "license_ems": "INTEGER DEFAULT 0",
    "license_trucker": "INTEGER DEFAULT 0", "last_trucker_game": "TEXT DEFAULT ''",
    "briefcase": "INTEGER DEFAULT 0",
    "shop_name": "TEXT DEFAULT ''", "shop_manager": "INTEGER DEFAULT 0", "last_shop_auto": "TEXT DEFAULT ''",
    "shop_food_stock": "INTEGER DEFAULT 0", "shop_food_price": "INTEGER DEFAULT 1500",
    "shop_medkit_stock": "INTEGER DEFAULT 0", "shop_medkit_price": "INTEGER DEFAULT 4000",
    "shop_energy_stock": "INTEGER DEFAULT 0", "shop_energy_price": "INTEGER DEFAULT 2500",
    "shop_armor_stock": "INTEGER DEFAULT 0", "shop_armor_price": "INTEGER DEFAULT 10000",
    "shop_briefcase_stock": "INTEGER DEFAULT 0", "shop_briefcase_price": "INTEGER DEFAULT 5000",
    "axe": "INTEGER DEFAULT 0", "lockpicks": "INTEGER DEFAULT 0",
    "house_alarm": "INTEGER DEFAULT 0", "shop_alarm_stock": "INTEGER DEFAULT 0", "shop_alarm_price": "INTEGER DEFAULT 25000",
    "last_home_rob": "TEXT DEFAULT ''", "last_car_theft": "TEXT DEFAULT ''",
    "last_bot_home_rob": "TEXT DEFAULT ''", "last_bot_car_theft": "TEXT DEFAULT ''",
    "car_protection": "INTEGER DEFAULT 0", "car_insurance": "INTEGER DEFAULT 0",
    "house_insurance": "INTEGER DEFAULT 0", "car_recovery_key": "TEXT DEFAULT ''", "car_recovery_at": "TEXT DEFAULT ''",
    "incoming_transfers_blocked": "INTEGER DEFAULT 0",
    "transfer_control_unlocked": "INTEGER DEFAULT 0",
    "license_mreo": "INTEGER DEFAULT 0", "license_auto": "INTEGER DEFAULT 0", "license_weapon": "INTEGER DEFAULT 0",
    "weapon_shop_name": "TEXT DEFAULT ''", "weapon_shop_last_income": "TEXT DEFAULT ''",
    "weapon_shop_ak47_stock": "INTEGER DEFAULT 0", "weapon_shop_ak47_price": "INTEGER DEFAULT 0",
    "weapon_shop_deagle_stock": "INTEGER DEFAULT 0", "weapon_shop_deagle_price": "INTEGER DEFAULT 0",
    "weapon_shop_m4a1_stock": "INTEGER DEFAULT 0", "weapon_shop_m4a1_price": "INTEGER DEFAULT 0",
    "xp_boost_until": "TEXT DEFAULT ''", "money_boost_until": "TEXT DEFAULT ''",
    "vip_type": "TEXT DEFAULT ''", "vip_expires": "TEXT DEFAULT ''", "vip_last_hourly": "TEXT DEFAULT ''",
    "tg_username": "TEXT DEFAULT ''", "ban_time": "TEXT DEFAULT ''", "ban_reason": "TEXT DEFAULT ''",
    "pass_blackmarket": "INTEGER DEFAULT 0", "c4": "INTEGER DEFAULT 0", "gun": "INTEGER DEFAULT 0",
    "last_rob": "TEXT DEFAULT ''", "bank_weapon_pending": "TEXT DEFAULT ''", "bank_heist_active": "INTEGER DEFAULT 0",
    "bank_weapon_uses_deagle": "INTEGER DEFAULT 0", "bank_weapon_uses_ak47": "INTEGER DEFAULT 0", "bank_weapon_uses_m4a1": "INTEGER DEFAULT 0"
}
for col, col_type in new_columns.items():
    if col not in columns:
        cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")

cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, money INTEGER DEFAULT 1000, last_work TEXT DEFAULT '')")
cur.execute("CREATE TABLE IF NOT EXISTS clans (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, owner_id INTEGER, bank INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS inventory_items (user_id INTEGER NOT NULL, item_key TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id, item_key))")
cur.execute("CREATE TABLE IF NOT EXISTS market_listings (id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER NOT NULL, item_key TEXT NOT NULL, quantity INTEGER NOT NULL, price_each INTEGER NOT NULL, created_at TEXT NOT NULL)")
cur.execute("""
CREATE TABLE IF NOT EXISTS donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, nickname TEXT, stars INTEGER, rubles INTEGER, charge_id TEXT, date TEXT
)
""")
conn.commit()

def get_user(uid: int):
    cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    if not row: return None
    cur.execute("PRAGMA table_info(users)")
    return dict(zip([c[1] for c in cur.fetchall()], row))

def get_user_by_nick(nick: str):
    cur.execute("SELECT * FROM users WHERE nickname=? COLLATE NOCASE", (nick,))
    row = cur.fetchone()
    if not row: return None
    cur.execute("PRAGMA table_info(users)")
    return dict(zip([c[1] for c in cur.fetchall()], row))

def create_user(uid: int, name: str):
    cur.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, name)); conn.commit()

def save(uid: int, **kwargs):
    for key, value in kwargs.items():
        cur.execute(f"UPDATE users SET {key}=? WHERE user_id=?", (value, uid))
    conn.commit()

def recover_insured_car(uid: int):
    u = get_user(uid)
    if not u or not u.get("car_recovery_key") or not u.get("car_recovery_at"):
        return None
    try:
        recovery_at = datetime.fromisoformat(u["car_recovery_at"])
    except (TypeError, ValueError):
        save(uid, car_recovery_key="", car_recovery_at="")
        return None
    if recovery_at > datetime.now():
        return None
    car_key = u["car_recovery_key"]
    save(uid, car=car_key, car_recovery_key="", car_recovery_at="")
    return CARS_CATALOG.get(car_key, ("Машина",))[0]

def car_recovery_pending(u: dict) -> bool:
    if not u or not u.get("car_recovery_key") or not u.get("car_recovery_at"):
        return False
    try:
        return datetime.fromisoformat(u["car_recovery_at"]) > datetime.now()
    except (TypeError, ValueError):
        return False

def xp_required(level: int) -> int:
    return 100 + max(0, level - 1) * 25

def add_experience(level: int, xp: int, amount: int) -> tuple[int, int]:
    xp += amount
    while xp >= xp_required(level):
        xp -= xp_required(level)
        level += 1
    return level, xp

def work_cooldown(u: dict) -> int:
    car_cooldowns = {
        "car_vaz_2107": 29, "car_vaz_2109": 27, "car_granta": 26,
        "car_m5": 23, "car_supra": 21, "car_g63": 18, "car_huracan": 15,
    }
    return car_cooldowns.get(u.get("car"), 30)

def work_hunger_after(u: dict, increase: int) -> int:
    total = min(100, u["hunger"] + increase)
    _salary, hunger_reduction = HOUSE_PERKS.get(u.get("house"), (1.0, 0.0))
    total = int(total * (1 - hunger_reduction))
    return total

def work_health_penalty(u: dict, hunger_increase: int, hunger_after: int) -> int:
    # Проверяем достижение 100% до снижения голода бонусом дома.
    raw_hunger = min(100, u.get("hunger", 0) + hunger_increase)
    return 15 if raw_hunger >= 100 or u.get("hunger", 0) >= 100 or hunger_after >= 100 else 0

def house_salary_multiplier(u: dict) -> float:
    return HOUSE_PERKS.get(u.get("house"), (1.0, 0.0))[0]

def boost_active(u: dict, column: str) -> bool:
    value = u.get(column, "")
    return bool(value and datetime.fromisoformat(value) > datetime.now())

def boost_expiry(u: dict, column: str, minutes: int) -> str:
    now = datetime.now()
    current = u.get(column, "")
    start = datetime.fromisoformat(current) if current and datetime.fromisoformat(current) > now else now
    return (start + timedelta(minutes=minutes)).isoformat()

VIP_TIERS = {
    "titan": {"name":"Titan VIP", "stars":20, "salary":1.2, "xp":1.3, "hourly_money":30_000, "hourly_xp":400, "weapon_discount":False},
    "premium": {"name":"Premium VIP", "stars":40, "salary":1.4, "xp":1.5, "hourly_money":45_000, "hourly_xp":600, "weapon_discount":False},
    "full": {"name":"Full VIP", "stars":55, "salary":1.6, "xp":1.7, "hourly_money":55_000, "hourly_xp":800, "weapon_discount":True},
}

def vip_config(u: dict):
    tier=VIP_TIERS.get(u.get("vip_type", ""))
    expires=u.get("vip_expires", "")
    if not tier or not expires:return None
    try:
        return tier if datetime.fromisoformat(expires)>datetime.now() else None
    except ValueError:return None

def vip_salary_multiplier(u: dict) -> float:
    tier=vip_config(u)
    return tier["salary"] if tier else 1.0

def vip_xp_multiplier(u: dict) -> float:
    tier=vip_config(u)
    return tier["xp"] if tier else 1.0

def vip_accrue_hourly(uid: int):
    """Начисляет целые накопившиеся часы VIP, в том числе после перерыва игрока."""
    u=get_user(uid)
    if not u or not u.get("vip_type"):
        return None
    tier=VIP_TIERS.get(u["vip_type"])
    try:expires=datetime.fromisoformat(u.get("vip_expires", ""))
    except (TypeError,ValueError):expires=datetime.min
    if not tier:
        save(uid,vip_type="",vip_expires="",vip_last_hourly="")
        return None
    now=datetime.now()
    try:last=datetime.fromisoformat(u.get("vip_last_hourly", ""))
    except (TypeError,ValueError):last=now
    end=min(now,expires)
    hours=max(0,int((end-last).total_seconds()//3600))
    reward=None
    if hours:
        money=tier["hourly_money"]*hours
        xp=tier["hourly_xp"]*hours
        level,new_xp=add_experience(u["level"],u["xp"],xp)
        next_tick=last+timedelta(hours=hours)
        save(uid,money=u["money"]+money,level=level,xp=new_xp,vip_last_hourly=next_tick.isoformat())
        reward={"hours":hours,"money":money,"xp":xp,"tier":tier["name"]}
    if now>=expires:
        save(uid,vip_type="",vip_expires="",vip_last_hourly="")
    return reward

def public_weapon_price(u: dict, weapon_key: str) -> int:
    base={"ak47":300_000,"deagle":150_000,"m4a1":400_000}[weapon_key]
    price=market_price(u,base)
    tier=vip_config(u)
    if tier and tier["weapon_discount"]:
        price=int(price/1.5)
    return price

def market_price(u: dict, base: int) -> int:
    # На 30 уровне цены обычного магазина и чёрного рынка пока базовые.
    return int(base * 1.5) if u["level"] > 30 else base

def update_stats(uid: int, hunger_add=0, health_add=0):
    u = get_user(uid)
    new_hunger = min(100, max(0, u["hunger"] + hunger_add))
    new_health = min(100, max(0, u["health"] + health_add))
    hosp_time = u["hospital_time"]
    if new_health <= 0:
        hosp_time = (datetime.now() + timedelta(minutes=10)).isoformat()
        new_health = 100; new_hunger = 50
    save(uid, hunger=new_hunger, health=new_health, hospital_time=hosp_time)

def check_status(uid: int) -> tuple[bool, str]:
    u = get_user(uid)
    if u.get("ban_time") and datetime.fromisoformat(u["ban_time"]) > datetime.now():
        return False, f"🚫 Вы забанены! Причина: {u.get('ban_reason')}"
    if u["hospital_time"] and datetime.fromisoformat(u["hospital_time"]) > datetime.now():
        return False, "🏥 Ты в больнице!"
    if u["jail_time"] and datetime.fromisoformat(u["jail_time"]) > datetime.now():
        return False, "🚔 Ты в КПЗ!"
    return True, ""

# ==================== ДАННЫЕ ====================
BAD_WORDS = ["хуй", "пизд", "ебан", "ебал", "бля", "пидор", "пидр", "сук", "мраз", "гандон", "долбоеб", "залуп", "говно", "жопа", "муд"]

TESTS = {
    "job_mvd": [{"q": "Что делать, если ты видишь вооруженного грабителя в банке?", "a": ["Вызвать СОБР и оцепить зону", "Бежать на него с кулаками", "Снимать на телефон"], "c": 0}, {"q": "Пьяная драка в ТЦ. Твои действия?", "a": ["Разнять и задержать зачинщиков", "Пройти мимо", "Кинуть в них стул"], "c": 0}, {"q": "Водитель едет зигзагами, явно пьян. Что делаешь?", "a": ["Остановить, составить протокол", "Отпустить за взятку", "Расстрелять колеса"], "c": 0}, {"q": "Найден подозрительный пакет в метро. Твои действия?", "a": ["Оцепить территорию и вызвать саперов", "Пнуть ногой", "Забрать домой"], "c": 0}, {"q": "Тебе предлагают взятку в 500 000 ₽ за молчание. Что делать?", "a": ["Отказаться и задержать", "Взять и уйти", "Попросить миллион"], "c": 0}],
    "job_mchs": [{"q": "Пожар на 5 этаже, человек кричит из окна. Что делаешь?", "a": ["Развернуть спасательную подушку/лестницу", "Кричать 'прыгай'", "Ждать, пока приедет начальство"], "c": 0}, {"q": "Загорелся бензин в гараже. Чем тушить?", "a": ["Пеной или порошком", "Водой", "Землей"], "c": 0}, {"q": "Сильное задымление в подвале. Что надеть?", "a": ["Дыхательный аппарат (противогаз)", "Медицинскую маску", "Мокрую футболку"], "c": 0}, {"q": "Кот застрял на дереве. Как снимать?", "a": ["Использовать автолестницу и спецкостюм", "Срубить дерево", "Кинуть в него палкой"], "c": 0}, {"q": "Человек заперт в горящей машине. Первые действия?", "a": ["Обесточить аккумулятор и вытащить", "Тушить машину, пока он внутри", "Ждать взрыва"], "c": 0}],
    "job_ems": [{"q": "Бабушка без сознания, нет пульса. Твои действия?", "a": ["Начать непрямой массаж сердца (СЛР)", "Дать таблетку от давления", "Ждать скорую"], "c": 0}, {"q": "Человек подавился и не может дышать. Что делать?", "a": ["Прием Геймлиха (толчки в живот)", "Похлопать по спине и дать воды", "Сделать укол"], "c": 0}, {"q": "Открытый перелом ноги. Твои действия?", "a": ["Наложить шину и обезболить", "Выпрямить ногу", "Дать понюхать нашатырь"], "c": 0}, {"q": "Сильное кровотечение из руки. Что делать?", "a": ["Наложить жгут выше раны", "Промыть водой", "Забинтовать прямо по ране"], "c": 0}, {"q": "Инсульт (парализовало половину лица). Твои действия?", "a": ["Уложить, обеспечить покой и везти в больницу", "Дать аспирин", "Отправить поспать"], "c": 0}]
}

# Отдельные экзамены МРЭО; варианты ответов перемешиваются общим обработчиком тестов.
TESTS["mreo_apply"] = [
    {"q":"Что нужно проверить перед выдачей водительского удостоверения?","a":["Личность заявителя и результаты экзамена","Только цвет автомобиля","Наличие страховки у родственника"],"c":0},
    {"q":"Что делать, если документы заявителя содержат расхождения?","a":["Приостановить оформление и перепроверить данные","Игнорировать и выдать права","Изменить данные наугад"],"c":0},
    {"q":"Как следует хранить персональные данные водителей?","a":["Не разглашать и использовать только по службе","Отправлять в общий чат","Публиковать в открытом доступе"],"c":0},
    {"q":"Человек просит оформить права без экзамена за деньги. Твои действия?","a":["Отказать и сообщить о попытке подкупа","Согласиться, если сумма большая","Попросить перевести знакомому"],"c":0},
    {"q":"Что сделать при подозрении на поддельный документ?","a":["Проверить по официальной базе и доложить","Сразу вернуть и забыть","Выдать лицензию по фотографии"],"c":0},
    {"q":"Кто может получить категорию B?","a":["Кандидат, прошедший предусмотренные проверки","Любой пассажир автомобиля","Только владелец автосалона"],"c":0},
    {"q":"Как правильно принять заявление?","a":["Проверить комплектность и зарегистрировать обращение","Положить без регистрации","Попросить написать данные на случайной бумаге"],"c":0},
    {"q":"Что делать при сбое базы во время оформления?","a":["Приостановить операцию до восстановления проверки","Внести любые данные вручную","Выдать временные права всем"],"c":0},
    {"q":"Заявитель не сдал практический экзамен. Что дальше?","a":["Сообщить результат и порядок повторной сдачи","Поставить зачёт из жалости","Удалить запись о попытке"],"c":0},
    {"q":"Как сотруднику МРЭО вести себя с посетителем?","a":["Вежливо, одинаково применяя правила ко всем","Требовать подарок за обслуживание","Отказывать без объяснения"],"c":0},
]
TESTS["mreo_test_b"] = [
    {"q":"На нерегулируемом перекрёстке равнозначных дорог кому уступают?","a":["Транспортному средству справа","Тому, кто быстрее подъехал","Тому, кто сигналит"],"c":0},
    {"q":"Что означает красный сигнал светофора?","a":["Движение запрещено","Можно ехать прямо","Разрешён поворот без остановки"],"c":0},
    {"q":"Перед пешеходным переходом человек начал переходить дорогу. Как поступить?","a":["Остановиться и пропустить","Объехать его по встречной полосе","Посигналить и продолжить"],"c":0},
    {"q":"Как безопасно начать движение после стоянки у тротуара?","a":["Убедиться в безопасности, включить сигнал и уступить потоку","Сразу выехать, заставив поток тормозить","Выехать без зеркал"],"c":0},
    {"q":"На дороге густой туман. Что следует сделать?","a":["Снизить скорость и увеличить дистанцию","Ехать быстрее, чтобы скорее выехать","Включить дальний свет постоянно"],"c":0},
    {"q":"Можно ли пользоваться телефоном в руках во время движения?","a":["Нет, остановиться в безопасном месте","Можно на малой скорости","Можно на перекрёстке"],"c":0},
    {"q":"Что делать при приближении машины экстренной службы с маячками и сиреной?","a":["Освободить путь, не создавая опасности","Ускориться перед ней","Остановиться посреди перекрёстка"],"c":0},
    {"q":"Какую дистанцию нужно держать на скользкой дороге?","a":["Увеличенную, учитывая длинный тормозной путь","Минимальную, чтобы не вклинились","Такую же, как летом"],"c":0},
    {"q":"Перед поворотом водитель должен?","a":["Заранее занять нужное положение и подать сигнал","Сигналить после поворота","Резко повернуть из любой полосы"],"c":0},
    {"q":"Что означает знак «Уступите дорогу»?","a":["Не начинать манёвр, если заставишь других менять скорость или направление","Всегда остановиться независимо от обстановки","Имеешь преимущество перед всеми"],"c":0},
    {"q":"При выезде со двора на дорогу водитель обязан?","a":["Уступить участникам движения на дороге и пешеходам","Требовать, чтобы все остановились","Выезжать первым по сигналу"],"c":0},
    {"q":"Как поступить, если впереди остановился школьный автобус с сигналами?","a":["Снизить скорость и быть готовым остановиться","Объехать на высокой скорости","Подать длинный сигнал"],"c":0},
    {"q":"Можно ли пересекать сплошную линию для обгона?","a":["Нет, пересечение запрещено правилами разметки","Можно, если дорога пустая","Можно только ночью"],"c":0},
    {"q":"Что проверить перед длительной поездкой?","a":["Техническое состояние, шины, световые приборы и документы","Только уровень музыки","Только чистоту кузова"],"c":0},
    {"q":"При проколе шины на ходу безопаснее всего?","a":["Крепко держать руль, плавно снизить скорость и съехать в безопасное место","Резко затормозить и повернуть","Выключить зажигание на полосе"],"c":0},
    {"q":"На перекрёстке образовался затор. Можно ли въехать, если выезд заблокирован?","a":["Нет, нужно дождаться свободного выезда","Да, если горит зелёный","Да, если посигналить"],"c":0},
    {"q":"При перестроении водитель должен?","a":["Проверить зеркала и слепую зону, затем уступить тем, кто едет по полосе","Считать, что его обязаны пропустить","Резко занять полосу"],"c":0},
    {"q":"Что делать на железнодорожном переезде при запрещающем сигнале?","a":["Остановиться перед стоп-линией и не въезжать","Объехать шлагбаум","Ускориться, пока поезд далеко"],"c":0},
    {"q":"Когда допустимо включать дальний свет?","a":["Когда он не ослепляет встречных и попутных водителей","Всегда в городе","Только при остановке"],"c":0},
    {"q":"Водитель почувствовал усталость и теряет концентрацию. Что делать?","a":["Остановиться в безопасном месте и отдохнуть","Открыть окно и увеличить скорость","Продолжить, отвлекаясь на телефон"],"c":0},
]

TESTS["job_trucker"] = [
    {"q": "Перед рейсом выяснилось, что масса груза близка к пределу. Что проверить в первую очередь?", "a": ["Полную массу и нагрузку на каждую ось", "Только общий объём кузова", "Только давление в передних шинах", "Цвет маркировки груза"], "c": 0},
    {"q": "При длинном спуске рабочие тормоза начинают перегреваться. Как действовать?", "a": ["Включить нейтраль и катиться", "Перейти на подходящую низшую передачу и использовать торможение двигателем", "Ускориться, чтобы быстрее закончить спуск", "Держать тормоз постоянно нажатым"], "c": 1},
    {"q": "Руль внезапно потянуло после хлопка шины на скорости. Что безопаснее?", "a": ["Резко ударить по тормозам", "Сильно повернуть в сторону обочины", "Крепко удерживать руль, плавно отпустить газ и замедлиться", "Сразу включить заднюю передачу"], "c": 2},
    {"q": "На мокрой дороге грузовик начал аквапланировать. Твои действия?", "a": ["Плавно отпустить газ и избегать резких движений", "Резко затормозить", "Повернуть руль до упора", "Включить круиз-контроль"], "c": 0},
    {"q": "После резкого торможения груз сместился и ремень ослаб. Что делать?", "a": ["Продолжать до пункта назначения", "Остановиться в безопасном месте и заново проверить крепление", "Ехать быстрее, чтобы груз прижало", "Открыть двери кузова на ходу"], "c": 1},
    {"q": "Как безопаснее сдавать назад, если обзор перекрыт?", "a": ["Ориентироваться только по одному зеркалу", "Попросить помощника, остановиться если потерял его из виду", "Сдавать быстро, чтобы меньше мешать", "Сигналить и не смотреть по сторонам"], "c": 1},
    {"q": "Загорелась лампа низкого давления масла. Что нужно сделать?", "a": ["Продолжать до ближайшей заправки", "Повысить обороты двигателя", "Безопасно остановиться и заглушить двигатель", "Отключить датчик"], "c": 2},
    {"q": "Как правильно действовать при отказе ABS во время экстренного торможения?", "a": ["Нажимать и отпускать педаль очень быстро", "Тормозить уверенно, держать направление и учитывать увеличенный тормозной путь", "Выключить зажигание на ходу", "Резко затянуть стояночный тормоз"], "c": 1},
    {"q": "Маршрут проходит под мостом, а высота машины почти равна указанному габариту. Что выбрать?", "a": ["Проверить фактическую высоту и выбрать безопасный маршрут с запасом", "Попробовать проехать по центру", "Спустить часть топлива", "Ехать быстрее"], "c": 0},
    {"q": "Почему опасно резко менять полосу на загруженном грузовике?", "a": ["Из-за большего радиуса поворота и риска потери устойчивости", "Потому что указатели поворота отключатся", "Потому что двигатель остановится", "Это влияет только на расход топлива"], "c": 0},
    {"q": "В зеркалах пропала машина, которая ехала рядом. Перед перестроением нужно:", "a": ["Сразу перестроиться", "Проверить слепую зону и только потом менять полосу", "Посигналить и повернуть", "Тормозить до полной остановки в полосе"], "c": 1},
    {"q": "При сильном боковом ветре на открытом участке безопаснее:", "a": ["Снизить скорость и крепко держать руль", "Ехать ближе к соседнему грузовику", "Увеличить скорость", "Открыть окно и высунуть руку"], "c": 0},
    {"q": "После долгого рейса чувствуешь, что начинаешь засыпать. Что делать?", "a": ["Остановиться в безопасном месте и отдохнуть", "Включить громкую музыку и продолжить", "Увеличить скорость", "Ехать за другим грузовиком"], "c": 0},
    {"q": "Какой интервал нужен за грузовиком на скользкой дороге?", "a": ["Такой же, как на сухой", "Меньше, чтобы не вклинивались", "Больше, с учётом увеличенного тормозного пути", "Интервал не важен при включённых фарах"], "c": 2},
    {"q": "Во время рейса заметил, что грузовые ремни повреждены. Как поступить?", "a": ["Заменить или закрепить груз исправными средствами до продолжения пути", "Завязать узел и ехать", "Снять все ремни", "Попросить пассажира держать груз"], "c": 0},
    {"q": "На перекрёстке грузовик не успевает безопасно завершить поворот из-за траектории. Что важно?", "a": ["Учитывать занос задней оси и заранее оценивать пространство", "Поворачивать резче", "Заехать на встречную полосу без проверки", "Остановиться поперёк перекрёстка"], "c": 0},
    {"q": "Во время движения отказали фары в темноте. Что делать?", "a": ["Продолжать с аварийкой", "Снизить скорость и безопасно остановиться вне потока", "Ехать за ближайшей машиной вплотную", "Включить дальний свет миганием"], "c": 1},
    {"q": "Почему нельзя резко поворачивать на высокой скорости с высоким грузом?", "a": ["Повышается риск опрокидывания из-за смещения центра тяжести", "Так экономится топливо", "Увеличивается давление масла", "Это отключает тормоза"], "c": 0},
    {"q": "Перед выездом обнаружил трещину на колесе или диске. Как правильно?", "a": ["Не начинать рейс до проверки и устранения неисправности", "Ехать только по правой полосе", "Снизить давление в остальных шинах", "Проверить после рейса"], "c": 0},
    {"q": "Грузовик занесло на скользкой дороге. Какой принцип безопаснее?", "a": ["Не делать резких торможений и поворотов, плавно корректировать движение", "Резко повернуть в противоположную сторону", "Нажать газ до упора", "Сразу затянуть стояночный тормоз"], "c": 0},
]

class RegStates(StatesGroup): nickname, real_name, gender = State(), State(), State()
class ClanStates(StatesGroup): create_name = State(); invite_nick = State()
class DonateStates(StatesGroup): custom_amount = State(); custom_xp = State()
class NicknameChangeStates(StatesGroup): new_nickname = State()
class TestStates(StatesGroup): in_test = State()
class ShopStates(StatesGroup): create_name = State(); set_price = State(); buy_stock = State()
class TransferStates(StatesGroup): choose_amount = State()
class RobStates(StatesGroup): in_game = State()
class CasinoStates(StatesGroup): choose_bet = State(); choose_side = State()
class JobTaskStates(StatesGroup): in_task = State(); trucker_game = State()
class HeistStates(StatesGroup): car_door = State(); car_ignition = State(); house_lock = State(); house_alarm = State()
class WeaponShopStates(StatesGroup): restock_amount = State(); set_price = State(); buy_amount = State()
class MarketplaceStates(StatesGroup): listing_amount = State(); listing_price = State(); buy_amount = State()

# ==================== БОТ ====================
bot = Bot(TOKEN)
dp = Dispatcher()
def is_admin(uid: int) -> bool: return uid in ADMINS

class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, Message):
            action = event.text or event.caption or f"сообщение ({event.content_type})"
            log_player_action(event.from_user, action)
        elif isinstance(event, CallbackQuery):
            log_player_action(event.from_user, f"нажал кнопку: {event.data or 'без callback_data'}")
        user_id = None
        if isinstance(event, Message): user_id = event.from_user.id
        elif isinstance(event, CallbackQuery): user_id = event.from_user.id
        if user_id and not is_admin(user_id):
            u = get_user(user_id)
            if u and u.get("ban_time") and datetime.fromisoformat(u["ban_time"]) > datetime.now():
                if isinstance(event, Message): await event.answer(f"🚫 <b>Вы забанены!</b>\nПричина: {u.get('ban_reason')}", parse_mode="HTML")
                elif isinstance(event, CallbackQuery): await event.answer(f"🚫 Вы забанены! Причина: {u.get('ban_reason')}", show_alert=True)
                return
        recovered_car=recover_insured_car(user_id) if user_id else None
        vip_reward=vip_accrue_hourly(user_id) if user_id else None
        result=await handler(event,data)
        if recovered_car:
            try: await bot.send_message(user_id,f"🛡 Страховка вернула твою машину: {recovered_car}. Она снова в гараже.")
            except Exception: pass
        if vip_reward:
            try:
                await bot.send_message(user_id,f"👑 {vip_reward['tier']}: за {vip_reward['hours']} ч. начислено +{vip_reward['money']:,} ₽ и +{vip_reward['xp']:,} XP.".replace(","," "))
            except Exception:pass
        return result

dp.message.middleware(BanMiddleware())
dp.callback_query.middleware(BanMiddleware())

# ==================== МЕНЮ ====================
def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💼 Работа")],
        [KeyboardButton(text="🏛 Гос. структуры"), KeyboardButton(text="🎒 Инвентарь")],
        [KeyboardButton(text="🛍 Торговая площадка")],
        [KeyboardButton(text="🔫 Магазин оружия")],
        [KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="🏆 ТОП")],
        [KeyboardButton(text="🏢 Бизнес"), KeyboardButton(text="🏦 Банк")],
        [KeyboardButton(text="🚗 Авто"), KeyboardButton(text="🏠 Дом")],
        [KeyboardButton(text="🛡 Страховка")],
        [KeyboardButton(text="🕵 Ограбление")],
        [KeyboardButton(text="🛡 Кланы"), KeyboardButton(text="📈 Биржа")],
        [KeyboardButton(text="🎁 Кейсы"), KeyboardButton(text="💸 Дать денег")],
        [KeyboardButton(text="🎰 Казино")],
        [KeyboardButton(text="⭐ Донат")],
    ], resize_keyboard=True)

NEW_JOBS = {
    "job_cook": {"name": "Повар", "action": "🍳 Готовить блюдо", "min": 6_000, "max": 10_000, "level": 3, "xp": 25},
    "job_lumberjack": {"name": "Лесоруб", "action": "🪓 Рубить дерево", "min": 7_000, "max": 12_000, "level": 5, "xp": 30},
    "job_fisherman": {"name": "Рыбак", "action": "🎣 Ловить рыбу", "min": 6_000, "max": 11_000, "level": 4, "xp": 28},
    "job_farmer": {"name": "Фермер", "action": "🌾 Собирать урожай", "min": 8_000, "max": 14_000, "level": 7, "xp": 35},
    "job_mine": {"name": "Шахтёр", "action": "⛏ Добывать руду", "min": 0, "max": 0, "level": 5, "xp": 0},
    "job_sawmill": {"name": "Лесопилка", "action": "🪵 Заготовить древесину", "min": 0, "max": 0, "level": 5, "xp": 0},
    "job_trucker": {"name": "Дальнобойщик", "action": "🚛 Везти груз", "min": 15_000, "max": 30_000, "level": 30, "xp": 50},
}

def jobs_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏢 Офис", callback_data="job_office"), InlineKeyboardButton(text="🏗 Стройка", callback_data="job_builder")],
        [InlineKeyboardButton(text="🚕 Таксист", callback_data="job_taxi"), InlineKeyboardButton(text="⛏ Шахта", callback_data="job_mine")],
        [InlineKeyboardButton(text="💻 Программист (с 5 ур.)", callback_data="job_it")],
        [InlineKeyboardButton(text="💊 Закладчик", callback_data="job_drug")],
        [InlineKeyboardButton(text="👨‍🍳 Повар", callback_data="job_cook"), InlineKeyboardButton(text="🌲 Лесопилка", callback_data="job_sawmill")],
        [InlineKeyboardButton(text="🌲 Лесоруб", callback_data="job_lumberjack"), InlineKeyboardButton(text="🎣 Рыбак", callback_data="job_fisherman")],
        [InlineKeyboardButton(text="🌾 Фермер", callback_data="job_farmer"), InlineKeyboardButton(text="🚛 Дальнобойщик (30 ур.)", callback_data="job_trucker")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])

def work_menu(job: str):
    if job in NEW_JOBS:
        if job == "job_mine": return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⛏ Добывать руду", callback_data="gather_mine")], [InlineKeyboardButton(text="🔙 Назад", callback_data="jobs")]])
        if job == "job_farmer": return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🌿 Добыть лён", callback_data="gather_flax"), InlineKeyboardButton(text="☁️ Добыть хлопок", callback_data="gather_cotton")], [InlineKeyboardButton(text="🔙 Назад", callback_data="jobs")]])
        if job == "job_sawmill": return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🪵 Добыть древесину", callback_data="gather_wood")], [InlineKeyboardButton(text="🔙 Назад", callback_data="jobs")]])
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="▶️ Начать смену", callback_data=f"newwork_start_{job}")], [InlineKeyboardButton(text="🔙 Назад", callback_data="jobs")]])
    if job in ["job_mvd", "job_mchs", "job_ems"]:
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📞 Вызовы", callback_data=f"calls_{job}")], [InlineKeyboardButton(text="🔙 Назад", callback_data="jobs")]])
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="▶️ Работать", callback_data=f"do_{job}")], [InlineKeyboardButton(text="🔙 Назад", callback_data="jobs")]])

def calls_menu(job: str):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📞 Выехать на вызов", callback_data=f"do_call_{job}_1")],[InlineKeyboardButton(text="🔙 Назад", callback_data="jobs")]])

CARS_CATALOG = {
    "car_vaz_2107": ("ВАЗ 2107", 50_000, "vaz2107.jpg"),
    "car_vaz_2109": ("ВАЗ 2109", 150_000, "vaz2109.jpg"),
    "car_m5": ("BMW M5 F90", 2_000_000, "m5.jpg"),
    "car_granta": ("LADA Granta", 300_000, "lada.jpg"),
    "car_supra": ("Toyota Supra A90", 3_500_000, "supra90.jpg"),
    "car_g63": ("Mercedes-Benz G 63 AMG", 8_000_000, "gelik.jpg"),
    "car_huracan": ("Lamborghini Huracán", 12_000_000, "lamva.jpg"),
}
HOUSES_CATALOG = {
    "house_dacha": ("Дача", 200_000),
    "house_townhouse": ("Таунхаус", 800_000),
    "house_penthouse": ("Пентхаус", 3_000_000),
    "house_cottage": ("Коттедж", 5_000_000),
    "house_villa": ("Вилла", 12_000_000),
    "house_mansion": ("Особняк", 25_000_000),
    "house_castle": ("Замок", 50_000_000),
}
HOUSE_PERKS = {
    # Множитель зарплаты и доля снижения итогового голода после работы.
    "house_dacha": (1.15, 0.02),
    "house_townhouse": (1.20, 0.03),
    "house_penthouse": (1.25, 0.04),
    "house_cottage": (1.30, 0.05),
    "house_villa": (1.35, 0.06),
    "house_mansion": (1.40, 0.07),
    "house_castle": (1.50, 0.08),
}

def sequence_keyboard(prefix: str, max_number: int):
    buttons = [InlineKeyboardButton(text=str(n), callback_data=f"{prefix}_{n}") for n in range(1, max_number + 1)]
    return InlineKeyboardMarkup(inline_keyboard=[buttons, [InlineKeyboardButton(text="❌ Отмена", callback_data="heist_cancel")]])

def house_wire_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Зелёный",callback_data="heist_house_wire_green")],
        [InlineKeyboardButton(text="🔴 Красный",callback_data="heist_house_wire_red")],
        [InlineKeyboardButton(text="🔵 Синий",callback_data="heist_house_wire_blue")],
        [InlineKeyboardButton(text="❌ Отмена",callback_data="heist_cancel")],
    ])

def sequence_prompt(title: str, sequence: list[int], progress: int = 0):
    return f"{title}\n🔒 Код скрыт. Подбирай цифры кнопками.\nВведено: {progress}/{len(sequence)}"

def shop_menu(u):
    prices = {"food": market_price(u, 5_000), "medkit": market_price(u, 15_000), "energy": market_price(u, 10_000), "armor": market_price(u, 50_000), "briefcase": market_price(u, 20_000), "alarm": market_price(u, 75_000)}
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🍔 Еда ({prices['food']:,}) [-30 Голода]".replace(",", " "), callback_data="buy_food")],
        [InlineKeyboardButton(text=f"💊 Аптечка ({prices['medkit']:,}) [+30 Здоровья]".replace(",", " "), callback_data="buy_medkit")],
        [InlineKeyboardButton(text=f"⚡ Энергетик ({prices['energy']:,}) | У тебя: {u.get('energy_drinks', 0)}".replace(",", " "), callback_data="buy_energy")],
        [InlineKeyboardButton(text=f"🛡 Бронежилет ({prices['armor']:,}) | У тебя: {u.get('armor', 0)}".replace(",", " "), callback_data="buy_armor")],
        [InlineKeyboardButton(text=f"💼 Портфель ({prices['briefcase']:,}) | У тебя: {u.get('briefcase', 0)}".replace(",", " "), callback_data="buy_briefcase")],
        [InlineKeyboardButton(text=f"🚨 Сигнализация ({prices['alarm']:,}) · зарядов: {u.get('house_alarm', 0)}".replace(",", " "), callback_data="buy_house_alarm")],
        [InlineKeyboardButton(text="🕶 Черный рынок", callback_data="black_market_menu")],
        [InlineKeyboardButton(text="🏪 Магазины игроков", callback_data="browse_shops")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])

def black_market_menu(u):
    prices = {"pass": market_price(u, 50_000), "c4": market_price(u, 100_000), "axe": market_price(u, 40_000), "lockpick": market_price(u, 15_000)}
    pass_kb = [InlineKeyboardButton(text=f"🎫 Пропуск ({prices['pass']:,} ₽)".replace(",", " "), callback_data="buy_pass")] if u.get("pass_blackmarket") == 0 else []
    return InlineKeyboardMarkup(inline_keyboard=[
        *([pass_kb] if pass_kb else []),
        [InlineKeyboardButton(text=f"💣 С4 ({prices['c4']:,} ₽) | У тебя: {u.get('c4', 0)}".replace(",", " "), callback_data="buy_c4")],
        [InlineKeyboardButton(text=f"🪓 Топор ({prices['axe']:,} ₽) | У тебя: {u.get('axe', 0)}".replace(",", " "), callback_data="buy_axe")],
        [InlineKeyboardButton(text=f"🔓 Отмычка ({prices['lockpick']:,} ₽) | У тебя: {u.get('lockpicks', 0)}".replace(",", " "), callback_data="buy_lockpick")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_shop")]
    ])

def cars_menu(u):
    kb = [[InlineKeyboardButton(text=f"{'✅ ' if u.get('car')==k else ''}{v[0]} ({v[1]:,} ₽)".replace(",", " "), callback_data=f"view_car_{k}")] for k, v in CARS_CATALOG.items()]
    if u.get("car") in CARS_CATALOG:
        kb.append([InlineKeyboardButton(text="💸 Продать свою машину", callback_data="sell_car")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def houses_menu(u):
    kb = [[InlineKeyboardButton(text=f"{'✅ ' if u.get('house')==k else ''}🏠 {v[0]} ({v[1]:,} ₽)".replace(",", " "), callback_data=f"buy_house_{k}")] for k, v in HOUSES_CATALOG.items()]
    if u.get("house") in HOUSES_CATALOG:
        kb.append([InlineKeyboardButton(text="💰 Собрать доход с дома", callback_data="collect_house")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def business_menu(u):
    kb = []
    if u.get("business") == "coffee": kb.append([InlineKeyboardButton(text="📈 Собрать доход с Кофейни", callback_data="collect_business")])
    else: kb.append([InlineKeyboardButton(text="☕ Купить Кофейню (1 млн ₽)", callback_data="buy_coffee")])
    if u.get("shop_name"): kb.append([InlineKeyboardButton(text=f"⚙️ Мой магазин ({u['shop_name']})", callback_data="my_shop")])
    else: kb.append([InlineKeyboardButton(text="🏪 Купить Магазин (2 млн ₽)", callback_data="buy_player_shop")])
    if u.get("shop_name"):
        last = u.get("last_shop_auto", "")
        ready = not last or datetime.now() - datetime.fromisoformat(last) >= timedelta(hours=24)
        label = "💰 Забрать дневную прибыль магазина (200–300к)" if ready else "⏳ Прибыль магазина: сбор через 24 ч."
        kb.append([InlineKeyboardButton(text=label, callback_data="collect_shop_daily")])
    if u.get("weapon_shop_name"):
        kb.append([InlineKeyboardButton(text="🔫 Управление оружейным магазином", callback_data="weapon_shop_manage")])
        last = u.get("weapon_shop_last_income", "")
        ready = not last or datetime.now() - datetime.fromisoformat(last) >= timedelta(hours=24)
        label = "💰 Собрать прибыль оружейного магазина (300–400к)" if ready else "⏳ Прибыль оружейного магазина: через 24 ч."
        kb.append([InlineKeyboardButton(text=label, callback_data="weapon_shop_collect")])
    else:
        kb.append([InlineKeyboardButton(text="🔫 Купить оружейный магазин (3 млн ₽)", callback_data="weapon_shop_buy_business")])
    kb.append([InlineKeyboardButton(text=f"🤝 Нанять Дилеров (50к) | Твои: {u.get('dealers', 0)}", callback_data="hire_dealer")])
    if u.get("dealers", 0) > 0: kb.append([InlineKeyboardButton(text="💰 Собрать доход с дилеров", callback_data="collect_dealers")])
    kb.append([InlineKeyboardButton(text="💸 Взятка МВД (100к)", callback_data="bribe")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ==================== ЧЕРНЫЙ РЫНОК ====================
@dp.callback_query(F.data == "black_market_menu")
async def black_market(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if u.get("pass_blackmarket") == 0:
        text = "🕶 <b>Черный рынок</b>\n\nДля входа нужен пропуск (50к)."
    else:
        text = "🕶 <b>Черный рынок</b>\n\nСнаряжение для ограблений и угонов. Нужен пропуск."
    await cb.message.edit_text(text, reply_markup=black_market_menu(u), parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data == "buy_pass")
async def buy_pass(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    price = market_price(u, 50_000)
    if u["money"] < price: return await cb.answer(f"Нужно {price:,} ₽!".replace(",", " "), show_alert=True)
    save(cb.from_user.id, money=u["money"] - price, pass_blackmarket=1)
    await cb.answer("✅ Пропуск куплен!", show_alert=True)
    await cb.message.edit_reply_markup(reply_markup=black_market_menu(get_user(cb.from_user.id)))

@dp.callback_query(F.data == "buy_c4")
async def buy_c4(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if u.get("pass_blackmarket") == 0: return await cb.answer("Нужен пропуск!", show_alert=True)
    price = market_price(u, 100_000)
    if u["money"] < price: return await cb.answer(f"Нужно {price:,} ₽!".replace(",", " "), show_alert=True)
    save(cb.from_user.id, money=u["money"] - price, c4=u.get("c4", 0) + 1)
    await cb.answer("💣 С4 куплено!", show_alert=True)
    await cb.message.edit_reply_markup(reply_markup=black_market_menu(get_user(cb.from_user.id)))

@dp.callback_query(F.data == "buy_axe")
async def buy_axe(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if not u.get("pass_blackmarket"): return await cb.answer("Нужен пропуск чёрного рынка!", show_alert=True)
    price = market_price(u, 40_000)
    if u["money"] < price: return await cb.answer(f"Нужно {price:,} ₽!".replace(",", " "), show_alert=True)
    save(cb.from_user.id, money=u["money"] - price, axe=u.get("axe", 0) + 1)
    await cb.answer("🪓 Топор куплен!", show_alert=True)
    await cb.message.edit_reply_markup(reply_markup=black_market_menu(get_user(cb.from_user.id)))

@dp.callback_query(F.data == "buy_lockpick")
async def buy_lockpick(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if not u.get("pass_blackmarket"): return await cb.answer("Нужен пропуск чёрного рынка!", show_alert=True)
    price = market_price(u, 15_000)
    if u["money"] < price: return await cb.answer(f"Нужно {price:,} ₽!".replace(",", " "), show_alert=True)
    save(cb.from_user.id, money=u["money"] - price, lockpicks=u.get("lockpicks", 0) + 1)
    await cb.answer("🔓 Отмычка куплена!", show_alert=True)
    await cb.message.edit_reply_markup(reply_markup=black_market_menu(get_user(cb.from_user.id)))

# ==================== ОГРАБЛЕНИЕ БАНКА ====================
BANK_WEAPONS = {
    "weapon_deagle": {"name":"Дигл", "injury_chance":0.50, "uses_column":"bank_weapon_uses_deagle"},
    "weapon_ak47": {"name":"АК-47", "injury_chance":0.25, "uses_column":"bank_weapon_uses_ak47"},
    "weapon_m4a1": {"name":"М4А1", "injury_chance":0.10, "uses_column":"bank_weapon_uses_m4a1"},
}
BANK_WEAPON_PRIORITY = ("weapon_m4a1", "weapon_ak47", "weapon_deagle")

@dp.message(F.text == "🏦 Банк")
async def bank(message: Message):
    u = get_user(message.from_user.id)
    kb = [[InlineKeyboardButton(text="🔫 Ограбить банк", callback_data="rob_bank")], [InlineKeyboardButton(text="⚖️ Внести залог (КПЗ)", callback_data="bail")], [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]]
    weapon_key=next((key for key in BANK_WEAPON_PRIORITY if inventory_amount(message.from_user.id,key)>0),None)
    weapon_text="Нет оружия для ограбления банка."
    if weapon_key:
        config=BANK_WEAPONS[weapon_key]
        uses=int(u.get(config["uses_column"],0))
        weapon_text=f"Оружие: {config['name']} · прочность {5-uses}/5 ограблений · шанс ранения {int(config['injury_chance']*100)}%."
    text = f"🏦 <b>Банк:</b>\nМаксимальный куш: 500 000 ₽.\nОграбление доступно раз в 1 час.\n{weapon_text}"
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@dp.callback_query(F.data == "rob_bank")
async def rob_bank_start(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    
    if u.get("last_rob"):
        last = datetime.fromisoformat(u["last_rob"])
        if datetime.now() - last < timedelta(hours=1):
            left = timedelta(hours=1) - (datetime.now() - last)
            mins = int(left.total_seconds() // 60)
            return await cb.answer(f"Банк усилил охрану. Ждать {mins} мин.", show_alert=True)
            
    if u["level"] < 10: return await cb.answer("Нужен 10 уровень!", show_alert=True)
    if u.get("pass_blackmarket") == 0: return await cb.answer("Нужен пропуск на Черный рынок!", show_alert=True)
    if u.get("c4", 0) == 0: return await cb.answer("Нужно С4!", show_alert=True)
    if not u.get("license_weapon"): return await cb.answer("Нужна лицензия на оружие из МРЭО!", show_alert=True)
    weapon_key=next((key for key in BANK_WEAPON_PRIORITY if inventory_amount(cb.from_user.id,key)>0),None)
    if not weapon_key:return await cb.answer("Нужно оружие из лицензированного оружейного магазина!",show_alert=True)

    save(cb.from_user.id, c4=u["c4"] - 1, bank_weapon_pending=weapon_key, bank_heist_active=1)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚪 Зайти в банк", callback_data="rob_step_1")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="rob_cancel")]
    ])
    await cb.message.answer("🏦 Ты подошел к банку. Охрана пока ничего не подозревает. Начинаем?", reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "rob_step_1")
async def rob_step_1(cb: CallbackQuery):
    u=get_user(cb.from_user.id)
    if not u.get("bank_heist_active",0):return await cb.answer("Ограбление уже завершено. Начни заново.",show_alert=True)
    weapon_key=u.get("bank_weapon_pending","")
    config=BANK_WEAPONS.get(weapon_key)
    if not config or inventory_amount(cb.from_user.id,weapon_key)<1:
        save(cb.from_user.id,bank_weapon_pending="")
        return await cb.answer("Оружие для перестрелки не найдено. Начни ограбление заново.",show_alert=True)
    uses=int(u.get(config["uses_column"],0))
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔫 Стрелять из {config['name']} · риск ранения {int(config['injury_chance']*100)}%",callback_data="rob_shoot")],
        [InlineKeyboardButton(text="🚶 Попытаться пройти тихо",callback_data="rob_fail")],
    ])
    await cb.message.edit_text(f"🏦 Ты вошёл в банк. Охрана готова открыть огонь.\n🔫 Оружие: {config['name']} · использовано {uses}/5 раз.\nВыбери действие:",reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "rob_shoot")
async def rob_shoot(cb: CallbackQuery):
    u=get_user(cb.from_user.id)
    if not u.get("bank_heist_active",0):return await cb.answer("Ограбление уже завершено. Начни заново.",show_alert=True)
    weapon_key=u.get("bank_weapon_pending","")
    config=BANK_WEAPONS.get(weapon_key)
    if not config or inventory_amount(cb.from_user.id,weapon_key)<1:
        save(cb.from_user.id,bank_weapon_pending="")
        return await cb.answer("Оружие для перестрелки не найдено. Начни ограбление заново.",show_alert=True)

    # Одно использование тратится каждый раз, когда игрок вступает в перестрелку.
    save(cb.from_user.id,bank_weapon_pending="")
    uses=int(u.get(config["uses_column"],0))+1
    weapon_message=f"🔫 Оружие: {config['name']} · использование {min(uses,5)}/5."
    if uses>=5:
        inventory_take(cb.from_user.id,weapon_key,1)
        save(cb.from_user.id,**{config["uses_column"]:0})
        weapon_message+=f"\n⚠️ {config['name']} израсходован после пятого ограбления."
    else:
        save(cb.from_user.id,**{config["uses_column"]:uses})

    if random.random()<config["injury_chance"]:
        save(cb.from_user.id,jail_time=(datetime.now()+timedelta(minutes=15)).isoformat(),last_rob=datetime.now().isoformat(),bank_heist_active=0)
        update_stats(cb.from_user.id,health_add=-25)
        await cb.message.edit_text(f"🚨 <b>Охрана ранила тебя!</b>\n{weapon_message}\n❤️ Потеряно 25 здоровья. Ты задержан и отправлен в КПЗ на 15 минут.",parse_mode="HTML")
        return await cb.answer("Охрана победила в перестрелке!",show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💣 Перейти к хранилищу", callback_data="rob_step_2")]])
    await cb.message.edit_text(f"🏦 Ты отбился от охраны и прошёл к хранилищу.\n{weapon_message}", reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "rob_step_2")
async def rob_step_2(cb: CallbackQuery):
    if not get_user(cb.from_user.id).get("bank_heist_active",0):return await cb.answer("Ограбление уже завершено. Начни заново.",show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💣 Заложить С4", callback_data="rob_success")],
        [InlineKeyboardButton(text="🔨 Сломать дверь руками", callback_data="rob_fail")]
    ])
    await cb.message.edit_text("🔫 Ты нейтрализовал охрану. Перед тобой хранилище. Как его открыть?", reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "rob_success")
async def rob_success(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if not u.get("bank_heist_active",0):return await cb.answer("Это ограбление уже завершено.",show_alert=True)
    reward = random.randint(100_000, 500_000)
    save(cb.from_user.id, money=u["money"] + reward, last_rob=datetime.now().isoformat(),bank_weapon_pending="",bank_heist_active=0)
    
    await cb.message.edit_text(f"💥 <b>БУМ!</b> Хранилище взорвано!\n💰 Ты забрал <b>{reward:,} ₽</b> и скрылся.\n\nСледующее ограбление через 1 час.".replace(",", " "), parse_mode="HTML")
    await cb.answer("Успех!")

@dp.callback_query(F.data == "rob_fail")
async def rob_fail(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if not u.get("bank_heist_active",0):return await cb.answer("Это ограбление уже завершено.",show_alert=True)
    save(cb.from_user.id, jail_time=(datetime.now() + timedelta(minutes=15)).isoformat(), last_rob=datetime.now().isoformat(),bank_weapon_pending="",bank_heist_active=0)
    await cb.message.edit_text("🚨 <b>Охрана тебя заметила!</b>\nТебя скрутили. Ты в КПЗ на 15 минут.", parse_mode="HTML")
    await cb.answer("Провал!")

@dp.callback_query(F.data == "rob_cancel")
async def rob_cancel(cb: CallbackQuery):
    save(cb.from_user.id,bank_weapon_pending="",bank_heist_active=0)
    await cb.message.delete()
    await cb.answer("Ограбление отменено. Потраченный С4 не возвращается.",show_alert=True)

# ==================== ОГРАБЛЕНИЕ ДОМОВ И УГОН МАШИН ====================
@dp.message(F.text == "🕵 Ограбление")
async def crime_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Ограбить дом", callback_data="crime_house_list")],
        [InlineKeyboardButton(text="🚘 Угнать машину", callback_data="crime_car_list")],
    ])
    await message.answer("🕵 <b>Выбери цель:</b>\n\nДля угона нужны пропуск и отмычка. Для дома — пропуск, отмычка и топор.", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "crime_house_list")
async def crime_house_list(cb: CallbackQuery):
    cur.execute("SELECT user_id, nickname, house FROM users WHERE house NOT IN ('none', '') AND house IS NOT NULL AND user_id != ?", (cb.from_user.id,))
    rows = [(uid, nick, house) for uid, nick, house in cur.fetchall() if house in HOUSES_CATALOG]
    kb = [[InlineKeyboardButton(text="🏠 Дом бота · небольшая добыча", callback_data="heist_house_bot")]]
    kb += [[InlineKeyboardButton(text=f"🏠 {nick or 'Игрок'} | {HOUSES_CATALOG[house][0]}", callback_data=f"heist_house_target_{uid}")] for uid, nick, house in rows]
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    await cb.message.edit_text("Выбери цель. У дома бота добыча меньше:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()

@dp.callback_query(F.data == "crime_car_list")
async def crime_car_list(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if u.get("car") not in (None, "", "none") or car_recovery_pending(u):
        return await cb.answer("Твой гараж уже занят. Сначала освободи свою машину.", show_alert=True)
    cur.execute("SELECT user_id, nickname, car FROM users WHERE car NOT IN ('none', '') AND car IS NOT NULL AND user_id != ?", (cb.from_user.id,))
    rows = [(uid, nick, car) for uid, nick, car in cur.fetchall() if car in CARS_CATALOG]
    kb = [[InlineKeyboardButton(text="🚘 Машина бота · мало денег в бардачке", callback_data="heist_car_bot")]]
    kb += [[InlineKeyboardButton(text=f"🚘 {nick or 'Игрок'} | {CARS_CATALOG[car][0]}", callback_data=f"heist_car_target_{uid}")] for uid, nick, car in rows]
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    await cb.message.edit_text("Выбери машину. У бота в бардачке меньше денег:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()

@dp.callback_query(F.data == "heist_cancel")
async def heist_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer("Попытка отменена. Потраченные инструменты не возвращаются.", show_alert=True)
    try: await cb.message.edit_text("Попытка ограбления отменена.")
    except Exception: pass

@dp.callback_query(F.data.startswith("heist_car_target_"))
async def heist_car_start(cb: CallbackQuery, state: FSMContext):
    target_id = int(cb.data.removeprefix("heist_car_target_"))
    thief, target = get_user(cb.from_user.id), get_user(target_id)
    if not target or target.get("car") not in CARS_CATALOG:
        return await cb.answer("У владельца больше нет этой машины.", show_alert=True)
    if thief.get("car") not in (None, "", "none") or car_recovery_pending(thief):
        return await cb.answer("Твой гараж уже занят.", show_alert=True)
    if not thief.get("pass_blackmarket"):
        return await cb.answer("Нужен пропуск чёрного рынка!", show_alert=True)
    if thief.get("lockpicks", 0) < 1:
        return await cb.answer("Нужна отмычка с чёрного рынка!", show_alert=True)
    if thief.get("last_car_theft") and datetime.now() - datetime.fromisoformat(thief["last_car_theft"]) < timedelta(hours=1):
        return await cb.answer("После угона нужно подождать час.", show_alert=True)
    ok, reason = check_status(cb.from_user.id)
    if not ok: return await cb.answer(reason, show_alert=True)
    sequence = [random.randint(1, 4) for _ in range(4)]
    save(cb.from_user.id, lockpicks=thief["lockpicks"] - 1, last_car_theft=datetime.now().isoformat())
    await state.set_state(HeistStates.car_door)
    await state.update_data(target_id=target_id, bot_target=False, sequence=sequence, progress=0)
    await cb.message.edit_text(sequence_prompt("🚘 <b>Взлом двери</b>", sequence), reply_markup=sequence_keyboard("heist_car_door", 4), parse_mode="HTML")
    await cb.answer("Отмычка использована.")

@dp.callback_query(F.data == "heist_car_bot")
async def heist_car_bot_start(cb: CallbackQuery, state: FSMContext):
    thief = get_user(cb.from_user.id)
    if thief.get("car") not in (None, "", "none") or car_recovery_pending(thief):
        return await cb.answer("Твой гараж уже занят. Сначала освободи свою машину.", show_alert=True)
    if not thief.get("pass_blackmarket"):
        return await cb.answer("Нужен пропуск чёрного рынка!", show_alert=True)
    if thief.get("lockpicks", 0) < 1:
        return await cb.answer("Нужна отмычка с чёрного рынка!", show_alert=True)
    if thief.get("last_bot_car_theft") and datetime.now() - datetime.fromisoformat(thief["last_bot_car_theft"]) < timedelta(minutes=30):
        return await cb.answer("Угон машины бота будет доступен через 30 минут после прошлой попытки.", show_alert=True)
    ok, reason = check_status(cb.from_user.id)
    if not ok:
        return await cb.answer(reason, show_alert=True)
    bot_car = random.choice(("car_vaz_2107", "car_vaz_2109", "car_granta"))
    sequence = [random.randint(1, 4) for _ in range(4)]
    save(cb.from_user.id, lockpicks=thief["lockpicks"] - 1, last_bot_car_theft=datetime.now().isoformat())
    await state.set_state(HeistStates.car_door)
    await state.update_data(target_id=0, bot_target=True, bot_car=bot_car, sequence=sequence, progress=0)
    await cb.message.edit_text(sequence_prompt("🚘 <b>Взлом двери машины бота</b>", sequence), reply_markup=sequence_keyboard("heist_car_door", 4), parse_mode="HTML")
    await cb.answer("Отмычка использована.")

@dp.callback_query(HeistStates.car_door, F.data.startswith("heist_car_door_"))
async def heist_car_door_step(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data(); sequence = data["sequence"]; progress = data["progress"]
    door_title = "🚘 <b>Взлом двери машины бота</b>" if data.get("bot_target") else "🚘 <b>Взлом двери</b>"
    guess = int(cb.data.rsplit("_", 1)[1])
    if guess != sequence[progress]:
        await state.update_data(progress=0)
        await cb.message.edit_text("❌ Неверная цифра! Взлом двери сбросился. Начни код заново.\n\n" + sequence_prompt(door_title, sequence), reply_markup=sequence_keyboard("heist_car_door", 4), parse_mode="HTML")
        return await cb.answer("Код сброшен.", show_alert=True)
    progress += 1
    if progress < len(sequence):
        await state.update_data(progress=progress)
        await cb.message.edit_text(sequence_prompt(door_title, sequence, progress), reply_markup=sequence_keyboard("heist_car_door", 4), parse_mode="HTML")
        return await cb.answer(f"Верно: {progress}/4")
    sequence = [random.randint(1, 3) for _ in range(3)]
    await state.set_state(HeistStates.car_ignition)
    await state.update_data(sequence=sequence, progress=0)
    await cb.message.edit_text(sequence_prompt("🔑 <b>Заведи машину</b>", sequence), reply_markup=sequence_keyboard("heist_car_ignition", 3), parse_mode="HTML")
    await cb.answer("Дверь открыта!")

@dp.callback_query(HeistStates.car_ignition, F.data.startswith("heist_car_ignition_"))
async def heist_car_ignition_step(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data(); sequence = data["sequence"]; progress = data["progress"]
    guess = int(cb.data.rsplit("_", 1)[1])
    if guess != sequence[progress]:
        await state.update_data(progress=0)
        await cb.message.edit_text("❌ Неверный провод! Запуск сброшен. Повтори всю комбинацию.\n\n" + sequence_prompt("🔑 <b>Заведи машину</b>", sequence), reply_markup=sequence_keyboard("heist_car_ignition", 3), parse_mode="HTML")
        return await cb.answer("Комбинация сброшена.", show_alert=True)
    progress += 1
    if progress < len(sequence):
        await state.update_data(progress=progress)
        await cb.message.edit_text(sequence_prompt("🔑 <b>Заведи машину</b>", sequence, progress), reply_markup=sequence_keyboard("heist_car_ignition", 3), parse_mode="HTML")
        return await cb.answer(f"Верно: {progress}/3")
    if data.get("bot_target"):
        thief = get_user(cb.from_user.id)
        car_key = data.get("bot_car")
        if car_key not in CARS_CATALOG or thief.get("car") not in (None, "", "none"):
            await state.clear()
            return await cb.answer("Машина уже недоступна или твой гараж занят.", show_alert=True)
        glovebox_cash = random.randint(5_000, 40_000)
        save(cb.from_user.id, car=car_key, car_protection=0, money=thief["money"] + glovebox_cash)
        await state.clear()
        car_name = CARS_CATALOG[car_key][0]
        log_player_action(cb.from_user, f"УГОН МАШИНЫ БОТА: получена {car_name}, из бардачка забрано {glovebox_cash} ₽")
        await cb.message.edit_text(f"✅ Ты угнал машину бота!\n🚘 Машина: {car_name}\n💵 В бардачке: +{glovebox_cash:,} ₽".replace(",", " "))
        return await cb.answer("Машина угнана!")
    target_id = data["target_id"]
    thief, target = get_user(cb.from_user.id), get_user(target_id)
    car_key = target.get("car") if target else None
    if car_key not in CARS_CATALOG or thief.get("car") not in (None, "", "none"):
        await state.clear()
        return await cb.answer("Машина уже недоступна или твой гараж занят.", show_alert=True)
    if target.get("car_protection", 0) > 0:
        remaining = target["car_protection"] - 1
        save(target_id, car_protection=remaining)
        await state.clear()
        if remaining > 0:
            status = f"🛡 Защита сработала! Осталось блокировок: {remaining}/5."
            owner_notice = f"🛡 Система защиты остановила угон машины {CARS_CATALOG[car_key][0]}. Осталось блокировок: {remaining}/5."
        else:
            status = "🛡 Защита остановила угон, но система сломалась. Купи новую за 500 000 ₽ в профиле."
            owner_notice = f"🛡 Защита остановила угон машины {CARS_CATALOG[car_key][0]}, но после пятого срабатывания сломалась. Купи новую за 500 000 ₽ в профиле."
        log_player_action(cb.from_user, f"ПОПЫТКА УГОНА: защита автомобиля {CARS_CATALOG[car_key][0]} сработала, осталось {remaining}/5")
        try: await bot.send_message(target_id, owner_notice)
        except Exception: pass
        await cb.message.edit_text(status)
        return await cb.answer("Угон заблокирован!")
    glovebox_cash = min(target["money"], random.randint(50_000, 250_000))
    if target.get("car_insurance", 0):
        recovery_at=(datetime.now()+timedelta(hours=6)).isoformat()
        save(target_id,car="none",car_protection=0,car_insurance=0,car_recovery_key=car_key,car_recovery_at=recovery_at,money=target["money"]-glovebox_cash)
        save(cb.from_user.id,money=thief["money"]+glovebox_cash)
        await state.clear()
        car_name=CARS_CATALOG[car_key][0]
        log_player_action(cb.from_user,f"ПОПЫТКА УГОНА ЗАСТРАХОВАННОГО АВТО: {car_name} застрахован, из бардачка забрано {glovebox_cash} ₽")
        try:await bot.send_message(target_id,f"🚨 Машину {car_name} угнали, но страховка отследила её. Возврат в гараж примерно через 6 часов. Из бардачка украли {glovebox_cash:,} ₽.".replace(","," "))
        except Exception:pass
        await cb.message.edit_text(f"🛡 На машине была страховка: GPS-система вернёт её владельцу через 6 часов.\n💵 Из бардачка ты забрал: +{glovebox_cash:,} ₽".replace(","," "))
        return await cb.answer("Страховка вызвала GPS-возврат машины.")
    save(target_id, car="none", car_protection=0, money=target["money"] - glovebox_cash)
    save(cb.from_user.id, car=car_key, car_protection=0, money=thief["money"] + glovebox_cash)
    await state.clear()
    car_name = CARS_CATALOG[car_key][0]
    log_player_action(cb.from_user, f"УГОН: похищена машина {car_name} у {target.get('nickname')} (uid={target_id}), из бардачка забрано {glovebox_cash} ₽")
    try: await bot.send_message(target_id, f"🚨 Твою машину {car_name} угнали! Из бардачка пропало {glovebox_cash:,} ₽.".replace(",", " "))
    except Exception: pass
    await cb.message.edit_text(f"✅ Ты завёл машину и скрылся!\n🚘 Трофей: {car_name}\n💵 В бардачке нашлось: +{glovebox_cash:,} ₽".replace(",", " "))
    await cb.answer("Машина угнана!")

async def finish_house_heist(cb: CallbackQuery, state: FSMContext, target_id: int):
    data = await state.get_data()
    if data.get("bot_target"):
        robber = get_user(cb.from_user.id)
        loot = random.randint(50_000, 100_000)
        save(cb.from_user.id, money=robber["money"] + loot)
        await state.clear()
        log_player_action(cb.from_user, f"ОГРАБЛЕНИЕ ДОМА БОТА: добыча {loot} ₽")
        await cb.message.edit_text(f"✅ Ты обчистил дом бота!\n💰 Добыча: {loot:,} ₽".replace(",", " "))
        await cb.answer("Ограбление удалось!")
        return
    robber, owner = get_user(cb.from_user.id), get_user(target_id)
    if not owner or owner.get("house") not in HOUSES_CATALOG:
        await state.clear()
        await cb.message.edit_text("Дом уже недоступен. Ограбление отменено.")
        return
    loot = owner["money"] // 4
    compensation=0
    if loot>0 and owner.get("house_insurance",0):
        house_value=HOUSES_CATALOG[owner["house"]][1]
        compensation=min(int(loot*0.75),house_value//4)
        save(target_id,money=owner["money"]-loot+compensation,house_insurance=0)
    else:
        save(target_id, money=owner["money"] - loot)
    save(cb.from_user.id, money=robber["money"] + loot)
    await state.clear()
    log_player_action(cb.from_user, f"ОГРАБЛЕНИЕ ДОМА: у {owner.get('nickname')} (uid={target_id}) похищено {loot} ₽")
    victim_note=f"🚨 В твой дом проникли! Украдено {loot:,} ₽.".replace(",", " ")
    if compensation:victim_note+=f"\n🛡 Страховка вернула {compensation:,} ₽. Полис использован.".replace(","," ")
    try: await bot.send_message(target_id,victim_note)
    except Exception: pass
    result_text=f"✅ Ты обчистил дом!\n💰 Добыча: {loot:,} ₽".replace(",", " ")
    if compensation:result_text+=f"\n🛡 Страховка владельца вернула ему {compensation:,} ₽.".replace(","," ")
    await cb.message.edit_text(result_text)
    await cb.answer("Ограбление удалось!")

@dp.callback_query(F.data.startswith("heist_house_target_"))
async def heist_house_start(cb: CallbackQuery, state: FSMContext):
    target_id = int(cb.data.removeprefix("heist_house_target_"))
    robber, owner = get_user(cb.from_user.id), get_user(target_id)
    if not owner or owner.get("house") not in HOUSES_CATALOG:
        return await cb.answer("У владельца больше нет дома.", show_alert=True)
    if not robber.get("pass_blackmarket"):
        return await cb.answer("Нужен пропуск чёрного рынка!", show_alert=True)
    if robber.get("axe", 0) < 1:
        return await cb.answer("Нужен топор с чёрного рынка!", show_alert=True)
    if robber.get("lockpicks", 0) < 1:
        return await cb.answer("Нужна отмычка с чёрного рынка!", show_alert=True)
    if robber.get("last_home_rob") and datetime.now() - datetime.fromisoformat(robber["last_home_rob"]) < timedelta(hours=1):
        return await cb.answer("После ограбления дома нужно подождать час.", show_alert=True)
    ok, reason = check_status(cb.from_user.id)
    if not ok: return await cb.answer(reason, show_alert=True)
    # Топор многоразовый; расходуется только отмычка.
    save(cb.from_user.id, lockpicks=robber["lockpicks"] - 1, last_home_rob=datetime.now().isoformat())
    await state.set_state(HeistStates.house_lock)
    await state.update_data(target_id=target_id, bot_target=False, alarm_checked=False, alarm_disarmed=False)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔎 Проверить сигнализацию",callback_data="house_check_alarm")],[InlineKeyboardButton(text="🚪 Сразу взламывать замок",callback_data="house_skip_alarm")],[InlineKeyboardButton(text="❌ Отмена",callback_data="heist_cancel")]])
    await cb.message.edit_text("🏠 Перед взломом реши, проверить ли дом на сигнализацию. Если пропустить установленную сигнализацию, полиция задержит тебя после взлома.",reply_markup=kb)
    await cb.answer("Топор и отмычка использованы.")

@dp.callback_query(F.data == "heist_house_bot")
async def heist_house_bot_start(cb: CallbackQuery, state: FSMContext):
    robber = get_user(cb.from_user.id)
    if not robber.get("pass_blackmarket"):
        return await cb.answer("Нужен пропуск чёрного рынка!", show_alert=True)
    if robber.get("axe", 0) < 1:
        return await cb.answer("Нужен топор с чёрного рынка!", show_alert=True)
    if robber.get("lockpicks", 0) < 1:
        return await cb.answer("Нужна отмычка с чёрного рынка!", show_alert=True)
    if robber.get("last_bot_home_rob") and datetime.now() - datetime.fromisoformat(robber["last_bot_home_rob"]) < timedelta(minutes=30):
        return await cb.answer("Дом бота можно грабить раз в 30 минут.", show_alert=True)
    ok, reason = check_status(cb.from_user.id)
    if not ok:
        return await cb.answer(reason, show_alert=True)
    save(cb.from_user.id, lockpicks=robber["lockpicks"] - 1, last_bot_home_rob=datetime.now().isoformat())
    await state.set_state(HeistStates.house_lock)
    await state.update_data(target_id=0, bot_target=True, bot_alarm=random.random() < 0.3, alarm_checked=False, alarm_disarmed=False)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Проверить сигнализацию", callback_data="house_check_alarm")],
        [InlineKeyboardButton(text="🚪 Сразу взламывать замок", callback_data="house_skip_alarm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="heist_cancel")],
    ])
    await cb.message.edit_text("🏠 Дом бота: добраться до денег легче, но добыча меньше. На доме может быть сигнализация — пропускать её проверку опасно.", reply_markup=kb)
    await cb.answer("Отмычка использована.")

async def begin_house_lock(cb: CallbackQuery,state: FSMContext,target_id: int,alarm_checked: bool,alarm_disarmed: bool=False,bot_target: bool=False):
    sequence=[random.randint(1,4) for _ in range(4)]
    await state.set_state(HeistStates.house_lock)
    await state.update_data(target_id=target_id,sequence=sequence,progress=0,alarm_checked=alarm_checked,alarm_disarmed=alarm_disarmed,bot_target=bot_target)
    await cb.message.edit_text(sequence_prompt("🏠 <b>Взлом замка</b>",sequence),reply_markup=sequence_keyboard("heist_house_lock",4),parse_mode="HTML")

@dp.callback_query(F.data == "house_check_alarm")
async def house_check_alarm(cb: CallbackQuery,state: FSMContext):
    data=await state.get_data();target_id=data.get("target_id");bot_target=data.get("bot_target",False)
    owner=get_user(target_id) if target_id and not bot_target else None
    if not bot_target and not owner:return await cb.answer("Дом больше недоступен.",show_alert=True)
    alarm_active = data.get("bot_alarm",False) if bot_target else owner.get("house_alarm",0)>0
    if not alarm_active:
        await begin_house_lock(cb,state,target_id,True,bot_target=bot_target)
        return await cb.answer("Сигнализация не обнаружена.")
    colors=[random.choice(["green","red","blue"]) for _ in range(3)]
    await state.set_state(HeistStates.house_alarm);await state.update_data(target_id=target_id,bot_target=bot_target,wire_sequence=colors,wire_progress=0,alarm_checked=True)
    await cb.message.edit_text("🚨 <b>Обнаружена сигнализация!</b>\nПерережь провода в правильной последовательности. Ошибка сбросит последовательность.",reply_markup=house_wire_keyboard(),parse_mode="HTML")
    await cb.answer("Сигнализация найдена.")

@dp.callback_query(F.data == "house_skip_alarm")
async def house_skip_alarm(cb: CallbackQuery,state: FSMContext):
    data=await state.get_data();target_id=data.get("target_id");bot_target=data.get("bot_target",False)
    if target_id is None:return await cb.answer("Ограбление уже завершено.",show_alert=True)
    await begin_house_lock(cb,state,target_id,False,bot_target=bot_target)
    await cb.answer("Ты решил не проверять сигнализацию.",show_alert=True)

@dp.callback_query(HeistStates.house_lock, F.data.startswith("heist_house_lock_"))
async def heist_house_lock_step(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data(); sequence = data["sequence"]; progress = data["progress"]
    guess = int(cb.data.rsplit("_", 1)[1])
    if guess != sequence[progress]:
        await state.update_data(progress=0)
        await cb.message.edit_text("❌ Код не подошёл. Замок сброшен — повтори последовательность.\n\n" + sequence_prompt("🏠 <b>Взлом замка</b>", sequence), reply_markup=sequence_keyboard("heist_house_lock", 4), parse_mode="HTML")
        return await cb.answer("Код сброшен.", show_alert=True)
    progress += 1
    if progress < len(sequence):
        await state.update_data(progress=progress)
        await cb.message.edit_text(sequence_prompt("🏠 <b>Взлом замка</b>", sequence, progress), reply_markup=sequence_keyboard("heist_house_lock", 4), parse_mode="HTML")
        return await cb.answer(f"Верно: {progress}/4")
    target_id = data["target_id"]
    owner = get_user(target_id)
    bot_alarm = data.get("bot_target") and data.get("bot_alarm")
    player_alarm = owner and owner.get("house_alarm", 0) > 0
    if (bot_alarm or player_alarm) and not data.get("alarm_disarmed",False):
        if player_alarm:save(target_id,house_alarm=max(0,owner.get("house_alarm",0)-1))
        save(cb.from_user.id,jail_time=(datetime.now()+timedelta(minutes=5)).isoformat())
        await state.clear()
        if not data.get("bot_target"):
            try:await bot.send_message(target_id,"🚨 Сигнализация вызвала полицию! Налётчик задержан при попытке ограбления дома.")
            except Exception:pass
        await cb.message.edit_text("🚨 Сработала сигнализация! Полиция задержала тебя. КПЗ — 5 минут.")
        return await cb.answer("Пропуск проверки сигнализации стоил тебе свободы.",show_alert=True)
    await finish_house_heist(cb, state, target_id)

@dp.callback_query(HeistStates.house_alarm, F.data.startswith("heist_house_wire_"))
async def heist_house_wire_step(cb: CallbackQuery,state: FSMContext):
    data=await state.get_data();sequence=data.get("wire_sequence",[]);progress=int(data.get("wire_progress",0));color=cb.data.removeprefix("heist_house_wire_")
    if not sequence or color not in {"green","red","blue"}:return await cb.answer("Этап взлома сбросился. Отмени ограбление и начни заново.",show_alert=True)
    if color!=sequence[progress]:
        await state.update_data(wire_progress=0)
        await cb.message.edit_text("❌ Не тот провод. Сигнализация осталась цела — начни последовательность заново.",reply_markup=house_wire_keyboard())
        return await cb.answer("Последовательность сброшена.",show_alert=True)
    progress+=1
    if progress<len(sequence):
        await state.update_data(wire_progress=progress)
        await cb.answer(f"Провод принят: {progress}/3")
        return
    target_id=data["target_id"];owner=get_user(target_id) if target_id and not data.get("bot_target") else None
    if owner and owner.get("house_alarm",0)>0:save(target_id,house_alarm=owner["house_alarm"]-1)
    await state.update_data(alarm_disarmed=True,alarm_checked=True)
    await begin_house_lock(cb,state,target_id,True,True,bot_target=data.get("bot_target",False))
    await cb.answer("Сигнализация отключена. Переходи к замку.")

# ==================== ПЕРЕВОД ДЕНЕГ ====================
@dp.message(F.text == "💸 Дать денег")
async def transfer_menu(message: Message):
    u = get_user(message.from_user.id)
    if not u.get("transfer_control_unlocked", 0):
        transfer_toggle = InlineKeyboardButton(text="🚫 Отключить платежи (10 ⭐)", callback_data="donate_misc_transfer_control")
    elif u.get("incoming_transfers_blocked", 0):
        transfer_toggle = InlineKeyboardButton(text="✅ Разрешить платежи", callback_data="allow_incoming_transfers")
    else:
        transfer_toggle = InlineKeyboardButton(text="🚫 Отменить платежи", callback_data="block_incoming_transfers")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔍 Выбрать игрока", callback_data="transfer_page_0")], [transfer_toggle], [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]])
    status = "Входящие переводы отключены." if u.get("incoming_transfers_blocked", 0) else "Входящие переводы разрешены."
    await message.answer(f"💸 <b>Перевод денег:</b>\n{status}", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "block_incoming_transfers")
async def block_incoming_transfers(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if not u.get("transfer_control_unlocked", 0):
        return await cb.answer("Сначала разблокируй настройку за 10 ⭐ в донате → Разное.", show_alert=True)
    save(cb.from_user.id, incoming_transfers_blocked=1)
    log_player_action(cb.from_user, "ВХОДЯЩИЕ ПЕРЕВОДЫ ОТКЛЮЧЕНЫ")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔍 Выбрать игрока", callback_data="transfer_page_0")], [InlineKeyboardButton(text="✅ Разрешить платежи", callback_data="allow_incoming_transfers")], [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]])
    await cb.message.edit_text("💸 <b>Перевод денег:</b>\nВходящие переводы отключены.", reply_markup=kb, parse_mode="HTML")
    await cb.answer("Переводы тебе отключены.", show_alert=True)

@dp.callback_query(F.data == "allow_incoming_transfers")
async def allow_incoming_transfers(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if not u.get("transfer_control_unlocked", 0):
        return await cb.answer("Сначала разблокируй настройку за 10 ⭐ в донате → Разное.", show_alert=True)
    save(cb.from_user.id, incoming_transfers_blocked=0)
    log_player_action(cb.from_user, "ВХОДЯЩИЕ ПЕРЕВОДЫ РАЗРЕШЕНЫ")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔍 Выбрать игрока", callback_data="transfer_page_0")], [InlineKeyboardButton(text="🚫 Отменить платежи", callback_data="block_incoming_transfers")], [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]])
    await cb.message.edit_text("💸 <b>Перевод денег:</b>\nВходящие переводы разрешены.", reply_markup=kb, parse_mode="HTML")
    await cb.answer("Переводы снова разрешены.", show_alert=True)

async def show_transfer_page(message, owner_id: int, page: int, *, edit: bool = False):
    per_page = 10
    cur.execute(
        "SELECT COUNT(*) FROM users WHERE registered=1 AND incoming_transfers_blocked=0 AND user_id!=?",
        (owner_id,),
    )
    total = cur.fetchone()[0]
    if not total:
        text = "В игре пока нет игроков, которым разрешены переводы."
        if edit:
            return await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К переводам", callback_data="transfer_home")]]))
        return await message.answer(text)

    pages = (total + per_page - 1) // per_page
    page = max(0, min(page, pages - 1))
    cur.execute(
        "SELECT user_id, nickname FROM users WHERE registered=1 AND incoming_transfers_blocked=0 AND user_id!=? ORDER BY nickname COLLATE NOCASE, user_id LIMIT ? OFFSET ?",
        (owner_id, per_page, page * per_page),
    )
    page_users = cur.fetchall()
    kb = [[InlineKeyboardButton(text=f"👤 {nick}", callback_data=f"transfer_give_{uid}")] for uid, nick in page_users]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"transfer_page_{page-1}"))
    if page + 1 < pages:
        nav.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"transfer_page_{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="🔙 К переводам", callback_data="transfer_home")])
    text = f"💸 <b>Кому перевести?</b>\nСтраница {page + 1} из {pages} · игроков: {total}"
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    if edit:
        return await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    return await message.answer(text, reply_markup=markup, parse_mode="HTML")

@dp.callback_query(F.data.startswith("transfer_page_"))
async def transfer_list(cb: CallbackQuery):
    try:
        page = int(cb.data.rsplit("_", 1)[1])
    except (ValueError, IndexError):
        return await cb.answer("Не удалось открыть страницу.", show_alert=True)
    await show_transfer_page(cb.message, cb.from_user.id, page, edit=True)
    await cb.answer()

@dp.callback_query(F.data == "transfer_home")
async def transfer_home(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if not u.get("transfer_control_unlocked", 0):
        transfer_toggle = InlineKeyboardButton(text="🚫 Отключить платежи (10 ⭐)", callback_data="donate_misc_transfer_control")
    elif u.get("incoming_transfers_blocked", 0):
        transfer_toggle = InlineKeyboardButton(text="✅ Разрешить платежи", callback_data="allow_incoming_transfers")
    else:
        transfer_toggle = InlineKeyboardButton(text="🚫 Отменить платежи", callback_data="block_incoming_transfers")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Выбрать игрока", callback_data="transfer_page_0")],
        [transfer_toggle],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])
    status = "Входящие переводы отключены." if u.get("incoming_transfers_blocked", 0) else "Входящие переводы разрешены."
    await cb.message.edit_text(f"💸 <b>Перевод денег:</b>\n{status}", reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("transfer_give_"))
async def transfer_choose_amount(cb: CallbackQuery, state: FSMContext):
    target_id = int(cb.data.split("_")[2]); target_u = get_user(target_id)
    if not target_u or target_u.get("incoming_transfers_blocked", 0):
        return await cb.answer("Этот игрок отключил входящие переводы.", show_alert=True)
    await state.set_state(TransferStates.choose_amount); await state.update_data(target_id=target_id)
    await cb.message.answer(f"💰 Сколько денег перевести игроку <b>{target_u['nickname']}</b>?", parse_mode="HTML"); await cb.answer()

@dp.message(TransferStates.choose_amount)
async def transfer_execute(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0: raise ValueError
    except ValueError: return await message.answer("❌ Введи число:")
    data = await state.get_data(); target_id = data["target_id"]
    sender = get_user(message.from_user.id); receiver = get_user(target_id)
    if not receiver or receiver.get("incoming_transfers_blocked", 0):
        await state.clear(); return await message.answer("❌ Этот игрок отключил входящие переводы.")
    if sender["money"] < amount: await state.clear(); return await message.answer("❌ Мало денег!")
    save(sender["user_id"], money=sender["money"] - amount); save(target_id, money=receiver["money"] + amount)
    log_player_action(message.from_user, f"ПЕРЕВОД: от {sender['nickname']} (uid={sender['user_id']}) кому {receiver['nickname']} (uid={target_id}), сумма {amount} ₽")
    await state.clear(); await message.answer(f"✅ Переведено <b>{amount:,} ₽</b> игроку <b>{receiver['nickname']}</b>!".replace(",", " "), parse_mode="HTML")
    try: await bot.send_message(target_id, f"💸 Вам перевели <b>+{amount:,} ₽</b> от <b>{sender['nickname']}</b>".replace(",", " "), parse_mode="HTML")
    except: pass

# ==================== МАГАЗИН (P2P) ====================
SHOP_ITEMS = {
    "food": {"name": "🍔 Еда", "base_cost": 500, "db": "shop_food"},
    "medkit": {"name": "💊 Аптечка", "base_cost": 1500, "db": "shop_medkit"},
    "energy": {"name": "⚡ Энергетик", "base_cost": 1000, "db": "shop_energy"},
    "armor": {"name": "🛡 Бронежилет", "base_cost": 4000, "db": "shop_armor"},
    "briefcase": {"name": "💼 Портфель", "base_cost": 2000, "db": "shop_briefcase"},
    "alarm": {"name": "🚨 Сигнализация дома", "base_cost": 25000, "db": "shop_alarm"}
}

RESOURCE_ITEMS = {
    "stone": "🪨 Камень", "metal": "🔩 Металл", "silver": "🥈 Серебро",
    "flax": "🌿 Лён", "cotton": "☁️ Хлопок", "wood": "🪵 Древесина",
    "weapon_ak47": "🔫 АК-47", "weapon_deagle": "🔫 Дигл", "weapon_m4a1": "🔫 М4А1",
}
WEAPON_ITEMS = {
    "ak47": {"name":"АК-47", "wholesale":100_000, "stock_col":"weapon_shop_ak47_stock", "price_col":"weapon_shop_ak47_price"},
    "deagle": {"name":"Дигл", "wholesale":70_000, "stock_col":"weapon_shop_deagle_stock", "price_col":"weapon_shop_deagle_price"},
    "m4a1": {"name":"М4А1", "wholesale":130_000, "stock_col":"weapon_shop_m4a1_stock", "price_col":"weapon_shop_m4a1_price"},
}

def inventory_amount(uid: int, item_key: str) -> int:
    cur.execute("SELECT amount FROM inventory_items WHERE user_id=? AND item_key=?", (uid, item_key))
    row = cur.fetchone()
    return int(row[0]) if row else 0

def inventory_add(uid: int, item_key: str, amount: int):
    if amount <= 0: return
    cur.execute("INSERT INTO inventory_items(user_id,item_key,amount) VALUES(?,?,?) ON CONFLICT(user_id,item_key) DO UPDATE SET amount=amount+excluded.amount", (uid, item_key, amount))
    conn.commit()

def inventory_take(uid: int, item_key: str, amount: int) -> bool:
    current = inventory_amount(uid, item_key)
    if amount <= 0 or current < amount: return False
    if current == amount:
        cur.execute("DELETE FROM inventory_items WHERE user_id=? AND item_key=?", (uid, item_key))
    else:
        cur.execute("UPDATE inventory_items SET amount=amount-? WHERE user_id=? AND item_key=?", (amount, uid, item_key))
    conn.commit()
    weapon_config=globals().get("BANK_WEAPONS",{}).get(item_key)
    if current==amount and weapon_config:
        save(uid,bank_weapon_pending="",**{weapon_config["uses_column"]:0})
    return True

@dp.message(F.text == "🎒 Инвентарь")
async def inventory_view(message: Message):
    cur.execute("SELECT item_key,amount FROM inventory_items WHERE user_id=? AND amount>0 ORDER BY item_key", (message.from_user.id,))
    items = cur.fetchall()
    text = "🎒 <b>Инвентарь</b>\n\n" + ("\n".join(f"{RESOURCE_ITEMS.get(key, key)}: <b>{amount} шт.</b>" for key, amount in items) if items else "Пока пусто.")
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🛍 Торговая площадка")
async def marketplace_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Продать", callback_data="market_sell")],
        [InlineKeyboardButton(text="🛒 Купить", callback_data="market_buy")],
        [InlineKeyboardButton(text="👤 Мои объявления", callback_data="market_my")],
    ])
    await message.answer("🛍 <b>Торговая площадка</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "market_sell")
async def market_sell(cb: CallbackQuery):
    cur.execute("SELECT item_key,amount FROM inventory_items WHERE user_id=? AND amount>0 ORDER BY item_key", (cb.from_user.id,))
    rows = cur.fetchall()
    if not rows: return await cb.answer("В инвентаре нет ресурсов для продажи.", show_alert=True)
    kb = [[InlineKeyboardButton(text=f"{RESOURCE_ITEMS.get(k,k)} — {a} шт.", callback_data=f"market_sell_{k}")] for k,a in rows]
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="market_back")])
    await cb.message.edit_text("Выбери ресурс для объявления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)); await cb.answer()

@dp.callback_query(F.data.startswith("market_sell_") & (F.data != "market_sell"))
async def market_sell_choose(cb: CallbackQuery, state: FSMContext):
    key = cb.data.removeprefix("market_sell_")
    if key not in RESOURCE_ITEMS: return await cb.answer("Ресурс не найден.", show_alert=True)
    amount = inventory_amount(cb.from_user.id, key)
    if amount <= 0: return await cb.answer("Этого ресурса уже нет в инвентаре.", show_alert=True)
    await state.set_state(MarketplaceStates.listing_amount); await state.update_data(item_key=key)
    await cb.message.answer(f"Сколько выставить? У тебя есть {amount} шт.")
    await cb.answer()

@dp.message(MarketplaceStates.listing_amount)
async def market_listing_amount(message: Message, state: FSMContext):
    try: amount = int(message.text)
    except (ValueError, TypeError): return await message.answer("Введи целое количество.")
    data = await state.get_data(); key = data["item_key"]
    if amount <= 0 or amount > inventory_amount(message.from_user.id, key): return await message.answer("Такого количества нет в инвентаре.")
    await state.update_data(amount=amount); await state.set_state(MarketplaceStates.listing_price)
    await message.answer(f"Введи цену за 1 шт. {RESOURCE_ITEMS[key]} в ₽:")

@dp.message(MarketplaceStates.listing_price)
async def market_listing_price(message: Message, state: FSMContext):
    try: price = int(message.text)
    except (ValueError, TypeError): return await message.answer("Введи целую цену.")
    if price <= 0: return await message.answer("Цена должна быть больше нуля.")
    data = await state.get_data(); uid = message.from_user.id; key = data["item_key"]; amount = data["amount"]
    if not inventory_take(uid, key, amount):
        await state.clear()
        return await message.answer("Ресурса уже не хватает; объявление не создано.")
    cur.execute("INSERT INTO market_listings(seller_id,item_key,quantity,price_each,created_at) VALUES(?,?,?,?,?)", (uid,key,amount,price,datetime.now().isoformat())); conn.commit()
    log_player_action(message.from_user, f"ТОРГОВАЯ ПЛОЩАДКА: выставлено {RESOURCE_ITEMS[key]} ×{amount} по {price} ₽/шт.")
    await state.clear()
    await message.answer(f"✅ Выставлено: {RESOURCE_ITEMS[key]} — {amount} шт. по {price:,} ₽ за штуку.".replace(",", " "))

@dp.callback_query(F.data == "market_buy")
async def market_buy(cb: CallbackQuery):
    cur.execute("SELECT DISTINCT u.user_id,u.nickname FROM market_listings l JOIN users u ON u.user_id=l.seller_id WHERE l.quantity>0 AND l.seller_id!=? ORDER BY u.nickname", (cb.from_user.id,))
    sellers = cur.fetchall()
    if not sellers: return await cb.answer("Сейчас никто не продаёт ресурсы.", show_alert=True)
    kb = [[InlineKeyboardButton(text=f"👤 {nick or 'Игрок'}", callback_data=f"market_seller_{uid}")] for uid,nick in sellers]
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="market_back")])
    await cb.message.edit_text("Выбери продавца:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)); await cb.answer()

@dp.callback_query(F.data.startswith("market_seller_"))
async def market_seller(cb: CallbackQuery):
    seller_id = int(cb.data.rsplit("_",1)[1])
    cur.execute("SELECT id,item_key,quantity,price_each FROM market_listings WHERE seller_id=? AND quantity>0 ORDER BY id", (seller_id,))
    listings = cur.fetchall()
    if not listings: return await cb.answer("У продавца больше нет объявлений.", show_alert=True)
    kb = [[InlineKeyboardButton(text=f"{RESOURCE_ITEMS.get(key,key)} · {qty} шт. · {price:,} ₽/шт.".replace(","," "), callback_data=f"market_listing_{lid}")] for lid,key,qty,price in listings]
    kb.append([InlineKeyboardButton(text="🔙 Продавцы", callback_data="market_buy")])
    cur.execute("SELECT nickname FROM users WHERE user_id=?", (seller_id,)); row=cur.fetchone(); nick=row[0] if row else "Игрок"
    await cb.message.edit_text(f"🏪 Объявления игрока <b>{nick}</b>:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data.startswith("market_listing_"))
async def market_listing_choose(cb: CallbackQuery, state: FSMContext):
    listing_id=int(cb.data.rsplit("_",1)[1]); cur.execute("SELECT item_key,quantity,price_each,seller_id FROM market_listings WHERE id=?", (listing_id,)); row=cur.fetchone()
    if not row: return await cb.answer("Объявление уже снято.", show_alert=True)
    key,qty,price,seller=row
    if key.startswith("weapon_") and not get_user(cb.from_user.id).get("license_weapon",0):return await cb.answer("Для покупки оружия нужна лицензия.",show_alert=True)
    await state.set_state(MarketplaceStates.buy_amount); await state.update_data(listing_id=listing_id)
    await cb.message.answer(f"Сколько купить? На продаже {qty} шт. по {price:,} ₽/шт.".replace(","," ")); await cb.answer()

@dp.message(MarketplaceStates.buy_amount)
async def market_buy_amount(message: Message, state: FSMContext):
    try: amount=int(message.text)
    except (ValueError,TypeError): return await message.answer("Введи целое количество.")
    data=await state.get_data(); cur.execute("SELECT item_key,quantity,price_each,seller_id FROM market_listings WHERE id=?", (data["listing_id"],)); row=cur.fetchone()
    if not row: await state.clear(); return await message.answer("Объявление уже снято.")
    key,stock,price,seller=row
    if amount<=0 or amount>stock: return await message.answer(f"Можно купить от 1 до {stock} шт.")
    total=amount*price; buyer=get_user(message.from_user.id)
    if not buyer or buyer["money"] < total: return await message.answer(f"Не хватает денег. Нужно {total:,} ₽.".replace(","," "))
    await state.update_data(amount=amount,total=total)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Да, купить", callback_data="market_confirm_buy"),InlineKeyboardButton(text="❌ Нет", callback_data="market_cancel_buy")]])
    await message.answer(f"Купить {amount} шт. {RESOURCE_ITEMS[key]} за {total:,} ₽?".replace(","," "),reply_markup=kb)

@dp.callback_query(F.data == "market_confirm_buy")
async def market_confirm_buy(cb: CallbackQuery, state: FSMContext):
    data=await state.get_data(); listing_id=data.get("listing_id"); amount=int(data.get("amount",0))
    cur.execute("BEGIN IMMEDIATE")
    try:
        cur.execute("SELECT item_key,quantity,price_each,seller_id FROM market_listings WHERE id=?", (listing_id,)); row=cur.fetchone()
        buyer=get_user(cb.from_user.id)
        if not row or amount<=0: raise ValueError("Объявление уже снято.")
        key,stock,price,seller_id=row; total=amount*price; seller=get_user(seller_id)
        if key.startswith("weapon_") and not buyer.get("license_weapon",0): raise ValueError("Для покупки оружия нужна лицензия.")
        if amount>stock: raise ValueError("Товара осталось меньше, чем ты выбрал.")
        if not buyer or buyer["money"]<total: raise ValueError("Недостаточно денег.")
        if not seller: raise ValueError("Продавец не найден.")
        cur.execute("UPDATE users SET money=money-? WHERE user_id=?", (total,cb.from_user.id))
        cur.execute("UPDATE users SET money=money+? WHERE user_id=?", (total,seller_id))
        cur.execute("INSERT INTO inventory_items(user_id,item_key,amount) VALUES(?,?,?) ON CONFLICT(user_id,item_key) DO UPDATE SET amount=amount+excluded.amount",(cb.from_user.id,key,amount))
        if stock==amount: cur.execute("DELETE FROM market_listings WHERE id=?",(listing_id,))
        else: cur.execute("UPDATE market_listings SET quantity=quantity-? WHERE id=?",(amount,listing_id))
        conn.commit()
    except (ValueError,Exception) as exc:
        conn.rollback(); await state.clear(); return await cb.answer(str(exc),show_alert=True)
    await state.clear(); log_player_action(cb.from_user,f"ТОРГОВАЯ ПЛОЩАДКА: куплено {amount} {key} за {total} ₽ у uid={seller_id}")
    await cb.message.edit_text(f"✅ Куплено {amount} шт. {RESOURCE_ITEMS[key]} за {total:,} ₽.".replace(","," ")); await cb.answer()

@dp.callback_query(F.data == "market_cancel_buy")
async def market_cancel_buy(cb: CallbackQuery,state: FSMContext):
    await state.clear(); await cb.message.edit_text("Покупка отменена."); await cb.answer()

@dp.callback_query(F.data == "market_my")
async def market_my(cb: CallbackQuery):
    cur.execute("SELECT id,item_key,quantity,price_each FROM market_listings WHERE seller_id=? AND quantity>0 ORDER BY id",(cb.from_user.id,)); rows=cur.fetchall()
    if not rows: return await cb.answer("У тебя нет активных объявлений.",show_alert=True)
    kb=[[InlineKeyboardButton(text=f"❌ Снять {RESOURCE_ITEMS.get(key,key)} · {qty} шт.",callback_data=f"market_cancel_{lid}")] for lid,key,qty,_ in rows]
    kb.append([InlineKeyboardButton(text="🔙 Назад",callback_data="market_back")])
    text="👤 <b>Твои объявления:</b>\n"+"\n".join(f"{RESOURCE_ITEMS.get(k,k)} — {q} шт. по {p:,} ₽/шт.".replace(","," ") for _,k,q,p in rows)
    await cb.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data.startswith("market_cancel_"))
async def market_cancel_listing(cb: CallbackQuery):
    lid=int(cb.data.rsplit("_",1)[1]); cur.execute("SELECT item_key,quantity FROM market_listings WHERE id=? AND seller_id=?",(lid,cb.from_user.id)); row=cur.fetchone()
    if not row: return await cb.answer("Объявление не найдено.",show_alert=True)
    key,qty=row; cur.execute("DELETE FROM market_listings WHERE id=? AND seller_id=?",(lid,cb.from_user.id)); conn.commit(); inventory_add(cb.from_user.id,key,qty)
    log_player_action(cb.from_user, f"ТОРГОВАЯ ПЛОЩАДКА: снято объявление, возвращено {RESOURCE_ITEMS[key]} ×{qty}")
    await cb.answer("Объявление снято, товар возвращён.",show_alert=True)

@dp.callback_query(F.data == "market_back")
async def market_back(cb: CallbackQuery):
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📤 Продать",callback_data="market_sell")],[InlineKeyboardButton(text="🛒 Купить",callback_data="market_buy")],[InlineKeyboardButton(text="👤 Мои объявления",callback_data="market_my")]])
    await cb.message.edit_text("🛍 <b>Торговая площадка</b>",reply_markup=kb,parse_mode="HTML"); await cb.answer()

@dp.message(F.text == "🔫 Магазин оружия")
async def weapon_shop_browse(message: Message):
    u=get_user(message.from_user.id)
    if not u.get("license_weapon"):
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚘 Перейти в МРЭО",callback_data="mreo_menu")]])
        return await message.answer("Для покупки оружия нужна лицензия на оружие из МРЭО.",reply_markup=kb)
    prices={key:public_weapon_price(u,key) for key in ("ak47","deagle","m4a1")}
    kb=[[InlineKeyboardButton(text=f"{WEAPON_ITEMS[key]['name']} — {price:,} ₽".replace(","," "),callback_data=f"buy_public_weapon_{key}")] for key,price in prices.items()]
    kb.append([InlineKeyboardButton(text="🏪 Магазины игроков",callback_data="weapon_player_shops")])
    await message.answer("🔫 <b>Оружейный магазин</b>\nДля покупки требуется лицензия на оружие.",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML")

@dp.callback_query(F.data.startswith("buy_public_weapon_"))
async def buy_public_weapon(cb: CallbackQuery):
    key=cb.data.removeprefix("buy_public_weapon_");info=WEAPON_ITEMS.get(key);u=get_user(cb.from_user.id)
    if not info:return await cb.answer("Оружие не найдено.",show_alert=True)
    if not u.get("license_weapon"):return await cb.answer("Нужна лицензия на оружие из МРЭО.",show_alert=True)
    price=public_weapon_price(u,key)
    if u["money"]<price:return await cb.answer(f"Не хватает денег: {price:,} ₽.".replace(","," "),show_alert=True)
    save(cb.from_user.id,money=u["money"]-price);inventory_add(cb.from_user.id,f"weapon_{key}",1)
    log_player_action(cb.from_user,f"КУПЛЕНО ОРУЖИЕ: {info['name']} за {price} ₽ в городском магазине")
    await cb.answer(f"Куплено: {info['name']}.",show_alert=True)

@dp.callback_query(F.data == "weapon_player_shops")
async def weapon_player_shops(cb: CallbackQuery):
    u=get_user(cb.from_user.id)
    if not u.get("license_weapon"):return await cb.answer("Для покупки нужна лицензия на оружие.",show_alert=True)
    cur.execute("SELECT user_id,weapon_shop_name,nickname FROM users WHERE weapon_shop_name!=''")
    shops=cur.fetchall()
    if not shops:return await cb.answer("Пока нет работающих оружейных магазинов.",show_alert=True)
    kb=[[InlineKeyboardButton(text=f"🔫 {name} · {nick or 'Владелец'}",callback_data=f"weapon_view_{uid}")] for uid,name,nick in shops if uid!=cb.from_user.id]
    if not kb:return await cb.answer("Других оружейных магазинов пока нет.",show_alert=True)
    await cb.message.answer("Выбери оружейный магазин:",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb));await cb.answer()

@dp.callback_query(F.data == "weapon_shop_buy_business")
async def weapon_shop_buy_business(cb: CallbackQuery):
    u=get_user(cb.from_user.id)
    if u.get("weapon_shop_name"):return await cb.answer("У тебя уже есть оружейный магазин.",show_alert=True)
    if u["money"]<3_000_000:return await cb.answer("Нужно 3 000 000 ₽.",show_alert=True)
    save(cb.from_user.id,money=u["money"]-3_000_000,weapon_shop_name=f"Оружейный магазин {u.get('nickname','')}",weapon_shop_last_income=datetime.now().isoformat())
    log_player_action(cb.from_user,"КУПЛЕН ОРУЖЕЙНЫЙ МАГАЗИН за 3 000 000 ₽")
    await cb.answer("Оружейный магазин открыт!",show_alert=True)
    await cb.message.edit_text("🏢 Бизнес:",reply_markup=business_menu(get_user(cb.from_user.id)))

@dp.callback_query(F.data == "weapon_shop_manage")
async def weapon_shop_manage(cb: CallbackQuery):
    u=get_user(cb.from_user.id)
    if not u.get("weapon_shop_name"):return await cb.answer("У тебя нет оружейного магазина.",show_alert=True)
    rows=[]
    for key,info in WEAPON_ITEMS.items():
        rows.append([InlineKeyboardButton(text=f"{info['name']} · склад {u.get(info['stock_col'],0)} · цена {u.get(info['price_col'],0):,} ₽".replace(","," "),callback_data=f"weapon_manage_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Бизнес",callback_data="business_back")])
    await cb.message.edit_text(f"🔫 <b>{u['weapon_shop_name']}</b>\nЗакупка оружия и настройка цен:",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),parse_mode="HTML");await cb.answer()

@dp.callback_query(F.data.startswith("weapon_manage_"))
async def weapon_manage_item(cb: CallbackQuery):
    key=cb.data.removeprefix("weapon_manage_");info=WEAPON_ITEMS.get(key);u=get_user(cb.from_user.id)
    if not info or not u.get("weapon_shop_name"):return await cb.answer("Товар или магазин не найден.",show_alert=True)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"📦 Закупить ({info['wholesale']:,} ₽/шт.)".replace(","," "),callback_data=f"weapon_restock_{key}")],[InlineKeyboardButton(text="💰 Установить цену",callback_data=f"weapon_price_{key}")],[InlineKeyboardButton(text="🔙 В магазин",callback_data="weapon_shop_manage")]])
    await cb.message.edit_text(f"{info['name']}\nНа складе: {u.get(info['stock_col'],0)} шт.\nЦена продажи: {u.get(info['price_col'],0):,} ₽/шт.".replace(","," "),reply_markup=kb);await cb.answer()

@dp.callback_query(F.data.startswith("weapon_restock_"))
async def weapon_restock_start(cb: CallbackQuery,state: FSMContext):
    key=cb.data.removeprefix("weapon_restock_");info=WEAPON_ITEMS.get(key)
    if not info:return await cb.answer("Товар не найден.",show_alert=True)
    await state.set_state(WeaponShopStates.restock_amount);await state.update_data(weapon_key=key)
    await cb.message.answer(f"Сколько единиц {info['name']} закупить по {info['wholesale']:,} ₽ за штуку?".replace(","," "));await cb.answer()

@dp.message(WeaponShopStates.restock_amount)
async def weapon_restock_amount(message: Message,state: FSMContext):
    try:amount=int(message.text)
    except (ValueError,TypeError):return await message.answer("Введи целое количество.")
    data=await state.get_data();key=data["weapon_key"];info=WEAPON_ITEMS[key];u=get_user(message.from_user.id);cost=amount*info["wholesale"]
    if amount<=0 or amount>10000:return await message.answer("Количество должно быть от 1 до 10 000.")
    if not u.get("weapon_shop_name"):await state.clear();return await message.answer("У тебя больше нет оружейного магазина.")
    if u["money"]<cost:return await message.answer(f"Для закупки нужно {cost:,} ₽.".replace(","," "))
    save(message.from_user.id,money=u["money"]-cost,**{info["stock_col"]:u.get(info["stock_col"],0)+amount});await state.clear()
    await message.answer(f"✅ Закуплено: {info['name']} ×{amount}.")

@dp.callback_query(F.data.startswith("weapon_price_"))
async def weapon_price_start(cb: CallbackQuery,state: FSMContext):
    key=cb.data.removeprefix("weapon_price_")
    if key not in WEAPON_ITEMS:return await cb.answer("Товар не найден.",show_alert=True)
    await state.set_state(WeaponShopStates.set_price);await state.update_data(weapon_key=key)
    await cb.message.answer(f"Введи цену продажи {WEAPON_ITEMS[key]['name']} за 1 штуку:");await cb.answer()

@dp.message(WeaponShopStates.set_price)
async def weapon_price_set(message: Message,state: FSMContext):
    try:price=int(message.text)
    except (ValueError,TypeError):return await message.answer("Введи целую цену.")
    if price<=0:return await message.answer("Цена должна быть больше нуля.")
    data=await state.get_data();info=WEAPON_ITEMS[data["weapon_key"]];save(message.from_user.id,**{info["price_col"]:price});await state.clear()
    await message.answer(f"Цена обновлена: {price:,} ₽.".replace(","," "))

@dp.callback_query(F.data.startswith("weapon_view_"))
async def weapon_view(cb: CallbackQuery):
    buyer=get_user(cb.from_user.id)
    if not buyer.get("license_weapon"):return await cb.answer("Для покупки нужна лицензия на оружие.",show_alert=True)
    seller_id=int(cb.data.rsplit("_",1)[1]);seller=get_user(seller_id)
    if not seller or not seller.get("weapon_shop_name"):return await cb.answer("Этот магазин закрыт.",show_alert=True)
    rows=[]
    for key,info in WEAPON_ITEMS.items():
        stock=seller.get(info["stock_col"],0);price=seller.get(info["price_col"],0)
        if stock>0 and price>0:rows.append([InlineKeyboardButton(text=f"{info['name']} · {price:,} ₽ · в наличии {stock}".replace(","," "),callback_data=f"weapon_buy_{seller_id}_{key}")])
    if not rows:return await cb.answer("В магазине пока нет товаров с установленной ценой.",show_alert=True)
    await cb.message.edit_text(f"🔫 <b>{seller['weapon_shop_name']}</b>\nПродавец: {seller.get('nickname','Игрок')}",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),parse_mode="HTML");await cb.answer()

@dp.callback_query(F.data.startswith("weapon_buy_"))
async def weapon_buy_start(cb: CallbackQuery,state: FSMContext):
    buyer=get_user(cb.from_user.id)
    if not buyer.get("license_weapon"):return await cb.answer("Для покупки нужна лицензия на оружие.",show_alert=True)
    _,_,seller_id,key=cb.data.split("_",3);info=WEAPON_ITEMS.get(key);seller=get_user(int(seller_id))
    if not info or not seller:return await cb.answer("Магазин не найден.",show_alert=True)
    stock=seller.get(info["stock_col"],0);price=seller.get(info["price_col"],0)
    if stock<=0 or price<=0:return await cb.answer("Оружие закончилось или цена не установлена.",show_alert=True)
    await state.set_state(WeaponShopStates.buy_amount);await state.update_data(seller_id=int(seller_id),weapon_key=key)
    await cb.message.answer(f"Сколько штук купить? В наличии {stock}.");await cb.answer()

@dp.message(WeaponShopStates.buy_amount)
async def weapon_buy_amount(message: Message,state: FSMContext):
    try:amount=int(message.text)
    except (ValueError,TypeError):return await message.answer("Введи целое количество.")
    data=await state.get_data();seller=get_user(data["seller_id"]);buyer=get_user(message.from_user.id);info=WEAPON_ITEMS[data["weapon_key"]]
    if amount<=0 or amount>seller.get(info["stock_col"],0):return await message.answer(f"Можно купить от 1 до {seller.get(info['stock_col'],0)} шт.")
    total=amount*seller.get(info["price_col"],0)
    if buyer["money"]<total:return await message.answer(f"Не хватает денег: нужно {total:,} ₽.".replace(","," "))
    await state.update_data(amount=amount,total=total)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Да",callback_data="weapon_confirm_buy"),InlineKeyboardButton(text="❌ Нет",callback_data="weapon_cancel_buy")]])
    await message.answer(f"Подтвердить покупку {info['name']} ×{amount} за {total:,} ₽?".replace(","," "),reply_markup=kb)

@dp.callback_query(F.data == "weapon_confirm_buy")
async def weapon_confirm_buy(cb: CallbackQuery,state: FSMContext):
    data=await state.get_data();seller_id=data.get("seller_id");key=data.get("weapon_key");amount=int(data.get("amount",0));info=WEAPON_ITEMS.get(key);buyer=get_user(cb.from_user.id);seller=get_user(seller_id)
    if not info or not buyer or not buyer.get("license_weapon") or not seller:
        await state.clear()
        return await cb.answer("Покупка недоступна.",show_alert=True)
    stock=seller.get(info["stock_col"],0);price=seller.get(info["price_col"],0);total=amount*price
    if amount<=0 or amount>stock or buyer["money"]<total:return await cb.answer("Изменилась цена/остаток или не хватает денег.",show_alert=True)
    save(cb.from_user.id,money=buyer["money"]-total);save(seller_id,money=seller["money"]+total,**{info["stock_col"]:stock-amount});inventory_add(cb.from_user.id,f"weapon_{key}",amount)
    await state.clear();log_player_action(cb.from_user,f"ПОКУПКА ОРУЖИЯ: {info['name']} ×{amount} за {total} ₽");await cb.message.edit_text(f"✅ Куплено {info['name']} ×{amount}.");await cb.answer()

@dp.callback_query(F.data == "weapon_cancel_buy")
async def weapon_cancel_buy(cb: CallbackQuery,state: FSMContext):
    await state.clear();await cb.message.edit_text("Покупка отменена.");await cb.answer()

@dp.callback_query(F.data == "weapon_shop_collect")
async def weapon_shop_collect(cb: CallbackQuery):
    u=get_user(cb.from_user.id)
    if not u.get("weapon_shop_name"):return await cb.answer("У тебя нет оружейного магазина.",show_alert=True)
    last=u.get("weapon_shop_last_income","")
    if last and datetime.now()-datetime.fromisoformat(last)<timedelta(hours=24):return await cb.answer("Прибыль можно собирать раз в 24 часа.",show_alert=True)
    profit=random.randint(300_000,400_000);save(cb.from_user.id,money=u["money"]+profit,weapon_shop_last_income=datetime.now().isoformat())
    log_player_action(cb.from_user,f"ОРУЖЕЙНЫЙ МАГАЗИН: ежедневная чистая прибыль +{profit} ₽")
    await cb.message.edit_text(f"✅ Оружейный магазин принёс {profit:,} ₽ чистыми.".replace(","," "),reply_markup=business_menu(get_user(cb.from_user.id)));await cb.answer()

@dp.callback_query(F.data == "buy_player_shop")
async def buy_shop_start(cb: CallbackQuery, state: FSMContext):
    u = get_user(cb.from_user.id)
    if u["money"] < 2_000_000: return await cb.answer("Нужно 2 млн ₽!", show_alert=True)
    await state.set_state(ShopStates.create_name); await cb.message.answer("🏪 Введи название для своего магазина:"); await cb.answer()

@dp.message(ShopStates.create_name)
async def buy_shop_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3 or len(name) > 30: return await message.answer("❌ Название от 3 до 30 символов.")
    u = get_user(message.from_user.id)
    if u["money"] < 2_000_000: await state.clear(); return await message.answer("❌ Мало денег.")
    save(message.from_user.id, money=u["money"] - 2_000_000, shop_name=name, last_shop_auto=datetime.now().isoformat()); await state.clear()
    text = f"🎉 Магазин <b>«{name}»</b> куплен!"
    img = IMAGES / "magazin.jpg"
    if img.exists(): await message.answer_photo(FSInputFile(img), caption=text, parse_mode="HTML")
    else: await message.answer(text, parse_mode="HTML")

@dp.callback_query(F.data == "my_shop")
async def my_shop_menu(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if not u.get("shop_name"): return await cb.answer("У тебя нет магазина!", show_alert=True)
    kb = [[InlineKeyboardButton(text=f"{info['name']} | Склад: {u.get(info['db']+'_stock',0)} | Закуп: {info['base_cost']} ₽ | Продажа: {u.get(info['db']+'_price', 0)} ₽".replace(",", " "), callback_data=f"manage_shop_{key}")] for key, info in SHOP_ITEMS.items()]
    if u.get("shop_manager") == 0: kb.append([InlineKeyboardButton(text="👨‍💼 Нанять Управляющего (1 млн ₽)", callback_data="shop_hire_manager")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="business_back")])
    await cb.message.answer(f"⚙️ <b>Магазин «{u['shop_name']}»</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data.startswith("manage_shop_"))
async def manage_shop_item(cb: CallbackQuery):
    item_key = cb.data.replace("manage_shop_", ""); info = SHOP_ITEMS[item_key]; u = get_user(cb.from_user.id)
    stock = u.get(info['db'] + '_stock', 0); price = u.get(info['db'] + '_price', 0)
    kb = [[InlineKeyboardButton(text=f"📦 Закупить (Себестоимость: {info['base_cost']:,} ₽)".replace(",", " "), callback_data=f"restock_{item_key}")], [InlineKeyboardButton(text="💰 Изменить цену", callback_data=f"price_{item_key}")], [InlineKeyboardButton(text="🔙 Назад", callback_data="my_shop")]]
    await cb.message.edit_text(f"{info['name']}\n📦 В наличии: {stock} шт.\n📥 Закупка: {info['base_cost']:,} ₽\n💰 Твоя цена: {price:,} ₽".replace(",", " "), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)); await cb.answer()

@dp.callback_query(F.data.startswith("restock_"))
async def restock_item_start(cb: CallbackQuery, state: FSMContext):
    item_key = cb.data.replace("restock_", ""); info = SHOP_ITEMS[item_key]
    await state.set_state(ShopStates.buy_stock); await state.update_data(item_key=item_key)
    await cb.message.answer(f"📦 Сколько штук товара <b>{info['name']}</b> закупить?\n(Себестоимость: {info['base_cost']:,} ₽/шт):".replace(",", " "), parse_mode="HTML"); await cb.answer()

@dp.message(ShopStates.buy_stock)
async def restock_item_buy(message: Message, state: FSMContext):
    data = await state.get_data(); item_key = data["item_key"]; info = SHOP_ITEMS[item_key]
    try:
        qty = int(message.text)
        if qty <= 0: raise ValueError
    except ValueError: return await message.answer("❌ Введи целое число:")
    cost = qty * info["base_cost"]; u = get_user(message.from_user.id)
    if u["money"] < cost: return await message.answer(f"❌ Нужно {cost:,} ₽.".replace(",", " "))
    stock_col = info["db"] + "_stock"
    save(message.from_user.id, money=u["money"] - cost, **{stock_col: u.get(stock_col, 0) + qty})
    await state.clear(); await message.answer(f"✅ Закуплено {qty} шт.!", parse_mode="HTML")

@dp.callback_query(F.data.startswith("price_"))
async def set_price_start(cb: CallbackQuery, state: FSMContext):
    item_key = cb.data.replace("price_", ""); await state.set_state(ShopStates.set_price); await state.update_data(item_key=item_key)
    await cb.message.answer(f"💰 Введи цену продажи 1 шт. товара <b>{SHOP_ITEMS[item_key]['name']}</b>:", parse_mode="HTML"); await cb.answer()

@dp.message(ShopStates.set_price)
async def set_price_input(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        if price < 100: return await message.answer("Мин. цена 100 ₽.")
    except ValueError: return await message.answer("❌ Введи число:")
    data = await state.get_data(); item_key = data["item_key"]; info = SHOP_ITEMS[item_key]
    save(message.from_user.id, **{info["db"] + "_price": price}); await state.clear()
    await message.answer(f"✅ Новая цена: {price:,} ₽.".replace(",", " "), parse_mode="HTML")

@dp.callback_query(F.data == "shop_hire_manager")
async def shop_hire_manager(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if u["money"] < 1_000_000: return await cb.answer("Нужно 1 млн!", show_alert=True)
    save(cb.from_user.id, money=u["money"] - 1_000_000, shop_manager=1)
    await cb.message.answer("👨‍💼 <b>Управляющий нанят!</b>", parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data == "collect_shop_daily")
async def collect_shop_daily(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if not u or not u.get("shop_name"):
        return await cb.answer("Сначала нужен собственный магазин.", show_alert=True)
    last = u.get("last_shop_auto", "")
    if last:
        elapsed = datetime.now() - datetime.fromisoformat(last)
        if elapsed < timedelta(hours=24):
            seconds_left = int((timedelta(hours=24) - elapsed).total_seconds())
            hours, minutes = divmod(seconds_left // 60, 60)
            return await cb.answer(f"Следующий сбор через {hours} ч. {minutes} мин.", show_alert=True)
    profit = random.randint(200_000, 300_000)
    save(cb.from_user.id, money=u["money"] + profit, last_shop_auto=datetime.now().isoformat())
    log_player_action(cb.from_user, f"ПАССИВНЫЙ ДОХОД МАГАЗИНА: +{profit} ₽ чистыми")
    await cb.answer(f"Магазин принёс {profit:,} ₽ чистыми!".replace(",", " "), show_alert=True)
    await cb.message.edit_text("🏢 <b>Бизнес:</b>", reply_markup=business_menu(get_user(cb.from_user.id)), parse_mode="HTML")

@dp.callback_query(F.data == "browse_shops")
async def browse_shops(cb: CallbackQuery):
    cur.execute("SELECT user_id, shop_name, nickname FROM users WHERE shop_name != ''"); shops = cur.fetchall()
    if not shops: return await cb.answer("Пока нет магазинов.", show_alert=True)
    kb = [[InlineKeyboardButton(text=f"🏪 {s_name} (Владелец: {nick})", callback_data=f"view_p2p_{uid}")] for uid, s_name, nick in shops]
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_shop")])
    await cb.message.edit_text("🏪 <b>Магазины игроков:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data.startswith("view_p2p_"))
async def view_p2p_shop(cb: CallbackQuery):
    owner_id = int(cb.data.split("_")[2]); owner = get_user(owner_id)
    if not owner or not owner.get("shop_name"): return await cb.answer("Магазин закрыт!", show_alert=True)
    kb = []
    for key, info in SHOP_ITEMS.items():
        stock = owner.get(info["db"] + "_stock", 0); price = owner.get(info["db"] + "_price", 0)
        if stock > 0: kb.append([InlineKeyboardButton(text=f"{info['name']} | {price:,} ₽ (В наличии: {stock})".replace(",", " "), callback_data=f"buy_p2p_{owner_id}_{key}")])
    if not kb: return await cb.answer("В магазине нет товаров!", show_alert=True)
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="browse_shops")])
    await cb.message.edit_text(f"🏪 <b>Магазин «{owner['shop_name']}»</b>\nВладелец: {owner['nickname']}", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data.startswith("buy_p2p_"))
async def buy_p2p_item(cb: CallbackQuery):
    parts = cb.data.split("_"); owner_id = int(parts[2]); item_key = parts[3]; info = SHOP_ITEMS[item_key]
    owner = get_user(owner_id); buyer = get_user(cb.from_user.id)
    stock = owner.get(info["db"] + "_stock", 0); price = owner.get(info["db"] + "_price", 0)
    if stock <= 0: return await cb.answer("Товар закончился!", show_alert=True)
    if item_key == "alarm" and buyer.get("house") not in HOUSES_CATALOG: return await cb.answer("Для сигнализации сначала нужен свой дом.",show_alert=True)
    if item_key == "alarm" and buyer.get("house_alarm",0)>0: return await cb.answer("Сигнализация уже установлена.",show_alert=True)
    if buyer["money"] < price: return await cb.answer(f"Мало денег! Нужно {price:,} ₽".replace(",", " "), show_alert=True)
    save(cb.from_user.id, money=buyer["money"] - price); save(owner_id, money=owner["money"] + price, **{info["db"] + "_stock": stock - 1})
    if item_key == "food": update_stats(cb.from_user.id, hunger_add=-40); effect = "-40 к голоду"
    elif item_key == "medkit": update_stats(cb.from_user.id, health_add=40); effect = "+40 к здоровью"
    elif item_key == "energy": save(cb.from_user.id, energy_drinks=buyer.get("energy_drinks",0)+1); effect = "Добавлен в инвентарь"
    elif item_key == "armor": save(cb.from_user.id, armor=buyer.get("armor",0)+1); effect = "Добавлен в инвентарь"
    elif item_key == "briefcase": save(cb.from_user.id, briefcase=buyer.get("briefcase",0)+1); effect = "Добавлен в инвентарь"
    elif item_key == "alarm": save(cb.from_user.id, house_alarm=5); effect = "Сигнализация установлена на 5 срабатываний"
    await cb.message.answer(f"🛍 Ты купил <b>{info['name']}</b> в магазине <b>«{owner['shop_name']}»</b> за {price:,} ₽!\n✨ Эффект: {effect}.".replace(",", " "), parse_mode="HTML")
    try: await bot.send_message(owner_id, f"🔔 В твоем магазине купили <b>{info['name']}</b>!\n💰 +{price:,} ₽ на баланс.".replace(",", " "), parse_mode="HTML")
    except: pass
    await cb.answer("Покупка успешна!")

@dp.callback_query(F.data == "business_back")
async def business_back(cb: CallbackQuery):
    await cb.message.delete(); await cb.message.answer("🏢 <b>Бизнес:</b>", reply_markup=business_menu(get_user(cb.from_user.id)), parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data == "back_shop")
async def back_shop(cb: CallbackQuery):
    await cb.message.edit_text("🛒 <b>Магазин:</b>", reply_markup=shop_menu(get_user(cb.from_user.id)), parse_mode="HTML"); await cb.answer()

# ==================== БИРЖА / КЕЙСЫ / АДМИНКА ====================
@dp.message(F.text == "📈 Биржа")
async def exchange_menu(message: Message):
    hour = datetime.now().hour; mult = 1 + (math.sin(hour) * 0.2)
    prices = {"btc": int(2_000_000 * mult), "eth": int(150_000 * mult), "gold": int(50_000 * mult)}
    u = get_user(message.from_user.id)
    kb = [[InlineKeyboardButton(text=f"₿ BTC ({prices['btc']:,} ₽) Купить", callback_data="buy_btc")],[InlineKeyboardButton(text=f"Ξ ETH ({prices['eth']:,} ₽) Купить", callback_data="buy_eth")],[InlineKeyboardButton(text=f"🥇 Золото ({prices['gold']:,} ₽) Купить", callback_data="buy_gold")],[InlineKeyboardButton(text="💸 Продать всё", callback_data="sell_all")],[InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]]
    await message.answer(f"📈 <b>Биржа:</b>\nУ тебя: BTC({u.get('btc',0)}) | ETH({u.get('eth',0)}) | Золото({u.get('gold',0)})", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@dp.callback_query(F.data.in_({"buy_btc", "buy_eth", "buy_gold"}))
async def exchange_buy(cb: CallbackQuery):
    asset = cb.data.replace("buy_", "")
    if asset not in ["btc", "eth", "gold"]: return await cb.answer("Ошибка!")
    hour = datetime.now().hour; mult = 1 + (math.sin(hour) * 0.2)
    prices = {"btc": int(2_000_000 * mult), "eth": int(150_000 * mult), "gold": int(50_000 * mult)}
    u = get_user(cb.from_user.id); price = prices[asset]
    if u["money"] < price: return await cb.answer("Мало денег!", show_alert=True)
    save(cb.from_user.id, money=u["money"] - price, **{asset: u.get(asset, 0) + 1})
    await cb.message.answer(f"📈 Куплено 1 {asset.upper()} за {price:,} ₽".replace(",", " ")); await cb.answer()

@dp.callback_query(F.data == "sell_all")
async def exchange_sell(cb: CallbackQuery):
    u = get_user(cb.from_user.id); hour = datetime.now().hour; mult = 1 + (math.sin(hour) * 0.2)
    prices = {"btc": int(2_000_000 * mult), "eth": int(150_000 * mult), "gold": int(50_000 * mult)}
    total = u.get("btc",0)*prices["btc"] + u.get("eth",0)*prices["eth"] + u.get("gold",0)*prices["gold"]
    if total == 0: return await cb.answer("Ничего нет!", show_alert=True)
    save(cb.from_user.id, money=u["money"] + total, btc=0, eth=0, gold=0)
    await cb.message.answer(f"💸 Продано за {total:,} ₽!".replace(",", " ")); await cb.answer()

@dp.message(F.text == "🎁 Кейсы")
async def cases_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📦 Открыть Кейс (100к)", callback_data="open_case")], [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]])
    await message.answer("🎁 <b>Кейсы:</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "open_case")
async def open_case(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if u["money"] < 100_000: return await cb.answer("Кейс стоит 100к!", show_alert=True)
    save(cb.from_user.id, money=u["money"] - 100_000)

    roll = random.random()
    if roll < 0.02:
        result_kind = "vip"
        result_label = "👑 VIP"
    elif roll < 0.04:
        result_kind = "jackpot"
        result_label = "💰 Деньги"
    elif roll < 0.12:
        result_kind = "car"
        result_label = "🚘 Машина"
    elif roll < 0.30:
        result_kind = "big_money"
        result_label = "💰 Деньги"
    elif roll < 0.75:
        result_kind = "money"
        result_label = "💰 Деньги"
    else:
        result_kind = "empty"
        result_label = "🕸 Ничего"

    await cb.answer()
    slots = ["🕸 Ничего", "🚘 Машина", "💰 Деньги", "👑 VIP"]
    delays = (0.8, 0.9, 1.0, 1.1, 1.2, 1.3)
    for frame, delay in enumerate(delays):
        current = result_label if frame == len(delays) - 1 else random.choice(slots)
        display = "   ".join(f"【{item}】" if item == current else item for item in slots)
        await cb.message.edit_text(f"🎰 <b>Кейс открывается · {frame + 1}/{len(delays)}</b>\n\n{display}", parse_mode="HTML")
        await asyncio.sleep(delay)

    if result_kind == "vip":
        days=random.randint(1,4)
        active_tier=vip_config(u)
        try:current_expiry=datetime.fromisoformat(u.get("vip_expires", ""))
        except (TypeError,ValueError):current_expiry=datetime.now()
        now=datetime.now()
        tier_key=u.get("vip_type") if active_tier else "titan"
        base=max(now,current_expiry) if active_tier else now
        expiry=(base+timedelta(days=days)).isoformat()
        save(cb.from_user.id,vip_type=tier_key,vip_expires=expiry,vip_last_hourly=u.get("vip_last_hourly") or now.isoformat())
        text=f"🎁 👑 <b>{VIP_TIERS[tier_key]['name']} на {days} дн.!</b>"
        if active_tier and tier_key!="titan":text+=f"\nТекущий VIP сохранён и продлён на {days} дн."
    elif result_kind == "jackpot": save(cb.from_user.id, money=u["money"]-100_000+1_000_000); text = "🎁 💎 <b>ДЖЕКПОТ!</b> 1 000 000 ₽!"
    elif result_kind == "car": save(cb.from_user.id, car="car_m5", car_protection=0); text = "🎁 🏎 <b>БИНГО!</b> BMW M5 F90!"
    elif result_kind == "big_money": r=random.randint(100_000, 300_000); save(cb.from_user.id, money=u["money"]-100_000+r); text = f"🎁 💰 Ты выбил {r:,} ₽!".replace(",", " ")
    elif result_kind == "money": r=random.randint(10_000, 50_000); save(cb.from_user.id, money=u["money"]-100_000+r); text = f"🎁 💵 Ты выбил {r:,} ₽.".replace(",", " ")
    else: text = "🎁 🕸 Пусто. Не повезло!"

    await cb.message.edit_text(text, parse_mode="HTML")

@dp.message(Command("un_money"))
async def cmd_un_money(message: Message):
    if not is_admin(message.from_user.id): return
    args = message.text.split()
    if len(args) < 3: return await message.answer("⚠️ /un_money [Ник] [Сумма]")
    try: amount = int(args[2])
    except ValueError: return await message.answer("⚠️ Сумма должна быть числом.")
    u = get_user_by_nick(args[1])
    if not u: return await message.answer("⚠️ Игрок не найден.")
    new_money = max(0, u["money"] - amount)
    save(u["user_id"], money=new_money)
    await message.answer(f"✅ У <b>{args[1]}</b> скрытно изъято {amount:,} ₽. Теперь у него {new_money:,} ₽.".replace(",", " "), parse_mode="HTML")

@dp.message(Command("donate"))
async def cmd_donate_logs(message: Message):
    if not is_admin(message.from_user.id): return
    cur.execute("SELECT nickname, stars, rubles, date FROM donations ORDER BY id DESC LIMIT 30")
    rows = cur.fetchall()
    if not rows: return await message.answer("Пока нет ни одного доната.")
    text = "💰 <b>Последние 30 донатов:</b>\n\n"
    for nick, stars, rubles, date in rows:
        dt = datetime.fromisoformat(date).strftime("%d.%m %H:%M")
        text += f"👤 <b>{nick}</b> | {stars} ⭐ | +{rubles:,} ₽ | {dt}\n".replace(",", " ")
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id): return
    text = "👑 <b>Админ-команды:</b>\n\n/all_user\n/o [Текст для всех игроков]\n/donate\n/add_money [Ник] [Сумма]\n/un_money [Ник] [Сумма]\n/add_xp [Ник] [XP]\n/bustxp [Ник] [Минуты]\n/bustlace [Ник] [Минуты]\n/ban [Ник] [Минуты] [Причина]\n/unban [Ник]\n/rename_nick [Ник]\n/vaip"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("o"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id): return
    parts=(message.text or "").split(maxsplit=1)
    text=parts[1].strip() if len(parts)>1 else ""
    if text.startswith('"') and text.endswith('"') and len(text)>=2:
        text=text[1:-1].strip()
    if not text:
        return await message.answer('Использование: <code>/o текст сообщения</code>',parse_mode="HTML")
    if len(text)>4096:
        return await message.answer("Текст слишком длинный. Максимум — 4096 символов.")
    cur.execute("SELECT user_id FROM users WHERE registered=1")
    recipients=[row[0] for row in cur.fetchall()]
    sent=failed=0
    for uid in recipients:
        try:
            await bot.send_message(uid,text)
            sent+=1
        except Exception:
            failed+=1
        await asyncio.sleep(0.05)
    await message.answer(f"📣 Рассылка завершена. Доставлено: {sent}; не доставлено: {failed}.")

@dp.message(Command("all_user"))
async def cmd_all_user(message: Message):
    if not is_admin(message.from_user.id): return
    cur.execute("SELECT nickname, tg_username, real_name FROM users WHERE registered=1"); users = cur.fetchall()
    if not users: return await message.answer("В игре пока нет зарегистрированных игроков.")
    text = "👥 <b>Список всех игроков:</b>\n\n"
    for i, (nick, tg_user, real_name) in enumerate(users, 1):
        tg_text = f"@{tg_user}" if tg_user else "❌ нет @username"
        text += f"{i}. <b>{nick}</b> ({real_name}) | {tg_text}\n"
    if len(text) > 4000: text = text[:4000] + "\n\n... (обрезано)"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("ban"))
async def cmd_ban(message: Message):
    if not is_admin(message.from_user.id): return
    args = message.text.split(maxsplit=3)
    if len(args) < 4: return await message.answer("⚠️ Использование: /ban [Ник] [Минуты] [Причина]")
    target_nick = args[1]
    try: minutes = int(args[2])
    except ValueError: return await message.answer("⚠️ Время должно быть числом.")
    reason = args[3]
    u = get_user_by_nick(target_nick)
    if not u: return await message.answer(f"⚠️ Игрок не найден.")
    save(u["user_id"], ban_time=(datetime.now() + timedelta(minutes=minutes)).isoformat(), ban_reason=reason)
    await message.answer(f"✅ Игрок <b>{target_nick}</b> забанен на {minutes} мин.\nПричина: {reason}", parse_mode="HTML")

@dp.message(Command("unban"))
async def cmd_unban(message: Message):
    if not is_admin(message.from_user.id): return
    args = message.text.split()
    if len(args) < 2: return await message.answer("⚠️ Использование: /unban [Ник]")
    u = get_user_by_nick(args[1])
    if not u: return await message.answer("⚠️ Игрок не найден.")
    save(u["user_id"], ban_time='', ban_reason='')
    await message.answer(f"✅ Игрок <b>{args[1]}</b> разбанен.", parse_mode="HTML")

@dp.message(Command("rename_nick"))
async def cmd_rename_nick(message: Message):
    if not is_admin(message.from_user.id): return
    args = message.text.split()
    if len(args) < 2: return await message.answer("⚠️ Использование: /rename_nick [Ник]")
    u = get_user_by_nick(args[1])
    if not u: return await message.answer("⚠️ Игрок не найден.")
    save(u["user_id"], registered=0, nickname='')
    await message.answer(f"✅ Никнейм игрока <b>{args[1]}</b> сброшен.", parse_mode="HTML")

@dp.message(Command("add_money"))
async def cmd_add_money(message: Message):
    if not is_admin(message.from_user.id): return
    args = message.text.split()
    if len(args) < 3: return await message.answer("⚠️ Использование: /add_money [Ник] [Сумма]")
    try: amount = int(args[2])
    except ValueError: return await message.answer("⚠️ Сумма должна быть числом.")
    u = get_user_by_nick(args[1])
    if not u: return await message.answer("⚠️ Игрок не найден.")
    save(u["user_id"], money=u["money"] + amount)
    await message.answer(f"✅ Игроку <b>{args[1]}</b> выдано {amount:,} ₽.".replace(",", " "), parse_mode="HTML")

@dp.message(Command("add_xp"))
async def cmd_add_xp(message: Message):
    if not is_admin(message.from_user.id): return
    args = message.text.split()
    if len(args) < 3: return await message.answer("⚠️ Использование: /add_xp [Ник] [XP]")
    try: amount = int(args[2])
    except ValueError: return await message.answer("⚠️ XP должно быть числом.")
    u = get_user_by_nick(args[1])
    if not u: return await message.answer("⚠️ Игрок не найден.")
    new_level, new_xp = add_experience(u["level"], u["xp"], amount)
    save(u["user_id"], xp=new_xp, level=new_level)
    await message.answer(f"✅ Игроку <b>{args[1]}</b> выдано {amount} XP.", parse_mode="HTML")

async def grant_admin_boost(message: Message, boost_column: str, label: str):
    if not is_admin(message.from_user.id): return
    args=(message.text or "").split()
    if len(args)!=3:return await message.answer(f"Использование: /{label} [Ник] [Минуты]")
    try:minutes=int(args[2])
    except ValueError:return await message.answer("Минуты должны быть целым числом.")
    if minutes<=0:return await message.answer("Длительность должна быть больше нуля.")
    u=get_user_by_nick(args[1])
    if not u:return await message.answer("Игрок с таким ником не найден.")
    expires=boost_expiry(u,boost_column,minutes)
    save(u["user_id"],**{boost_column:expires})
    multiplier="×2 XP" if boost_column=="xp_boost_until" else "×1,5 к зарплате"
    await message.answer(f"✅ Игроку <b>{html.escape(args[1])}</b> выдан буст {multiplier} на {minutes} мин.",parse_mode="HTML")
    try:await bot.send_message(u["user_id"],f"🎁 Администратор выдал тебе буст {multiplier} на {minutes} минут.")
    except Exception:pass

@dp.message(Command("bustxp"))
async def cmd_bust_xp(message: Message):
    await grant_admin_boost(message,"xp_boost_until","bustxp")

@dp.message(Command("bustlace"))
async def cmd_bust_money(message: Message):
    await grant_admin_boost(message,"money_boost_until","bustlace")

@dp.message(Command("vaip"))
async def cmd_wipe(message: Message):
    if not is_admin(message.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚠️ СБРОСИТЬ ИГРУ (VIP ОСТАНЕТСЯ)", callback_data="confirm_wipe")],[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wipe")]])
    await message.answer("🚨 <b>Сбросить игровой прогресс всех игроков?</b>\nАктивные Titan VIP, Premium VIP и Full VIP сохранятся вместе со сроком действия. Остальной игровой прогресс будет удалён.", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "confirm_wipe")
async def execute_wipe(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    cur.execute("""
        UPDATE users SET nickname='', real_name='', gender='', registered=0, tg_username='', ban_time='', ban_reason='',
        money=1000, level=1, xp=0, health=100, hunger=0, jail_time='', hospital_time='', business='none', last_business_collect='', car='none', car_protection=0, car_insurance=0, car_recovery_key='', car_recovery_at='', house='none', house_insurance=0, last_house_collect='',
        dealers=0, last_dealer_collect='', energy_drinks=0, armor=0, briefcase=0, license_mvd=0, license_mchs=0, license_ems=0, license_trucker=0, license_mreo=0, license_auto=0, license_weapon=0, clan_id=0,
        btc=0, eth=0, gold=0, shop_name='', shop_manager=0, last_shop_auto='', shop_food_stock=0, shop_food_price=1500, shop_medkit_stock=0, shop_medkit_price=4000, shop_energy_stock=0, shop_energy_price=2500, shop_armor_stock=0, shop_armor_price=10000, shop_briefcase_stock=0, shop_briefcase_price=5000, shop_alarm_stock=0, shop_alarm_price=25000,
        axe=0, lockpicks=0,
        weapon_shop_name='', weapon_shop_last_income='', weapon_shop_ak47_stock=0, weapon_shop_deagle_stock=0, weapon_shop_m4a1_stock=0,
        weapon_shop_ak47_price=0, weapon_shop_deagle_price=0, weapon_shop_m4a1_price=0, house_alarm=0,
        pass_blackmarket=0, c4=0, gun=0, last_rob='', bank_weapon_pending='', bank_heist_active=0, bank_weapon_uses_deagle=0, bank_weapon_uses_ak47=0, bank_weapon_uses_m4a1=0, last_home_rob='', last_car_theft='', last_bot_home_rob='', last_bot_car_theft='',
        last_work='', last_daily_bonus='', last_trucker_game='', incoming_transfers_blocked=0, transfer_control_unlocked=0,
        xp_boost_until='', money_boost_until=''
    """)
    cur.execute("DELETE FROM clans"); cur.execute("DELETE FROM donations"); cur.execute("DELETE FROM inventory_items"); cur.execute("DELETE FROM market_listings"); conn.commit()
    await cb.message.edit_text("💥 <b>СБРОС ИГРОВОГО ПРОГРЕССА ВЫПОЛНЕН!</b>\nАктивные VIP и сроки их действия сохранены.", parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data == "cancel_wipe")
async def cancel_wipe(cb: CallbackQuery): await cb.message.edit_text("❌ Вайп отменен."); await cb.answer()

# ==================== ДОНАТ / РЕГИСТРАЦИЯ ====================
@dp.message(F.text == "⭐ Донат")
async def donate_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Деньги", callback_data="donate_money_menu")],
        [InlineKeyboardButton(text="✨ XP", callback_data="donate_xp_menu")],
        [InlineKeyboardButton(text="🎁 Разное", callback_data="donate_misc_menu")],
        [InlineKeyboardButton(text="👑 VIP статус", callback_data="donate_vip_menu")],
    ])
    await message.answer("⭐ <b>Донат-магазин</b>\nВыбери категорию:", reply_markup=kb, parse_mode="HTML")

def donation_category_keyboard(category: str):
    rows = []
    if category == "money":
        rows = [[InlineKeyboardButton(text=f"💎 {n} ⭐ → {n*1000:,} ₽".replace(",", " "), callback_data=f"donate_money_{n}")] for n in (1, 10, 50, 100)]
        rows.append([InlineKeyboardButton(text="💰 Своя сумма", callback_data="donate_custom")])
    elif category == "xp":
        rows = [[InlineKeyboardButton(text=f"✨ {n} ⭐ → {n*50:,} XP".replace(",", " "), callback_data=f"donate_xp_{n}")] for n in (10, 50, 100, 250)]
        rows.append([InlineKeyboardButton(text="✨ Своя сумма", callback_data="donate_xp_custom")])
    elif category == "misc":
        rows = [
            [InlineKeyboardButton(text="✏️ Смена NickName — 15 ⭐", callback_data="donate_misc_rename")],
            [InlineKeyboardButton(text="🛡 Защита авто на 7 угонов — 20 ⭐", callback_data="donate_misc_car7")],
            [InlineKeyboardButton(text="✨ Буст XP x2 на 15 минут — 30 ⭐", callback_data="donate_misc_xpboost")],
            [InlineKeyboardButton(text="💵 Буст денег x1.5 на 5 минут — 125 ⭐", callback_data="donate_misc_moneyboost")],
            [InlineKeyboardButton(text="🚫 Отключение платежей и управление — 10 ⭐", callback_data="donate_misc_transfer_control")],
        ]
    else:
        rows = [[InlineKeyboardButton(text=f"👑 {VIP_TIERS[tier]['name']} — {VIP_TIERS[tier]['stars']} ⭐",callback_data=f"vip_select_{tier}")] for tier in ("titan","premium","full")]
    rows.append([InlineKeyboardButton(text="🔙 Категории", callback_data="donate_root")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@dp.callback_query(F.data.in_({"donate_root", "donate_money_menu", "donate_xp_menu", "donate_misc_menu", "donate_vip_menu"}))
async def donation_categories(cb: CallbackQuery):
    if cb.data == "donate_root":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💰 Деньги", callback_data="donate_money_menu")], [InlineKeyboardButton(text="✨ XP", callback_data="donate_xp_menu")], [InlineKeyboardButton(text="🎁 Разное", callback_data="donate_misc_menu")], [InlineKeyboardButton(text="👑 VIP статус", callback_data="donate_vip_menu")]])
        await cb.message.edit_text("⭐ <b>Донат-магазин</b>\nВыбери категорию:", reply_markup=kb, parse_mode="HTML")
    else:
        category = cb.data.replace("donate_", "").replace("_menu", "")
        category=category.replace("vip_menu","vip")
        captions = {"money": "💰 Деньги · 1 ⭐ = 1 000 ₽", "xp": "✨ Опыт · 1 ⭐ = 50 XP", "misc": "🎁 Разное", "vip":"👑 <b>VIP статус на 60 дней</b>"}
        await cb.message.edit_text(captions[category], reply_markup=donation_category_keyboard(category))
    await cb.answer()

@dp.callback_query(F.data.startswith("vip_select_"))
async def vip_select(cb: CallbackQuery):
    tier_key=cb.data.removeprefix("vip_select_");tier=VIP_TIERS.get(tier_key)
    if not tier:return await cb.answer("VIP не найден.",show_alert=True)
    text=(f"Вы уверены, что хотите купить <b>{tier['name']}</b> на 60 дней?\n\n"
          f"Бонусы:\n💰 Зарплата ×{tier['salary']}\n✨ Опыт за работу ×{tier['xp']}\n"
          f"⏱ Каждый час: +{tier['hourly_money']:,} ₽ и +{tier['hourly_xp']} XP".replace(","," "))
    if tier["weapon_discount"]:text+="\n🔫 Скидка ×1,5 в обычном оружейном магазине (магазины игроков не учитываются)."
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Да, подтверждаю покупку",callback_data=f"vip_confirm_{tier_key}")],[InlineKeyboardButton(text="❌ Отказаться",callback_data="vip_cancel")]])
    await cb.message.edit_text(text,reply_markup=kb,parse_mode="HTML");await cb.answer()

@dp.callback_query(F.data.startswith("vip_confirm_"))
async def vip_confirm(cb: CallbackQuery):
    tier_key=cb.data.removeprefix("vip_confirm_");tier=VIP_TIERS.get(tier_key)
    if not tier:return await cb.answer("VIP не найден.",show_alert=True)
    await bot.send_invoice(chat_id=cb.message.chat.id,title=f"{tier['name']} на 60 дней",description=f"VIP-бонусы на 60 дней: зарплата ×{tier['salary']}, опыт ×{tier['xp']}",payload=f"vip_{tier_key}",provider_token="",currency="XTR",prices=[LabeledPrice(label=tier["name"],amount=tier["stars"])])
    await cb.answer("Счёт на оплату отправлен.")

@dp.callback_query(F.data == "vip_cancel")
async def vip_cancel(cb: CallbackQuery):
    await cb.message.edit_text("Покупка VIP отменена.",reply_markup=donation_category_keyboard("vip"));await cb.answer()

@dp.callback_query(F.data.startswith("donate_") & ~F.data.startswith("donate_misc_"))
async def send_invoice(cb: CallbackQuery, state: FSMContext):
    if cb.data == "donate_custom":
        await state.set_state(DonateStates.custom_amount); await cb.message.answer("💰 Введи количество <b>Звёзд</b>:", parse_mode="HTML"); return await cb.answer()
    if cb.data == "donate_xp_custom":
        await state.set_state(DonateStates.custom_xp); await cb.message.answer("✨ Введи число звёзд (минимум 1):"); return await cb.answer()
    parts = cb.data.split("_")
    if len(parts) != 3 or parts[1] not in {"money", "xp"}: return await cb.answer("Неизвестный пакет", show_alert=True)
    kind, stars = parts[1], int(parts[2])
    reward = f"{stars*1000:,} ₽" if kind == "money" else f"{stars*50:,} XP"
    await bot.send_invoice(chat_id=cb.message.chat.id, title=f"Покупка за {stars} звёзд", description=f"Начисление: {reward}".replace(",", " "), payload=f"donate_{kind}_{stars}", provider_token="", currency="XTR", prices=[LabeledPrice(label="Донат", amount=stars)])
    await cb.answer()

@dp.message(DonateStates.custom_amount)
async def custom_amount_input(message: Message, state: FSMContext):
    try:
        stars = int(message.text)
        if stars < 1: return await message.answer("❌ Минимум 1 звезда!")
    except ValueError: return await message.answer("❌ Введи число:")
    await state.clear()
    await bot.send_invoice(chat_id=message.chat.id, title=f"Деньги за {stars} звёзд", description=f"Получение {stars * 1000:,} игровых рублей.".replace(",", " "), payload=f"donate_money_{stars}", provider_token="", currency="XTR", prices=[LabeledPrice(label="Донат", amount=stars)])

@dp.message(DonateStates.custom_xp)
async def custom_xp_input(message: Message, state: FSMContext):
    try: stars = int(message.text)
    except (ValueError, TypeError): return await message.answer("❌ Введи целое число звёзд.")
    if stars < 1: return await message.answer("❌ Минимум 1 звезда!")
    await state.clear()
    await bot.send_invoice(chat_id=message.chat.id, title=f"Опыт за {stars} звёзд", description=f"Начисление {stars*50:,} XP".replace(",", " "), payload=f"donate_xp_{stars}", provider_token="", currency="XTR", prices=[LabeledPrice(label="Опыт", amount=stars)])

@dp.callback_query(F.data.startswith("donate_misc_"))
async def donate_misc_invoice(cb: CallbackQuery):
    items = {"donate_misc_rename": (15, "Смена NickName"), "donate_misc_car7": (20, "Защита авто на 7 угонов"), "donate_misc_xpboost": (30, "Буст XP x2 на 15 минут"), "donate_misc_moneyboost": (125, "Буст денег x1.5 на 5 минут"), "donate_misc_transfer_control": (10, "Отключение платежей и управление")}
    if cb.data not in items: return await cb.answer("Неизвестный товар", show_alert=True)
    if cb.data == "donate_misc_transfer_control" and get_user(cb.from_user.id).get("transfer_control_unlocked", 0):
        return await cb.answer("Управление уже разблокировано бесплатно в меню переводов.", show_alert=True)
    stars, title = items[cb.data]
    await bot.send_invoice(chat_id=cb.message.chat.id, title=title, description=title, payload=cb.data, provider_token="", currency="XTR", prices=[LabeledPrice(label=title, amount=stars)])
    await cb.answer()

@dp.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery): await query.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message, state: FSMContext):
    payload = message.successful_payment.invoice_payload
    parts = payload.split("_")
    kind = "vip" if payload.startswith("vip_") else ("money" if len(parts) == 2 else parts[1] if len(parts) >= 3 and parts[0] == "donate" else "misc")
    misc_prices={"donate_misc_rename": 15, "donate_misc_car7": 20, "donate_misc_xpboost": 30, "donate_misc_moneyboost": 125, "donate_misc_transfer_control": 10}
    vip_key=payload.removeprefix("vip_") if kind=="vip" else ""
    stars = int(parts[-1]) if parts[-1].isdigit() else (VIP_TIERS[vip_key]["stars"] if vip_key in VIP_TIERS else misc_prices.get(payload, 0))
    rubles = stars * 1000 if kind == "money" else 0
    charge_id = message.successful_payment.telegram_payment_charge_id
    
    u = get_user(message.from_user.id)
    if u: 
        if kind == "money": save(message.from_user.id, money=u["money"] + rubles)
        elif kind == "xp":
            lvl, xp = add_experience(u["level"], u["xp"], stars * 50)
            save(message.from_user.id, level=lvl, xp=xp)
        elif kind == "vip" and vip_key in VIP_TIERS:
            vip_accrue_hourly(message.from_user.id)
            current=get_user(message.from_user.id);now=datetime.now()
            try:current_expiry=datetime.fromisoformat(current.get("vip_expires", ""))
            except (TypeError,ValueError):current_expiry=now
            base=max(now,current_expiry) if vip_config(current) else now
            new_expiry=(base+timedelta(days=60)).isoformat()
            save(message.from_user.id,vip_type=vip_key,vip_expires=new_expiry,vip_last_hourly=now.isoformat())
        elif payload == "donate_misc_car7": save(message.from_user.id, car_protection=7)
        elif payload == "donate_misc_xpboost": save(message.from_user.id, xp_boost_until=boost_expiry(u, "xp_boost_until", 15))
        elif payload == "donate_misc_moneyboost": save(message.from_user.id, money_boost_until=boost_expiry(u, "money_boost_until", 5))
        elif payload == "donate_misc_transfer_control":
            save(message.from_user.id, transfer_control_unlocked=1, incoming_transfers_blocked=1)
            log_player_action(message.from_user, "КУПЛЕНО УПРАВЛЕНИЕ ВХОДЯЩИМИ ПЕРЕВОДАМИ за 10 ⭐; переводы отключены")
        
        cur.execute("INSERT INTO donations (user_id, nickname, stars, rubles, charge_id, date) VALUES (?, ?, ?, ?, ?, ?)",
                    (u["user_id"], u["nickname"], stars, rubles, charge_id, datetime.now().isoformat()))
        conn.commit()
        
        if payload == "donate_misc_rename":
            await message.answer("✅ Оплата прошла! Введи новый игровой NickName (без пробелов):")
            await state.set_state(NicknameChangeStates.new_nickname)
        elif kind == "money": await message.answer(f"✅ Оплата прошла! Начислено {rubles:,} ₽".replace(",", " "))
        elif kind == "xp": await message.answer(f"✅ Оплата прошла! Начислено {stars*50:,} XP".replace(",", " "))
        elif kind == "vip" and vip_key in VIP_TIERS: await message.answer(f"👑 <b>{VIP_TIERS[vip_key]['name']} активирован на 60 дней!</b>\nЗарплата ×{VIP_TIERS[vip_key]['salary']}, опыт ×{VIP_TIERS[vip_key]['xp']}. Ежечасные начисления начнутся через час.",parse_mode="HTML")
        elif payload == "donate_misc_transfer_control": await message.answer("✅ За 10 ⭐ отключены входящие переводы. Менять настройку дальше можно бесплатно в меню переводов.")
        else: await message.answer("✅ Оплата прошла! Товар активирован.")
        
        try:
            await bot.send_message(
                chat_id=ADMINS[0],
                text=f"💰 <b>НОВЫЙ ДОНАТ!</b>\n\n"
                     f"👤 Игрок: <b>{u['nickname']}</b> (@{u.get('tg_username', 'нет_юзернейма')})\n"
                     f"⭐ Куплено звёзд: <b>{stars}</b>\n"
                     f"🎁 Товар: <b>{payload}</b>\n💵 Выдано рублей: <b>{rubles:,} ₽</b>\n"
                     f"🆔 ID: <code>{charge_id}</code>".replace(",", " "),
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Ошибка отправки уведомления: {e}")

@dp.message(NicknameChangeStates.new_nickname)
async def paid_nickname_change(message: Message, state: FSMContext):
    nick = (message.text or "").strip()
    if not nick or len(nick) > 24 or any(ch.isspace() for ch in nick):
        return await message.answer("Ник должен быть длиной 1–24 символа и без пробелов. Попробуй ещё раз:")
    existing = get_user_by_nick(nick)
    if existing and existing["user_id"] != message.from_user.id:
        return await message.answer("Этот ник уже занят. Введи другой:")
    u = get_user(message.from_user.id)
    old_nick = u.get("nickname", "")
    save(message.from_user.id, nickname=nick)
    cur.execute("UPDATE donations SET nickname=? WHERE user_id=?", (nick, message.from_user.id)); conn.commit()
    if old_nick and old_nick != nick:
        for log_path in LOG_DIR.glob("*.txt"):
            try:
                content = log_path.read_text(encoding="utf-8")
                log_path.write_text(content.replace(f"Игровой ник: {old_nick}", f"Игровой ник: {nick}"), encoding="utf-8")
            except OSError: pass
    await state.clear()
    log_player_action(message.from_user, f"ДОНАТ: ник изменён с {old_nick} на {nick}")
    await message.answer(f"✅ Игровой ник изменён на <b>{nick}</b>. Прогресс сохранён.", parse_mode="HTML")

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    uid = message.from_user.id; create_user(uid, message.from_user.full_name)
    tg_user = getattr(message.from_user, 'username', None)
    if tg_user: save(uid, tg_username=tg_user)
    u = get_user(uid)
    if not u["registered"]:
        await state.set_state(RegStates.nickname)
        await message.answer("👋 Привет! Придумай свой <b>Никнейм</b> (без пробелов):", parse_mode="HTML")
    else: await message.answer(f"С возвращением, {u['nickname']}!", reply_markup=main_menu())

@dp.message(RegStates.nickname)
async def reg_nick(message: Message, state: FSMContext):
    nick = message.text.strip()
    if len(nick) < 3 or " " in nick: return await message.answer("❌ Ник от 3 символов и без пробелов:")
    nick_lower = nick.lower()
    if any(word in nick_lower for word in BAD_WORDS): return await message.answer("❌ Этот никнейм содержит запрещенные слова. Придумай другой:")
    if get_user_by_nick(nick): return await message.answer("❌ Ник занят! Придумай другой:")
    await state.update_data(nickname=nick); await state.set_state(RegStates.real_name)
    await message.answer("📝 Напиши <b>Имя_Фамилию</b> (например: Иван_Иванов):", parse_mode="HTML")

@dp.message(RegStates.real_name)
async def reg_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3: return await message.answer("❌ Слишком короткое имя:")
    await state.update_data(real_name=name); await state.set_state(RegStates.gender)
    await message.answer("🚻 Выбери свой пол:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👦 Мужской", callback_data="gen_male"), InlineKeyboardButton(text="👧 Женский", callback_data="gen_female")]]))

@dp.callback_query(RegStates.gender)
async def reg_gender(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    save(cb.from_user.id, nickname=data["nickname"], real_name=data["real_name"], gender="Мужской" if cb.data == "gen_male" else "Женский", registered=1)
    await state.clear(); await cb.message.delete()
    await cb.message.answer(f"✅ Регистрация завершена!", reply_markup=main_menu()); await cb.answer()

# ==================== ПРОФИЛЬ И РАБОТА ====================
def profile_actions(u):
    rows = []
    if u.get("house") in HOUSES_CATALOG:
        rows.append([InlineKeyboardButton(text="🏠 Продать дом за 50% цены", callback_data="sell_house")])
    if u.get("car") in CARS_CATALOG:
        rows.append([InlineKeyboardButton(text="🚘 Продать машину за 50% цены", callback_data="sell_car")])
    hospital_until = u.get("hospital_time")
    if hospital_until and datetime.fromisoformat(hospital_until) > datetime.now():
        rows.append([InlineKeyboardButton(text="🏥 Выйти досрочно (50 000 ₽)", callback_data="hospital_early_exit")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

def profile_text(u):
    h_bar = "🟩" * (u["hunger"] // 10) + "⬛" * (10 - u["hunger"] // 10)
    hp_bar = "🟩" * (u["health"] // 10) + "⬛" * (10 - u["health"] // 10)
    xp_needed = xp_required(u["level"])
    xp_filled = min(10, u["xp"] * 10 // xp_needed)
    xp_bar = "🟩" * xp_filled + "⬛" * (10 - xp_filled)
    clan_name = "Нет"
    if u.get("clan_id"):
        cur.execute("SELECT name FROM clans WHERE id=?", (u["clan_id"],)); c = cur.fetchone()
        if c: clan_name = c[0]
    house_key = u.get("house")
    if house_key in HOUSES_CATALOG:
        salary_mult, hunger_reduction = HOUSE_PERKS.get(house_key, (1.0, 0.0))
        house_perk = f"🏠 Дом: зарплата ×{salary_mult:.2f}, голод после работы −{hunger_reduction*100:.1f}%"
    else:
        house_perk = "🏠 Дом: нет"
    car = CARS_CATALOG.get(u.get("car"))
    car_perk = f"🚘 Машина: {car[0]} — кулдаун работы {work_cooldown(u)} сек." if car else f"🚘 Машина: нет — кулдаун работы {work_cooldown(u)} сек."
    protection = u.get("car_protection", 0)
    car_security = (f"🛡 Защита от угона: {protection} блокировок" if protection > 0 else "🛡 Защита авто: не установлена или сломана") if car else (f"🛡 Защита на следующую машину: {protection} блокировок" if protection > 0 else "🛡 Защита от угона: нет машины")
    boosts = []
    tier=vip_config(u)
    if tier:
        try:vip_expiry=datetime.fromisoformat(u["vip_expires"]).strftime("%d.%m.%Y %H:%M")
        except (TypeError,ValueError):vip_expiry="—"
        boosts.append(f"👑 {tier['name']} до {vip_expiry}: зарплата ×{tier['salary']}, опыт ×{tier['xp']}")
    if boost_active(u, "xp_boost_until"): boosts.append(f"✨ XP ×2 до {datetime.fromisoformat(u['xp_boost_until']):%H:%M:%S}")
    if boost_active(u, "money_boost_until"): boosts.append(f"💵 Зарплата ×1.5 до {datetime.fromisoformat(u['money_boost_until']):%H:%M:%S}")
    boost_text = "\n".join(boosts) if boosts else "Бусты: нет"
    return f"👤 <b>{html.escape(str(u['nickname']))}</b> ({html.escape(str(u['real_name']))})\n⭐ Ур: {u['level']} (XP: {u['xp']}/{xp_needed} {xp_bar})\n💰 {u['money']:,} ₽\n🍔 Голод: {h_bar} ({u['hunger']}/100)\n❤️ Здоровье: {hp_bar} ({u['health']}/100)\n🛡 Клан: {clan_name}\n{house_perk}\n{car_perk}\n{car_security}\n{boost_text}".replace(",", " ")

def insurance_price_house(u: dict) -> int:
    return max(10_000, int(HOUSES_CATALOG[u["house"]][1] * 0.05))

def insurance_price_car(u: dict) -> int:
    return max(10_000, int(CARS_CATALOG[u["car"]][1] * 0.05))

def insurance_keyboard(u: dict):
    rows=[]
    if u.get("house") in HOUSES_CATALOG and not u.get("house_insurance",0):
        rows.append([InlineKeyboardButton(text=f"🏠 Застраховать дом · {insurance_price_house(u):,} ₽".replace(","," "),callback_data="insurance_buy_house")])
    if u.get("car") in CARS_CATALOG and not car_recovery_pending(u):
        if not u.get("car_insurance",0):
            rows.append([InlineKeyboardButton(text=f"🚘 Застраховать авто · {insurance_price_car(u):,} ₽".replace(","," "),callback_data="insurance_buy_car")])
        if not u.get("car_protection",0):
            rows.append([InlineKeyboardButton(text="🛡 Противоугонная защита · 500 000 ₽",callback_data="buy_car_protection")])
    rows.append([InlineKeyboardButton(text="🔙 Назад",callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def insurance_text(u: dict) -> str:
    house=u.get("house")
    if house in HOUSES_CATALOG:
        h_name=HOUSES_CATALOG[house][0]
        h_status="✅ Страховой случай доступен (1 раз)" if u.get("house_insurance",0) else f"Не застрахован · полис {insurance_price_house(u):,} ₽".replace(","," ")
        house_line=f"🏠 <b>Дом: {h_name}</b>\n{h_status}\nПолис возместит 75% добычи грабителя (не больше 25% цены дома) после ограбления игроком."
    else:
        house_line="🏠 <b>Дом:</b> сначала нужно купить дом."
    car_key=u.get("car")
    if car_recovery_pending(u):
        try: return_at=datetime.fromisoformat(u["car_recovery_at"]).strftime("%H:%M")
        except (TypeError,ValueError): return_at="позже"
        car_line=f"🚘 <b>Авто на восстановлении</b>\nСтраховка вернёт машину в гараж примерно в {return_at}."
    elif car_key in CARS_CATALOG:
        name=CARS_CATALOG[car_key][0]
        c_status="✅ Страховой случай доступен (1 раз)" if u.get("car_insurance",0) else f"Не застраховано · полис {insurance_price_car(u):,} ₽".replace(","," ")
        protection=f"\nЗащита от угона: {u.get('car_protection',0)} блокировок." if u.get("car_protection",0)>0 else ""
        car_line=f"🚘 <b>Авто: {name}</b>\n{c_status}\nПосле успешного угона страховка вернёт авто через 6 часов. Кулдаун работы с машиной: {work_cooldown(u)} сек. (бонуса к зарплате нет).{protection}"
    else:
        car_line="🚘 <b>Авто:</b> сначала нужно купить машину."
    return "🛡 <b>Страховка</b>\nПолис оплачивается один раз и действует до одного страхового случая.\n\n"+house_line+"\n\n"+car_line

async def show_insurance(message, u: dict, edit: bool=False):
    text=insurance_text(u); markup=insurance_keyboard(u)
    if edit:
        return await message.edit_text(text,reply_markup=markup,parse_mode="HTML")
    return await message.answer(text,reply_markup=markup,parse_mode="HTML")

@dp.message(F.text == "🛡 Страховка")
async def insurance_menu(message: Message):
    await show_insurance(message,get_user(message.from_user.id))

@dp.callback_query(F.data == "insurance_home")
async def insurance_home(cb: CallbackQuery):
    await show_insurance(cb.message,get_user(cb.from_user.id),edit=True)
    await cb.answer()

@dp.callback_query(F.data == "insurance_buy_house")
async def insurance_buy_house(cb: CallbackQuery):
    u=get_user(cb.from_user.id)
    if u.get("house") not in HOUSES_CATALOG:return await cb.answer("Сначала купи дом.",show_alert=True)
    if u.get("house_insurance",0):return await cb.answer("На доме уже есть активная страховка.",show_alert=True)
    price=insurance_price_house(u)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Подтвердить",callback_data="insurance_confirm_house")],[InlineKeyboardButton(text="❌ Отмена",callback_data="insurance_home")]])
    await cb.message.edit_text(f"Застраховать дом за {price:,} ₽? Полис возместит 75% добычи (до 25% цены дома) при следующем ограблении игроком.".replace(","," "),reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "insurance_confirm_house")
async def insurance_confirm_house(cb: CallbackQuery):
    u=get_user(cb.from_user.id)
    if u.get("house") not in HOUSES_CATALOG:return await cb.answer("Сначала купи дом.",show_alert=True)
    if u.get("house_insurance",0):return await cb.answer("Страховка уже активна.",show_alert=True)
    price=insurance_price_house(u)
    if u["money"]<price:return await cb.answer(f"Не хватает {price:,} ₽.".replace(","," "),show_alert=True)
    save(cb.from_user.id,money=u["money"]-price,house_insurance=1)
    log_player_action(cb.from_user,f"ЗАСТРАХОВАН ДОМ {HOUSES_CATALOG[u['house']][0]} за {price} ₽ (1 случай)")
    await show_insurance(cb.message,get_user(cb.from_user.id),edit=True)
    await cb.answer("Дом застрахован.",show_alert=True)

@dp.callback_query(F.data == "insurance_buy_car")
async def insurance_buy_car(cb: CallbackQuery):
    u=get_user(cb.from_user.id)
    if u.get("car") not in CARS_CATALOG:return await cb.answer("Сначала купи машину.",show_alert=True)
    if car_recovery_pending(u):return await cb.answer("Дождись возврата машины из страхового восстановления.",show_alert=True)
    if u.get("car_insurance",0):return await cb.answer("На машине уже есть активная страховка.",show_alert=True)
    price=insurance_price_car(u)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Подтвердить",callback_data="insurance_confirm_car")],[InlineKeyboardButton(text="❌ Отмена",callback_data="insurance_home")]])
    await cb.message.edit_text(f"Застраховать машину за {price:,} ₽? При успешном угоне она вернётся в гараж через 6 часов. Полис действует до одного страхового случая.".replace(","," "),reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "insurance_confirm_car")
async def insurance_confirm_car(cb: CallbackQuery):
    u=get_user(cb.from_user.id)
    if u.get("car") not in CARS_CATALOG:return await cb.answer("Сначала купи машину.",show_alert=True)
    if car_recovery_pending(u):return await cb.answer("Дождись возврата машины.",show_alert=True)
    if u.get("car_insurance",0):return await cb.answer("Страховка уже активна.",show_alert=True)
    price=insurance_price_car(u)
    if u["money"]<price:return await cb.answer(f"Не хватает {price:,} ₽.".replace(","," "),show_alert=True)
    save(cb.from_user.id,money=u["money"]-price,car_insurance=1)
    log_player_action(cb.from_user,f"ЗАСТРАХОВАН АВТО {CARS_CATALOG[u['car']][0]} за {price} ₽ (возврат через 6 часов)")
    await show_insurance(cb.message,get_user(cb.from_user.id),edit=True)
    await cb.answer("Машина застрахована.",show_alert=True)

@dp.message(F.text == "👤 Профиль")
async def profile(message: Message):
    u = get_user(message.from_user.id)
    await message.answer(profile_text(u), reply_markup=profile_actions(u), parse_mode="HTML")

@dp.callback_query(F.data == "hospital_early_exit")
async def hospital_early_exit(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    hospital_until = u.get("hospital_time") if u else None
    if not hospital_until or datetime.fromisoformat(hospital_until) <= datetime.now():
        return await cb.answer("Ты уже выписан.", show_alert=True)
    if u["money"] < 50_000:
        return await cb.answer("Для досрочной выписки нужно 50 000 ₽.", show_alert=True)
    save(cb.from_user.id, money=u["money"] - 50_000, hospital_time="")
    log_player_action(cb.from_user, "ДОСРОЧНАЯ ВЫПИСКА ИЗ БОЛЬНИЦЫ за 50 000 ₽")
    await cb.message.edit_text("✅ Ты оплатил досрочную выписку и покинул больницу.")
    await cb.answer("Выписан!")

@dp.message(F.text == "🛒 Магазин")
async def shop(message: Message): await message.answer("🛒 <b>Магазин:</b>", reply_markup=shop_menu(get_user(message.from_user.id)), parse_mode="HTML")

# ==================== КАЗИНО ====================
@dp.message(F.text == "🎰 Казино")
async def casino_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎡 Рулетка: красное/чёрное", callback_data="casino_game_roulette")],
        [InlineKeyboardButton(text="🎲 Кубик: меньше/больше", callback_data="casino_game_dice")],
    ])
    u = get_user(message.from_user.id)
    await message.answer(
        f"🎰 <b>Казино</b>\nБаланс: {u['money']:,} ₽\n\nВыбери игру, затем введи свою ставку. При выигрыше выплата — 2× ставки.".replace(",", " "),
        reply_markup=kb, parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("casino_game_"))
async def casino_choose_game(cb: CallbackQuery, state: FSMContext):
    game = cb.data.removeprefix("casino_game_")
    if game not in {"roulette", "dice"}:
        return await cb.answer("Неизвестная игра.", show_alert=True)
    u = get_user(cb.from_user.id)
    await state.update_data(casino_game=game)
    await state.set_state(CasinoStates.choose_bet)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="casino_cancel")]])
    await cb.message.answer(f"💰 Введи ставку целым числом. Твой баланс: {u['money']:,} ₽".replace(",", " "), reply_markup=cancel_kb)
    await cb.answer()

@dp.callback_query(F.data == "casino_cancel")
async def casino_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer("Игра отменена.", show_alert=True)

@dp.message(CasinoStates.choose_bet)
async def casino_take_bet(message: Message, state: FSMContext):
    try:
        bet = int(message.text.strip())
    except (ValueError, AttributeError):
        return await message.answer("Введи ставку целым числом, например 1000.")
    u = get_user(message.from_user.id)
    if bet <= 0:
        return await message.answer("Ставка должна быть больше нуля.")
    if not u or bet > u["money"]:
        return await message.answer("Ставка больше твоего баланса. Введи сумму поменьше.")

    data = await state.get_data()
    game = data.get("casino_game")
    if game == "roulette":
        buttons = [[InlineKeyboardButton(text="🔴 Красное", callback_data="casino_side_red"), InlineKeyboardButton(text="⚫ Чёрное", callback_data="casino_side_black")]]
        prompt = f"🎡 Ставка: {bet:,} ₽. Выбери цвет рулетки:".replace(",", " ")
    elif game == "dice":
        buttons = [[InlineKeyboardButton(text="⬇️ Меньше (1–3)", callback_data="casino_side_low"), InlineKeyboardButton(text="⬆️ Больше (4–6)", callback_data="casino_side_high")]]
        prompt = f"🎲 Ставка: {bet:,} ₽. Выбери диапазон кубика:".replace(",", " ")
    else:
        await state.clear()
        return await message.answer("Игра сбросилась. Открой казино и начни заново.")

    await state.update_data(casino_bet=bet)
    await state.set_state(CasinoStates.choose_side)
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="casino_cancel")])
    await message.answer(prompt, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(CasinoStates.choose_side, F.data.startswith("casino_side_"))
async def casino_play(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    game, bet = data.get("casino_game"), data.get("casino_bet")
    u = get_user(cb.from_user.id)
    if game not in {"roulette", "dice"} or not isinstance(bet, int):
        await state.clear()
        return await cb.answer("Ставка сбросилась. Начни заново.", show_alert=True)
    if not u or bet > u["money"]:
        await state.clear()
        return await cb.answer("На балансе уже не хватает денег на эту ставку.", show_alert=True)

    choice = cb.data.removeprefix("casino_side_")
    if game == "roulette":
        if choice not in {"red", "black"}:
            return await cb.answer("Неверный выбор.", show_alert=True)
        number = random.randint(0, 36)
        red_numbers = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        outcome = "green" if number == 0 else ("red" if number in red_numbers else "black")
        won = choice == outcome
        outcome_text = f"Выпало {number} — {'🟢 зелёное' if outcome == 'green' else ('🔴 красное' if outcome == 'red' else '⚫ чёрное')}"
        choice_text = "красное" if choice == "red" else "чёрное"
    else:
        if choice not in {"low", "high"}:
            return await cb.answer("Неверный выбор.", show_alert=True)
        number = random.randint(1, 6)
        outcome = "low" if number <= 3 else "high"
        won = choice == outcome
        outcome_text = f"Выпало {number} ({'меньше' if outcome == 'low' else 'больше'})"
        choice_text = "меньше (1–3)" if choice == "low" else "больше (4–6)"

    # Списываем ставку и сразу начисляем выигрыш, если он выпал.
    new_balance = u["money"] - bet + (bet * 2 if won else 0)
    await state.clear()
    save(cb.from_user.id, money=new_balance)
    log_player_action(cb.from_user, f"КАЗИНО: {game}, ставка {bet} ₽, выбор {choice_text}, {outcome_text}, {'выигрыш' if won else 'проигрыш'}")
    result = f"🎰 {outcome_text}\nТвой выбор: {choice_text}.\n"
    result += f"✅ Выигрыш: +{bet:,} ₽" if won else f"❌ Проигрыш: −{bet:,} ₽"
    result += f"\n💰 Баланс: {new_balance:,} ₽"
    await cb.message.answer(result.replace(",", " "))
    await cb.answer("Выиграл!" if won else "Не повезло.")

@dp.message(F.text == "💼 Работа")
async def jobs(message: Message): await message.answer("Выбери профессию:", reply_markup=jobs_menu())

@dp.message(F.text == "🏢 Бизнес")
async def business(message: Message): await message.answer("🏢 <b>Бизнес:</b>", reply_markup=business_menu(get_user(message.from_user.id)), parse_mode="HTML")

@dp.message(F.text == "🚗 Авто")
async def cars(message: Message): await message.answer("🚗 <b>Автосалон:</b>", reply_markup=cars_menu(get_user(message.from_user.id)), parse_mode="HTML")

@dp.message(F.text == "🏠 Дом")
async def houses(message: Message): await message.answer("🏠 <b>Недвижимость:</b>", reply_markup=houses_menu(get_user(message.from_user.id)), parse_mode="HTML")

@dp.message(F.text == "🎁 Бонус")
async def daily_bonus(message: Message):
    u = get_user(message.from_user.id)
    if u["last_daily_bonus"] and datetime.now() - datetime.fromisoformat(u["last_daily_bonus"]) < timedelta(days=1): return await message.answer("⏳ Бонус доступен раз в 24 часа.")
    bonus = random.randint(5000, 25000); save(message.from_user.id, money=u["money"] + bonus, last_daily_bonus=datetime.now().isoformat())
    await message.answer(f"🎁 Бонус: +{bonus:,} ₽!".replace(",", " "))

@dp.message(F.text == "🏆 ТОП")
async def top(message: Message):
    cur.execute("SELECT nickname, level, money FROM users WHERE registered=1 ORDER BY level DESC, money DESC LIMIT 10"); rows = cur.fetchall()
    await message.answer("🏆 <b>ТОП игроков:</b>\n\n" + "".join([f"{i}. {n} — Ур.{l} | {m:,} ₽\n".replace(",", " ") for i, (n, l, m) in enumerate(rows, 1)]), parse_mode="HTML")

# ==================== КЛАНЫ ====================
@dp.message(F.text == "🛡 Кланы")
async def clans_menu(message: Message):
    u = get_user(message.from_user.id); kb = []
    if u.get("clan_id"): kb.extend([[InlineKeyboardButton(text="💰 Внести в казну (50к)", callback_data="clan_donate")], [InlineKeyboardButton(text="📩 Пригласить по нику", callback_data="clan_invite")], [InlineKeyboardButton(text="🚪 Покинуть клан", callback_data="clan_leave")]])
    else: kb.append([InlineKeyboardButton(text="🛡 Создать клан (500к)", callback_data="clan_create")])
    kb.extend([[InlineKeyboardButton(text="📊 ТОП Кланов", callback_data="clan_top")], [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]])
    await message.answer("🛡 <b>Кланы:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@dp.callback_query(F.data == "clan_create")
async def clan_create_start(cb: CallbackQuery, state: FSMContext):
    u = get_user(cb.from_user.id)
    if u["money"] < 500_000: return await cb.answer("Нужно 500к для создания клана!", show_alert=True)
    await state.set_state(ClanStates.create_name); await cb.message.answer("🛡 Введи <b>название</b> для твоего клана:", parse_mode="HTML"); await cb.answer()

@dp.message(ClanStates.create_name)
async def clan_create_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3 or len(name) > 20: return await message.answer("❌ Название от 3 до 20 символов.")
    cur.execute("SELECT id FROM clans WHERE name=?", (name,))
    if cur.fetchone(): return await message.answer("❌ Клан с таким названием уже существует. Придумай другое:")
    u = get_user(message.from_user.id)
    if u["money"] < 500_000: await state.clear(); return await message.answer("❌ Недостаточно денег.")
    cur.execute("INSERT INTO clans (name, owner_id, bank) VALUES (?, ?, 0)", (name, message.from_user.id))
    save(message.from_user.id, money=u["money"] - 500_000, clan_id=cur.lastrowid); conn.commit()
    await state.clear(); await message.answer(f"🎉 Клан <b>{name}</b> создан!", parse_mode="HTML", reply_markup=main_menu())

@dp.callback_query(F.data == "clan_invite")
async def clan_invite_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ClanStates.invite_nick); await cb.message.answer("📩 Введи <b>никнейм</b> игрока:", parse_mode="HTML"); await cb.answer()

@dp.message(ClanStates.invite_nick)
async def clan_invite_send(message: Message, state: FSMContext):
    target_nick = message.text.strip(); t_user = get_user_by_nick(target_nick); u = get_user(message.from_user.id)
    if not t_user: await state.clear(); return await message.answer("❌ Игрок не найден.")
    if t_user["clan_id"] != 0: await state.clear(); return await message.answer("❌ Игрок уже в другом клане.")
    if t_user["user_id"] == u["user_id"]: await state.clear(); return await message.answer("❌ Нельзя пригласить себя.")
    cur.execute("SELECT name FROM clans WHERE id=?", (u["clan_id"],)); clan_name = cur.fetchone()[0]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Принять", callback_data=f"clan_acc_{u['clan_id']}"), InlineKeyboardButton(text="❌ Отказать", callback_data=f"clan_dec_{u['clan_id']}")]])
    try:
        await bot.send_message(t_user["user_id"], f"📩 Вам предложили вступить в клан <b>{clan_name}</b> от <b>{u['nickname']}</b>.", reply_markup=kb, parse_mode="HTML")
        await message.answer(f"✅ Приглашение отправлено <b>{t_user['nickname']}</b>!", parse_mode="HTML")
    except Exception: await message.answer("❌ Игрок заблокировал бота.")
    await state.clear()

@dp.callback_query(F.data.startswith("clan_acc_"))
async def clan_accept(cb: CallbackQuery):
    clan_id = int(cb.data.split("_")[2]); u = get_user(cb.from_user.id)
    if u["clan_id"] != 0: return await cb.answer("Ты уже состоишь в клане!", show_alert=True)
    save(cb.from_user.id, clan_id=clan_id); await cb.message.edit_text("✅ Ты успешно вступил в клан!", parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data.startswith("clan_dec_"))
async def clan_decline(cb: CallbackQuery): await cb.message.edit_text("❌ Ты отклонил приглашение."); await cb.answer()

@dp.callback_query(F.data == "clan_top")
async def clan_top(cb: CallbackQuery):
    cur.execute("SELECT name, bank FROM clans ORDER BY bank DESC LIMIT 5"); rows = cur.fetchall()
    if not rows: return await cb.answer("Кланов нет!", show_alert=True)
    await cb.message.answer("📊 <b>ТОП Кланов:</b>\n\n" + "".join([f"{i}. {n} — {b:,} ₽\n".replace(",", " ") for i, (n, b) in enumerate(rows, 1)]), parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data == "clan_donate")
async def clan_donate(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if u["money"] < 50_000: return await cb.answer("Нужно 50к!", show_alert=True)
    cur.execute("UPDATE clans SET bank = bank + 50000 WHERE id=?", (u["clan_id"],)); save(cb.from_user.id, money=u["money"] - 50_000); conn.commit()
    await cb.message.answer("💰 Внесено 50к в казну!"); await cb.answer()

@dp.callback_query(F.data == "clan_leave")
async def clan_leave(cb: CallbackQuery): save(cb.from_user.id, clan_id=0); await cb.message.answer("Ты покинул клан."); await cb.answer()

# ==================== ТЕСТИРОВАНИЕ / РАБОТА ====================
@dp.callback_query(F.data == "jobs")
async def cb_jobs(cb: CallbackQuery): await cb.message.edit_text("Выбери профессию:", reply_markup=jobs_menu()); await cb.answer()

@dp.callback_query(F.data.in_({"gather_mine", "gather_flax", "gather_cotton", "gather_wood"}))
async def gather_resources(cb: CallbackQuery):
    u=get_user(cb.from_user.id); action=cb.data
    required={"gather_mine":("job_mine",5),"gather_flax":("job_farmer",7),"gather_cotton":("job_farmer",7),"gather_wood":("job_sawmill",5)}[action]
    if u["level"]<required[1]: return await cb.answer(f"Для этой работы нужен {required[1]} уровень.",show_alert=True)
    ok,reason=check_status(cb.from_user.id)
    if not ok:return await cb.answer(reason,show_alert=True)
    cooldown=work_cooldown(u)
    if u.get("last_work") and datetime.now()-datetime.fromisoformat(u["last_work"])<timedelta(seconds=cooldown):
        return await cb.answer(f"Подожди {cooldown} сек. до следующего подхода.",show_alert=True)
    if action=="gather_mine":
        key=random.choices(["stone","metal","silver"],weights=[65,28,7],k=1)[0]; amount=5
    elif action=="gather_flax":key,amount="flax",5
    elif action=="gather_cotton":key,amount="cotton",5
    else:key,amount="wood",30
    inventory_add(cb.from_user.id,key,amount)
    xp=int(10*vip_xp_multiplier(u))
    if boost_active(u,"xp_boost_until"):xp*=2
    level,new_xp=add_experience(u["level"],u["xp"],xp)
    new_hunger=work_hunger_after(u,5);health_penalty=work_health_penalty(u,5,new_hunger)
    save(cb.from_user.id,last_work=datetime.now().isoformat(),level=level,xp=new_xp,hunger=new_hunger)
    if health_penalty:update_stats(cb.from_user.id,health_add=-health_penalty)
    log_player_action(cb.from_user,f"ДОБЫЧА: {RESOURCE_ITEMS[key]} +{amount}; опыт +{xp} XP")
    updated=get_user(cb.from_user.id)
    hospital=" Ты истощён и попал в больницу на 10 минут." if updated.get("hospital_time") and datetime.fromisoformat(updated["hospital_time"])>datetime.now() else ""
    fatigue=f" Потеряно {health_penalty} здоровья." if health_penalty else ""
    await cb.answer(f"Добыто: {RESOURCE_ITEMS[key]} ×{amount}.{fatigue}{hospital}",show_alert=True)

@dp.message(F.text == "🏛 Гос. структуры")
async def gov_structures(message: Message):
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚓 МВД",callback_data="job_mvd"),InlineKeyboardButton(text="🚒 МЧС",callback_data="job_mchs")],
        [InlineKeyboardButton(text="🏥 МЗ",callback_data="job_ems"),InlineKeyboardButton(text="🚘 МРЭО",callback_data="mreo_menu")],
    ])
    await message.answer("🏛 <b>Государственные структуры</b>\nРабота доступна с 10 уровня.",reply_markup=kb,parse_mode="HTML")

@dp.callback_query(F.data == "mreo_menu")
async def mreo_menu(cb: CallbackQuery):
    u=get_user(cb.from_user.id)
    if u["level"] < 10: return await cb.answer("Государственные структуры доступны с 10 уровня.",show_alert=True)
    rows=[]
    if u.get("license_mreo"):
        rows.append([InlineKeyboardButton(text="💼 Работать в МРЭО",callback_data="job_mreo")])
    else:
        rows.append([InlineKeyboardButton(text="📝 Устроиться в МРЭО",callback_data="starttest_mreo_apply")])
    rows.extend([
        [InlineKeyboardButton(text="📜 Купить лицензии",callback_data="mreo_licenses")],
        [InlineKeyboardButton(text="🪪 Сдать на права — категория B",callback_data="starttest_mreo_test_b")],
        [InlineKeyboardButton(text="🔙 Гос. структуры",callback_data="gov_structures_back")],
    ])
    kb=InlineKeyboardMarkup(inline_keyboard=rows)
    await cb.message.edit_text(f"🚘 <b>МРЭО</b>\nУровень для государственной службы: 10.\nРабота: {'устроен' if u.get('license_mreo') else 'не устроен'}\nАвто: {'есть' if u.get('license_auto') else 'нет'} · Оружие: {'есть' if u.get('license_weapon') else 'нет'}",reply_markup=kb,parse_mode="HTML");await cb.answer()

@dp.callback_query(F.data == "gov_structures_back")
async def gov_structures_back(cb: CallbackQuery):
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚓 МВД",callback_data="job_mvd"),InlineKeyboardButton(text="🚒 МЧС",callback_data="job_mchs")],[InlineKeyboardButton(text="🏥 МЗ",callback_data="job_ems"),InlineKeyboardButton(text="🚘 МРЭО",callback_data="mreo_menu")]])
    await cb.message.edit_text("🏛 Государственные структуры:",reply_markup=kb);await cb.answer()

@dp.callback_query(F.data == "mreo_licenses")
async def mreo_license_menu(cb: CallbackQuery):
    u=get_user(cb.from_user.id)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"🚗 Лицензия на авто — {'есть' if u.get('license_auto') else '100 000 ₽'}",callback_data="mreo_buy_auto")],[InlineKeyboardButton(text=f"🔫 Лицензия на оружие — {'есть' if u.get('license_weapon') else '250 000 ₽'}",callback_data="mreo_buy_weapon")],[InlineKeyboardButton(text="🔙 МРЭО",callback_data="mreo_menu")]])
    await cb.message.edit_text("📜 Выбери лицензию:",reply_markup=kb);await cb.answer()

@dp.callback_query(F.data.in_({"mreo_buy_auto","mreo_buy_weapon"}))
async def mreo_buy_license(cb: CallbackQuery):
    u=get_user(cb.from_user.id)
    if u["level"]<10:return await cb.answer("МРЭО доступно с 10 уровня.",show_alert=True)
    key="license_auto" if cb.data.endswith("auto") else "license_weapon"; price=100_000 if key=="license_auto" else 250_000
    if u.get(key):return await cb.answer("Эта лицензия уже есть.",show_alert=True)
    if u["money"]<price:return await cb.answer(f"Нужно {price:,} ₽.".replace(","," "),show_alert=True)
    save(cb.from_user.id,money=u["money"]-price,**{key:1});await cb.answer("Лицензия куплена.",show_alert=True)

@dp.callback_query(F.data.startswith("job_"))
async def cb_job(cb: CallbackQuery, state: FSMContext):
    job_key = cb.data; u = get_user(cb.from_user.id)
    if job_key not in JOBS and job_key not in NEW_JOBS: return await cb.answer("Работа не найдена.", show_alert=True)
    required_level = NEW_JOBS[job_key]["level"] if job_key in NEW_JOBS else JOBS[job_key][7]
    if u["level"] < required_level: return await cb.answer(f"Нужен {required_level} уровень!", show_alert=True)
    if job_key == "job_mreo" and not u.get("license_mreo", 0): return await mreo_menu(cb)
    if job_key in ["job_mvd", "job_mchs", "job_ems", "job_trucker"]:
        lic_col = "license_" + job_key.split("_")[1]
        if u.get(lic_col, 0) == 0:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📝 Начать тест", callback_data=f"starttest_{job_key}")], [InlineKeyboardButton(text="🔙 Гос. структуры", callback_data="gov_structures_back")]])
            return await cb.message.edit_text(f"⚠️ Для работы <b>{JOBS[job_key][0]}</b> нужно пройти тест.", reply_markup=kb, parse_mode="HTML")
    job_name = NEW_JOBS[job_key]["name"] if job_key in NEW_JOBS else JOBS[job_key][0]
    await cb.message.edit_text(f"💼 <b>{job_name}</b>", reply_markup=work_menu(job_key), parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data.startswith("starttest_"))
async def start_test(cb: CallbackQuery, state: FSMContext):
    job = cb.data.replace("starttest_", "")
    questions = []
    for source in TESTS[job]:
        answers = list(source["a"])
        correct_answer = answers[source["c"]]
        random.shuffle(answers)
        questions.append({"q": source["q"], "a": answers, "c": answers.index(correct_answer)})
    await state.set_state(TestStates.in_test)
    await state.update_data(job=job, idx=0, score=0, questions=questions)
    q = questions[0]
    kb = [[InlineKeyboardButton(text=a, callback_data=f"ans_{i}")] for i, a in enumerate(q["a"])]
    await cb.message.edit_text(f"📝 <b>Вопрос 1/{len(questions)}:</b>\n\n{q['q']}", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML"); await cb.answer()

@dp.callback_query(TestStates.in_test, F.data.startswith("ans_"))
async def process_answer(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data(); job, idx, score = data["job"], data["idx"], data["score"]
    questions = data.get("questions", TESTS[job])
    choice = int(cb.data.split("_")[1]); correct = questions[idx]["c"]
    if choice == correct: score += 1
    idx += 1
    if idx < len(questions):
        await state.update_data(idx=idx, score=score); q = questions[idx]
        kb = [[InlineKeyboardButton(text=a, callback_data=f"ans_{i}")] for i, a in enumerate(q["a"])]
        await cb.message.edit_text(f"📝 <b>Вопрос {idx+1}/{len(questions)}:</b>\n\n{q['q']}", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    else:
        await state.clear()
        passing_score = math.ceil(len(questions) * 0.8)
        if score >= passing_score:
            if job == "mreo_apply":
                save(cb.from_user.id, license_mreo=1); return_to="mreo_menu"; result="Ты принят на работу в МРЭО."
            elif job == "mreo_test_b":
                save(cb.from_user.id, license_auto=1); return_to="mreo_menu"; result="Водительское удостоверение категории B выдано."
            else:
                lic_col = "license_" + job.split("_")[1]; save(cb.from_user.id, **{lic_col: 1}); return_to=job; result="Доступ к работе открыт."
            await cb.message.edit_text(f"🎉 <b>Тест сдан!</b> ({score}/{len(questions)})\n{result}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Продолжить", callback_data=return_to)]]), parse_mode="HTML")
        else:
            await cb.message.edit_text(f"❌ <b>Тест провален.</b> ({score}/{len(questions)}). Нужно {passing_score} правильных.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Снова", callback_data=f"starttest_{job}")], [InlineKeyboardButton(text="🔙 Назад", callback_data="jobs")]]), parse_mode="HTML")
    await cb.answer()

JOBS = {
    "job_mvd": ("МВД", "polic.jpg", 3000, 6000, 25, 40, 0.9, 10), "job_mchs": ("МЧС", "pozarnik.jpg", 3500, 6500, 25, 40, 0.85, 10),
    "job_ems": ("МЗ", "skorka.jpg", 3000, 6000, 25, 40, 0.95, 10), "job_mreo": ("МРЭО", "mreo.jpg", 3500, 6500, 25, 40, 1.0, 10),
    "job_office": ("Офис", "ofic.jpg", 1000, 2000, 10, 20, 1.0, 1),
    "job_builder": ("Стройка", "stroika.jpg", 2500, 5000, 20, 35, 0.8, 2), "job_taxi": ("Таксист", "taxi.jpg", 1500, 3500, 15, 25, 0.9, 2),
    "job_it": ("Программист", "progra.jpg", 3500, 7000, 30, 50, 0.85, 5), "job_drug": ("Закладчик", "zakladka.jpg", 2500, 7000, 20, 40, 0.7, 1),
    "job_cook": ("Повар", "cook.jpg", 6000, 10000, 25, 30, 1.0, 3),
    "job_lumberjack": ("Лесоруб", "lumberjack.jpg", 7000, 12000, 30, 35, 1.0, 5),
    "job_fisherman": ("Рыбак", "fisherman.jpg", 6000, 11000, 28, 32, 1.0, 4),
    "job_farmer": ("Фермер", "farmer.jpg", 8000, 14000, 35, 40, 1.0, 7),
    "job_trucker": ("Дальнобойщик", "trucker.jpg", 15000, 30000, 50, 60, 1.0, 30)
}

@dp.callback_query(F.data.startswith("calls_"))
async def cb_calls(cb: CallbackQuery): await cb.message.edit_text("📞 Вызовы:", reply_markup=calls_menu(cb.data.replace("calls_", ""))); await cb.answer()

async def finish_new_job(cb: CallbackQuery, state: FSMContext, job_key: str):
    await state.clear()
    info = NEW_JOBS[job_key]
    u = get_user(cb.from_user.id)
    base_pay = random.randint(info["min"], info["max"])
    pay = int(base_pay * house_salary_multiplier(u) * vip_salary_multiplier(u))
    if boost_active(u, "money_boost_until"):
        pay = int(pay * 1.5)
    xp = int(info["xp"] * vip_xp_multiplier(u))
    if boost_active(u, "xp_boost_until"):xp*=2
    new_level, new_xp = add_experience(u["level"], u["xp"], xp)
    new_hunger = work_hunger_after(u, 10)
    health_penalty = work_health_penalty(u, 10, new_hunger)
    save(cb.from_user.id, money=u["money"] + pay, xp=new_xp, level=new_level, hunger=new_hunger, last_work=datetime.now().isoformat())
    if health_penalty: update_stats(cb.from_user.id, health_add=-health_penalty)
    log_player_action(cb.from_user, f"РАБОТА: {info['name']}, смена завершена, зарплата {pay} ₽")
    fatigue_text = f"\n⚠️ От голода потеряно {health_penalty} здоровья." if health_penalty else ""
    updated=get_user(cb.from_user.id)
    hospital_text = "\n🏥 Из-за истощения ты попал в больницу на 10 минут." if updated.get("hospital_time") and datetime.fromisoformat(updated["hospital_time"])>datetime.now() else ""
    await cb.message.edit_text(f"✅ Смена завершена: <b>{info['name']}</b>\n💰 Зарплата: +{pay:,} ₽\n✨ Опыт: +{xp} XP\n💼 Баланс: {u['money'] + pay:,} ₽{fatigue_text}{hospital_text}".replace(",", " "), parse_mode="HTML")
    await cb.answer("Зарплата получена!")

def trucker_game_keyboard(game: str, options=None):
    if game == "route":
        buttons = [InlineKeyboardButton(text=label, callback_data=f"truck_route_{key}") for key, label in [("up", "⬆️"), ("down", "⬇️"), ("left", "⬅️"), ("right", "➡️")]]
        return InlineKeyboardMarkup(inline_keyboard=[buttons, [InlineKeyboardButton(text="❌ Завершить", callback_data="newwork_cancel")]])
    if game == "load":
        buttons = [InlineKeyboardButton(text=f"{weight} т", callback_data=f"truck_load_{weight}") for weight in options]
        return InlineKeyboardMarkup(inline_keyboard=[[button] for button in buttons] + [[InlineKeyboardButton(text="❌ Завершить", callback_data="newwork_cancel")]])
    buttons = [InlineKeyboardButton(text=f"Место {n}", callback_data=f"truck_parking_{n}") for n in range(1, 5)]
    return InlineKeyboardMarkup(inline_keyboard=[[buttons[0], buttons[1]], [buttons[2], buttons[3]], [InlineKeyboardButton(text="❌ Завершить", callback_data="newwork_cancel")]])

@dp.callback_query(F.data.startswith("newwork_start_"))
async def newwork_start(cb: CallbackQuery, state: FSMContext):
    job_key = cb.data.removeprefix("newwork_start_")
    info = NEW_JOBS.get(job_key)
    u = get_user(cb.from_user.id)
    if not info or not u:
        return await cb.answer("Работа не найдена.", show_alert=True)
    ok, reason = check_status(cb.from_user.id)
    if not ok:
        return await cb.answer(reason, show_alert=True)
    if u["level"] < info["level"]:
        return await cb.answer(f"Нужен {info['level']} уровень!", show_alert=True)
    cooldown = work_cooldown(u)
    if u["last_work"] and datetime.now() - datetime.fromisoformat(u["last_work"]) < timedelta(seconds=cooldown):
        return await cb.answer(f"Следующая смена будет доступна через {cooldown} секунд.", show_alert=True)
    if job_key == "job_trucker":
        games = ["route", "load", "parking"]
        previous = u.get("last_trucker_game", "")
        available = [game for game in games if game != previous]
        game = random.choice(available)
        save(cb.from_user.id, last_trucker_game=game)
        await state.set_state(JobTaskStates.trucker_game)
        if game == "route":
            arrows = ["up", "down", "left", "right"]
            sequence = [random.choice(arrows) for _ in range(8)]
            await state.update_data(job_key=job_key, trucker_game=game, sequence=sequence, progress=0)
            arrow_labels = {"up": "⬆️", "down": "⬇️", "left": "⬅️", "right": "➡️"}
            pattern = " → ".join(arrow_labels[direction] for direction in sequence)
            text = f"🛣 <b>Навигация по маршруту — 8 поворотов</b>\nЗапомни последовательность: {pattern}\nПовтори её кнопками. Ошибка сбросит весь маршрут."
        elif game == "load":
            targets = [random.choice([10, 12, 14, 16, 18, 20]) for _ in range(5)]
            target_weight = targets[0]
            options = [target_weight - 2, target_weight, target_weight + 2]
            random.shuffle(options)
            await state.update_data(job_key=job_key, trucker_game=game, targets=targets, game_round=0, target_weight=target_weight, options=options)
            text = f"⚖️ <b>Погрузка — проверка 1/5</b>\nВ накладной указан вес <b>{target_weight} т</b>. Выбери правильную массу контрольного замера."
        else:
            parkings = [random.randint(1, 4) for _ in range(5)]
            await state.update_data(job_key=job_key, trucker_game=game, parkings=parkings, game_round=0, target_parking=parkings[0])
            text = f"🅿️ <b>Парковка — манёвр 1/5</b>\nЗаедь задним ходом точно на место №{parkings[0]}."
        await cb.message.edit_text(text, reply_markup=trucker_game_keyboard(game, options if game == "load" else None), parse_mode="HTML")
        await cb.answer("Для этой смены выбрана случайная мини-игра.")
        return
    await state.set_state(JobTaskStates.in_task)
    await state.update_data(job_key=job_key, progress=0)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{info['action']} (0/3)", callback_data="newwork_step")], [InlineKeyboardButton(text="❌ Завершить", callback_data="newwork_cancel")]])
    await cb.message.edit_text(f"💼 Смена: <b>{info['name']}</b>\nВыполни действие 3 раза, чтобы получить зарплату.", reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@dp.callback_query(JobTaskStates.in_task, F.data == "newwork_step")
async def newwork_step(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    job_key = data.get("job_key")
    info = NEW_JOBS.get(job_key)
    if not info:
        await state.clear()
        return await cb.answer("Смена сбросилась. Начни заново.", show_alert=True)
    progress = int(data.get("progress", 0)) + 1
    if progress < 3:
        await state.update_data(progress=progress)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{info['action']} ({progress}/3)", callback_data="newwork_step")], [InlineKeyboardButton(text="❌ Завершить", callback_data="newwork_cancel")]])
        await cb.message.edit_reply_markup(reply_markup=kb)
        await cb.answer(f"Готово: {progress}/3")
        return

    await finish_new_job(cb, state, job_key)

@dp.callback_query(JobTaskStates.trucker_game, F.data.startswith("truck_"))
async def trucker_minigame_step(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    game = data.get("trucker_game")
    job_key = data.get("job_key")
    if game == "route":
        choice = cb.data.removeprefix("truck_route_")
        sequence, progress = data["sequence"], data["progress"]
        if choice != sequence[progress]:
            await state.update_data(progress=0)
            arrow_labels = {"up": "⬆️", "down": "⬇️", "left": "⬅️", "right": "➡️"}
            pattern = " → ".join(arrow_labels[direction] for direction in sequence)
            await cb.message.edit_text(f"❌ Ошибка маршрута! Начни последовательность заново.\nЗапомни последовательность: {pattern}\nВведено: 0/8", reply_markup=trucker_game_keyboard("route"), parse_mode="HTML")
            return await cb.answer("Маршрут сброшен.", show_alert=True)
        progress += 1
        if progress < len(sequence):
            await state.update_data(progress=progress)
            arrow_labels = {"up": "⬆️", "down": "⬇️", "left": "⬅️", "right": "➡️"}
            pattern = " → ".join(arrow_labels[direction] for direction in sequence)
            await cb.message.edit_text(f"🛣 <b>Маршрут</b>\n{pattern}\nВведено: {progress}/8", reply_markup=trucker_game_keyboard("route"), parse_mode="HTML")
            await cb.answer(f"Поворот принят: {progress}/8")
            return
        return await finish_new_job(cb, state, job_key)
    if game == "load":
        choice = int(cb.data.removeprefix("truck_load_"))
        if choice != data["target_weight"]:
            return await cb.answer("Замер не совпал — эту проверку нужно повторить.", show_alert=True)
        game_round = data.get("game_round", 0) + 1
        if game_round >= 5:
            return await finish_new_job(cb, state, job_key)
        target_weight = data["targets"][game_round]
        options = [target_weight - 2, target_weight, target_weight + 2]
        random.shuffle(options)
        await state.update_data(game_round=game_round, target_weight=target_weight, options=options)
        await cb.message.edit_text(f"⚖️ <b>Погрузка — проверка {game_round + 1}/5</b>\nВ накладной указан вес <b>{target_weight} т</b>. Выбери правильную массу контрольного замера.", reply_markup=trucker_game_keyboard("load", options), parse_mode="HTML")
        await cb.answer(f"Проверка пройдена: {game_round}/5")
        return
    if game == "parking":
        choice = int(cb.data.removeprefix("truck_parking_"))
        if choice != data["target_parking"]:
            return await cb.answer("Не попал в карман — повтори этот манёвр.", show_alert=True)
        game_round = data.get("game_round", 0) + 1
        if game_round >= 5:
            return await finish_new_job(cb, state, job_key)
        parking = data["parkings"][game_round]
        await state.update_data(game_round=game_round, target_parking=parking)
        await cb.message.edit_text(f"🅿️ <b>Парковка — манёвр {game_round + 1}/5</b>\nЗаедь задним ходом точно на место №{parking}.", reply_markup=trucker_game_keyboard("parking"), parse_mode="HTML")
        await cb.answer(f"Манёвр пройден: {game_round}/5")
        return
    await state.clear()
    await cb.answer("Игра сбросилась. Начни смену заново.", show_alert=True)

@dp.callback_query(F.data == "newwork_cancel")
async def newwork_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Смена отменена. Зарплата не начислена.")
    await cb.answer()

@dp.callback_query(F.data == "newwork_step")
async def newwork_inactive(cb: CallbackQuery):
    await cb.answer("Сначала начни смену.", show_alert=True)

@dp.callback_query(F.data.startswith("do_call_") | F.data.startswith("do_job_"))
async def cb_work(cb: CallbackQuery):
    data = cb.data; u = get_user(cb.from_user.id)
    ok, msg = check_status(cb.from_user.id)
    if not ok: return await cb.answer(msg, show_alert=True)
    cooldown = work_cooldown(u)
    if u["last_work"] and datetime.now() - datetime.fromisoformat(u["last_work"]) < timedelta(seconds=cooldown):
        if u.get("energy_drinks", 0) > 0: save(cb.from_user.id, energy_drinks=u["energy_drinks"] - 1, last_work="")
        else: return await cb.answer(f"Ждать {cooldown} сек.", show_alert=True)

    if data.startswith("do_call_"): job_key = "_".join(data.split("_")[2:-1])
    else: job_key = data[3:]
    name, img_name, min_pay, max_pay, min_xp, max_xp, chance, req_lvl = JOBS[job_key]
    new_hunger = work_hunger_after(u, 15); health_penalty = work_health_penalty(u, 15, new_hunger)
    extra = "\n⚠️ <b>Ты истощен! -15 Здоровья.</b>" if health_penalty else ""

    if job_key == "job_drug" and random.random() < 0.3:
        save(cb.from_user.id, jail_time=(datetime.now() + timedelta(minutes=5)).isoformat(), last_work=datetime.now().isoformat(), hunger=new_hunger)
        return await cb.message.answer("🚔 Тебя повязали! КПЗ 5 минут.")

    success = random.random() < chance
    if not success and u.get("armor", 0) > 0:
        save(cb.from_user.id, armor=u["armor"] - 1); success = True; extra += "\n🛡 Броня спасла! (-1)"

    if success:
        pay = random.randint(min_pay, max_pay); xp = random.randint(min_xp, max_xp)
        if job_key in {"job_mvd", "job_mchs", "job_ems", "job_mreo"}:
            pay = random.randint(10_000, 15_000)
            xp = random.randint(200, 400)
        pay = int(pay * house_salary_multiplier(u) * vip_salary_multiplier(u))
        xp = int(xp * vip_xp_multiplier(u))
        if boost_active(u, "money_boost_until"):
            pay = int(pay * 1.5)
        if boost_active(u, "xp_boost_until"):
            xp *= 2
        new_level, new_xp = add_experience(u["level"], u["xp"], xp)
        save(cb.from_user.id, money=u["money"] + pay, xp=new_xp, level=new_level, last_work=datetime.now().isoformat(), hunger=new_hunger)
        update_stats(cb.from_user.id, health_add=-health_penalty)
        if new_level > u["level"]: extra += f"\n\n🎉 <b>УРОВЕНЬ ПОВЫШЕН!</b> Теперь у тебя {new_level} уровень!"
        text = f"✅ <b>{name}</b>\n💰 +{pay:,} ₽\n✨ +{xp} XP{extra}".replace(",", " ")
    else:
        save(cb.from_user.id, money=u["money"], last_work=datetime.now().isoformat(), hunger=new_hunger)
        update_stats(cb.from_user.id, health_add=-health_penalty)
        text = f"❌ Провал!\nТы не справился с задачей. Штрафа нет.{extra}".replace(",", " ")

    img = IMAGES / img_name
    if img.exists(): await cb.message.answer_photo(FSInputFile(img), caption=text, parse_mode="HTML")
    else: await cb.message.answer(text, parse_mode="HTML")
    await cb.answer()

# ==================== МАГАЗИН / АВТО / ДОМА / ПРОЧЕЕ ====================
@dp.callback_query(F.data == "buy_food")
async def buy_food(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    price = market_price(u, 5000)
    if u["money"] < price: return await cb.answer(f"Нужно {price:,} ₽!".replace(",", " "), show_alert=True)
    save(cb.from_user.id, money=u["money"] - price)
    update_stats(cb.from_user.id, hunger_add=-30)
    await cb.answer("🍔 Ты покушал! Голод снижен на 30.", show_alert=True)

@dp.callback_query(F.data == "buy_medkit")
async def buy_medkit(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    price = market_price(u, 15000)
    if u["money"] < price: return await cb.answer(f"Нужно {price:,} ₽!".replace(",", " "), show_alert=True)
    save(cb.from_user.id, money=u["money"] - price); update_stats(cb.from_user.id, health_add=30); await cb.answer("💊 Здоровье восстановлено!", show_alert=True)

@dp.callback_query(F.data == "buy_energy")
async def buy_energy(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    price = market_price(u, 10000)
    if u["money"] < price: return await cb.answer(f"Нужно {price:,} ₽!".replace(",", " "), show_alert=True)
    save(cb.from_user.id, money=u["money"] - price, energy_drinks=u.get("energy_drinks", 0) + 1); await cb.answer("Куплено!", show_alert=True)

@dp.callback_query(F.data == "buy_armor")
async def buy_armor(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    price = market_price(u, 50000)
    if u["money"] < price: return await cb.answer(f"Нужно {price:,} ₽!".replace(",", " "), show_alert=True)
    save(cb.from_user.id, money=u["money"] - price, armor=u.get("armor", 0) + 1); await cb.answer("Куплено!", show_alert=True)

@dp.callback_query(F.data == "buy_briefcase")
async def buy_briefcase(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    price = market_price(u, 20000)
    if u["money"] < price: return await cb.answer(f"Нужно {price:,} ₽!".replace(",", " "), show_alert=True)
    save(cb.from_user.id, money=u["money"] - price, briefcase=u.get("briefcase", 0) + 1); await cb.answer("Куплено!", show_alert=True)

@dp.callback_query(F.data == "buy_house_alarm")
async def buy_house_alarm(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if u.get("house") not in HOUSES_CATALOG:return await cb.answer("Для сигнализации сначала нужен свой дом.",show_alert=True)
    if u.get("house_alarm",0)>0:return await cb.answer(f"Сигнализация уже установлена: осталось {u['house_alarm']}/5 срабатываний.",show_alert=True)
    price = market_price(u, 75_000)
    if u["money"] < price: return await cb.answer(f"Нужно {price:,} ₽!".replace(",", " "), show_alert=True)
    save(cb.from_user.id, money=u["money"] - price, house_alarm=5)
    await cb.answer("🚨 Сигнализация установлена на 5 срабатываний!", show_alert=True)

@dp.callback_query(F.data.startswith("view_car_"))
async def view_car(cb: CallbackQuery):
    car_key = cb.data.replace("view_car_", "")
    name, price, img_name = CARS_CATALOG[car_key]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💸 Купить", callback_data=f"buy_car_{car_key}")],[InlineKeyboardButton(text="🔙 Назад", callback_data="back_cars")]])
    img = IMAGES / img_name
    if img.exists(): await cb.message.answer_photo(FSInputFile(img), caption=f"🚗 {name}\nЦена: {price:,} ₽".replace(",", " "), reply_markup=kb)
    else: await cb.message.answer(f"🚗 {name}\nЦена: {price:,} ₽".replace(",", " "), reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "back_cars")
async def back_cars(cb: CallbackQuery):
    await cb.message.delete(); await cb.message.answer("🚗 <b>Автосалон:</b>", reply_markup=cars_menu(get_user(cb.from_user.id)), parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data.startswith("buy_car_"))
async def confirm_buy_car(cb: CallbackQuery):
    car_key = cb.data.replace("buy_car_", "")
    if car_key not in CARS_CATALOG: return await cb.answer("Машина не найдена.", show_alert=True)
    buyer=get_user(cb.from_user.id)
    if car_recovery_pending(buyer):return await cb.answer("Дождись возврата застрахованной машины.",show_alert=True)
    if buyer.get("car") in CARS_CATALOG: return await cb.answer("Сначала продай текущую машину в профиле.", show_alert=True)
    price = CARS_CATALOG[car_key][1]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_car_{car_key}")],[InlineKeyboardButton(text="❌ Отказаться", callback_data="back_main")]])
    await cb.message.answer(f"Вы уверены, что хотите купить машину за {price:,} ₽?".replace(",", " "), reply_markup=kb); await cb.answer()

@dp.callback_query(F.data.startswith("confirm_car_"))
async def execute_buy_car(cb: CallbackQuery):
    car_key = cb.data.replace("confirm_car_", ""); u = get_user(cb.from_user.id)
    if car_key not in CARS_CATALOG: return await cb.answer("Машина не найдена.", show_alert=True)
    if car_recovery_pending(u):return await cb.answer("Дождись возврата застрахованной машины.",show_alert=True)
    if u.get("car") in CARS_CATALOG: return await cb.answer("Сначала продай текущую машину в профиле.", show_alert=True)
    price = CARS_CATALOG[car_key][1]
    if u["money"] < price: return await cb.answer("Мало денег!", show_alert=True)
    # Если 7-попыточная донатная защита куплена заранее, она применяется к следующей машине.
    save(cb.from_user.id, money=u["money"] - price, car=car_key, car_insurance=0)
    await cb.message.delete(); await cb.message.answer(f"🎉 Машина куплена: {CARS_CATALOG[car_key][0]}!"); await cb.answer()

@dp.callback_query(F.data == "sell_car")
async def sell_car(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    car_key = u.get("car")
    if car_key not in CARS_CATALOG:
        return await cb.answer("У тебя нет машины для продажи.", show_alert=True)
    car_name, price, _image = CARS_CATALOG[car_key]
    payout = price // 2
    save(cb.from_user.id, car="none", car_protection=0, car_insurance=0, money=u["money"] + payout)
    log_player_action(cb.from_user, f"ПРОДАЖА МАШИНЫ: {car_name}, получено {payout} ₽")
    updated = get_user(cb.from_user.id)
    await show_insurance(cb.message,updated,edit=True)
    await cb.answer(f"Продано за {payout:,} ₽".replace(",", " "), show_alert=True)

@dp.callback_query(F.data == "buy_car_protection")
async def buy_car_protection(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if u.get("car") not in CARS_CATALOG:
        return await cb.answer("Сначала нужна машина.", show_alert=True)
    if u.get("car_protection", 0) > 0:
        return await cb.answer("Защита уже установлена.", show_alert=True)
    if u["money"] < 500_000:
        return await cb.answer("Нужно 500 000 ₽.", show_alert=True)
    save(cb.from_user.id, money=u["money"] - 500_000, car_protection=5)
    log_player_action(cb.from_user, "КУПЛЕНА ЗАЩИТА АВТО ОТ УГОНА за 500 000 ₽ (5 блокировок)")
    updated = get_user(cb.from_user.id)
    await show_insurance(cb.message,updated,edit=True)
    await cb.answer("Защита установлена на 5 попыток.", show_alert=True)

@dp.callback_query(F.data.startswith("buy_house_"))
async def confirm_buy_house(cb: CallbackQuery):
    house_key = cb.data.replace("buy_house_", "")
    if house_key not in HOUSES_CATALOG: return await cb.answer("Дом не найден.", show_alert=True)
    if get_user(cb.from_user.id).get("house") in HOUSES_CATALOG: return await cb.answer("Сначала продай текущий дом в профиле.", show_alert=True)
    prices = {key: values[1] for key, values in HOUSES_CATALOG.items()}
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_house_{house_key}")],[InlineKeyboardButton(text="❌ Отказаться", callback_data="back_main")]])
    await cb.message.answer(f"Вы уверены, что хотите купить дом за {prices[house_key]:,} ₽?".replace(",", " "), reply_markup=kb); await cb.answer()

@dp.callback_query(F.data.startswith("confirm_house_"))
async def execute_buy_house(cb: CallbackQuery):
    house_key = cb.data.replace("confirm_house_", ""); u = get_user(cb.from_user.id)
    if house_key not in HOUSES_CATALOG: return await cb.answer("Дом не найден.", show_alert=True)
    if u.get("house") in HOUSES_CATALOG: return await cb.answer("Сначала продай текущий дом в профиле.", show_alert=True)
    prices = {key: values[1] for key, values in HOUSES_CATALOG.items()}
    if u["money"] < prices[house_key]: return await cb.answer("Мало денег!", show_alert=True)
    save(cb.from_user.id, money=u["money"] - prices[house_key], house=house_key, house_insurance=0, last_house_collect=datetime.now().isoformat())
    await cb.message.delete(); await cb.message.answer("🎉 Дом куплен!"); await cb.answer()

@dp.callback_query(F.data == "collect_house")
async def collect_house(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if u.get("house") not in HOUSES_CATALOG: return await cb.answer("У тебя нет дома.", show_alert=True)
    if datetime.now() - datetime.fromisoformat(u["last_house_collect"]) < timedelta(hours=1): return await cb.answer("Ждать 1 час!", show_alert=True)
    inc = {"house_dacha": 2000, "house_townhouse": 8000, "house_penthouse": 30000, "house_cottage": 8000, "house_villa": 12000, "house_mansion": 18000, "house_castle": 25000}.get(u["house"], 0)
    save(cb.from_user.id, money=u["money"] + inc, last_house_collect=datetime.now().isoformat())
    await cb.message.answer(f"💰 Доход: +{inc:,} ₽".replace(",", " ")); await cb.answer()

@dp.callback_query(F.data == "sell_house")
async def sell_house(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    house_key = u.get("house")
    if house_key not in HOUSES_CATALOG:
        return await cb.answer("У тебя нет дома для продажи.", show_alert=True)
    house_name, price = HOUSES_CATALOG[house_key]
    payout = price // 2
    save(cb.from_user.id, house="none", house_alarm=0, house_insurance=0, last_house_collect="", money=u["money"] + payout)
    log_player_action(cb.from_user, f"ПРОДАЖА ДОМА: {house_name}, получено {payout} ₽")
    updated = get_user(cb.from_user.id)
    await cb.message.edit_text(profile_text(updated), reply_markup=profile_actions(updated), parse_mode="HTML")
    await cb.answer(f"Дом продан за {payout:,} ₽".replace(",", " "), show_alert=True)

@dp.callback_query(F.data == "buy_coffee")
async def buy_coffee(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if u["money"] < 1_000_000: return await cb.answer("Нужен 1 млн!", show_alert=True)
    save(cb.from_user.id, money=u["money"] - 1_000_000, business="coffee", last_business_collect=datetime.now().isoformat())
    text = "🎉 Кофейня куплена!"; img = IMAGES / "magazin.jpg"
    if img.exists(): await cb.message.answer_photo(FSInputFile(img), caption=text, reply_markup=business_menu(get_user(cb.from_user.id)))
    else: await cb.message.answer(text, reply_markup=business_menu(get_user(cb.from_user.id)))
    await cb.answer()

@dp.callback_query(F.data == "collect_business")
async def collect_business(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if datetime.now() - datetime.fromisoformat(u["last_business_collect"]) < timedelta(days=1): return await cb.answer("Ждать 24 часа!", show_alert=True)
    net = random.randint(100_000, 200_000)
    income = net + 75_000
    save(cb.from_user.id, money=max(0, u["money"] + net), last_business_collect=datetime.now().isoformat())
    await cb.message.answer(f"📊 Доход: {income:,} ₽\nРасход: 75 000 ₽\nЧистая прибыль: +{net:,} ₽".replace(",", " "), reply_markup=business_menu(get_user(cb.from_user.id))); await cb.answer()

@dp.callback_query(F.data == "hire_dealer")
async def hire_dealer(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if u["money"] < 50_000: return await cb.answer("Нужно 50к!", show_alert=True)
    save(cb.from_user.id, money=u["money"] - 50_000, dealers=u.get("dealers", 0) + 1, last_dealer_collect=datetime.now().isoformat())
    await cb.message.answer("🤝 Дилер нанят!", reply_markup=business_menu(get_user(cb.from_user.id))); await cb.answer()

@dp.callback_query(F.data == "collect_dealers")
async def collect_dealers(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if datetime.now() - datetime.fromisoformat(u["last_dealer_collect"]) < timedelta(hours=1): return await cb.answer("Ждать 1 час!", show_alert=True)
    income = u["dealers"] * 20_000; extra = ""
    if random.random() < 0.15: income = 0; save(cb.from_user.id, dealers=0); extra = "\n🚔 Облава! Дилеры сбежали."
    save(cb.from_user.id, money=u["money"] + income, last_dealer_collect=datetime.now().isoformat())
    await cb.message.answer(f"💰 Дилеры принесли: {income:,} ₽{extra}".replace(",", " "), reply_markup=business_menu(get_user(cb.from_user.id))); await cb.answer()

@dp.callback_query(F.data == "bribe")
async def bribe(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if u["money"] < 100_000: return await cb.answer("Нужно 100к!", show_alert=True)
    save(cb.from_user.id, money=u["money"] - 100_000); await cb.answer("💸 Взятка дана!", show_alert=True)

@dp.callback_query(F.data == "bail")
async def bail(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if not u["jail_time"] or datetime.fromisoformat(u["jail_time"]) <= datetime.now(): return await cb.answer("Ты не в КПЗ!", show_alert=True)
    if u["money"] < 50_000: return await cb.answer("Нужно 50к!", show_alert=True)
    save(cb.from_user.id, money=u["money"] - 50_000, jail_time=""); await cb.message.answer("💸 Вышел под залог!"); await cb.answer()

@dp.callback_query(F.data == "back_main")
async def cb_back(cb: CallbackQuery): await cb.message.delete(); await cb.answer()

async def insurance_recovery_loop():
    while True:
        now=datetime.now().isoformat()
        cur.execute("SELECT user_id FROM users WHERE car_recovery_at!='' AND car_recovery_at<=?",(now,))
        due_users=[row[0] for row in cur.fetchall()]
        for uid in due_users:
            car_name=recover_insured_car(uid)
            if car_name:
                try:await bot.send_message(uid,f"🛡 Страховка вернула твою машину: {car_name}. Она снова в гараже.")
                except Exception:pass
        await asyncio.sleep(60)

async def main():
    print("Бот запущен!")
    recovery_task=asyncio.create_task(insurance_recovery_loop())
    try:
        await dp.start_polling(bot)
    finally:
        recovery_task.cancel()
        await asyncio.gather(recovery_task,return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())




