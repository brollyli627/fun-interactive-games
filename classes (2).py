"""
ARENA CLASH - a real-time 2D arena fighter.

Grown out of the original turn-based terminal battle (kept in classes_backup.py):
the same damage formula now drives three characters crossed with three fighting
styles, three game modes, and two bosses that do not play by the style rules.

PICK THREE TIMES
    Character - who you are: HP, speed, power, and which super you get.
    Style ..... what you fight WITH: all three weapon slots.
    Mode ...... how the night goes.
    A character's super rewrites itself to suit the style. Bob inflating his
    shots means nothing to a melee god, so for them it inflates the swing arc
    instead; for a gunslinger it tears out the reloads.

AIM AND STANCE
    The cursor is your crosshair - your shots leave on the line you point.
    The arc is capped either side of level, and the AI still fires level, so
    stance is still the thing that decides most exchanges:
      * crouch halves your height, so near-misses stay misses
      * jumping clears low shots
      * melee reaches both stances - the answer to a turtling crouch
    Three weapons ignore aim on purpose: the shotgun sprays a fan, the rocket
    has a proximity fuse, and the potion and knives steer themselves.

TWO KINDS OF COOLDOWN
    Weapon cooldown . runs after every use so you cannot spam a slot. Every
                      weapon in the game has one.
    Usage cooldown .. only on the heavy weapons. The first shot opens a live
                      window; when the window expires, or the shots run out,
                      that slot locks out for several seconds. No basic
                      attack has one.

STYLES
    SORCERER ... 1 Fireball (burn)  2 Ice (slow/freeze)   3 Bolt (stun)
    GUNSLINGER . 1 Pistol (free)    2 Shotgun (3 in 4s)   3 Rocket (one shot)
    MELEE GOD .. 1 Bat (free, = J)  2 Knives (12 in 4s)   3 Splash Potion

MODES
    QUICK ....... one opponent, best of three rounds.
    TOURNAMENT .. three one-round bouts, a shop between each.
    CONTINUE .... clearing a tournament does not end the run. You keep every
                  stat, card and coin, and pick one of:
      ENDLESS ... one round at a time, forever. Opponents open below parity
                  and compound about 6% a round, so the ramp is gentle right
                  up until it is not. Every fourth round is a boss, climbing
                  at roughly half that rate so it stays a spike, not a wall.
      BOSS ...... straight at Sensei or Steve, best of three, unscaled.
    Bosses are never on the main menu - they are somewhere you get to.
    The potion is the only weapon that does not care whose side you are on:
    it steers, shatters for slow + a stun + a small burn, leaves gas that
    keeps burning, stuns a second time as the gas breaks up - and catches
    you in all of it if you threw it at your own feet.

AIRDROPS
    A crate parachutes in mid-round and the first fighter to touch it keeps
    it: a health pack, a 10s stat boost, or 7.5s of near-invisibility that
    genuinely loses the AI - it tracks your last known position instead.

MODES
    QUICK ....... one opponent, best of three rounds.
    TOURNAMENT .. three opponents, one round each, and a shop between every
                  round. Gold buys flat speed/damage/HP; the upgrade cards
                  are free. Three cards, one bound to each of your weapons,
                  and you take one - so a card raises the reach of ONE
                  weapon, never the style. Every rarity is a flat 1-in-4;
                  there is no luck stat. First reroll each rest is free and
                  the next ones climb.
    BOSS ........ Sensei steps through any gap you thought you had and
                  answers being kited with a dash. Steve arcs arrows, lobs
                  TNT and drops cobblestone walls that eat your shots. Both
                  are beatable, and neither is quick.

CONTROLS
    Aim ............... mouse             (turns you and points your shots)
    Move .............. A / D            (or Left / Right)
    Jump .............. W / Space        (Max can double jump)
    Crouch ............ S                (or Down)
    Strike ............ J                (a melee god swings their bat)
    Weapons ........... 1  2  3          (whatever your style carries)
    Super ............. Q
    Shield ............ hold K           (only kits that have one)
    Shop .............. 1/2/3 buy, A/D pick a card, R reroll, ENTER continue
    Pause ............. P or Esc
    Restart ........... R on the results screen

Run it with:  python3 classes.py     (needs pygame-ce)
"""

import json
import math
import os
import random
import sys
from array import array
from dataclasses import dataclass, field

import pygame

# ---------------------------------------------------------------- config ----

WIDTH, HEIGHT = 1000, 560
GROUND_Y = 472
WALL_MARGIN = 46
FPS = 60
GRAVITY = 0.62
JUMP_VELOCITY = -13.4
ROUNDS_TO_WIN = 2              # best of three
ROUND_SECONDS = 60
CROUCH_SQUASH = 0.56           # how far the body compresses when crouching
# How much a fighter's size feeds into melee reach. At 1.0 a big body swings
# proportionally further, which hands the heaviest character the melee styles
# outright; at 0.0 a katana is a katana no matter who holds it. Simulation
# says 1.0: a big body's reach is the counterweight that stops the fastest
# character running away with every melee matchup.
REACH_BUILD = 1.0
# How far off level a shot can be aimed. Shots are no longer locked to the
# horizontal - the player aims with the cursor and the AI aims by skill - but
# the arc is capped, so a crouch is still a smaller target worth taking and
# straight-up/straight-down shots are off the table.
AIM_ARC = math.radians(52)

# --------------------------------------------------------------- palette ----

BLACK      = (10, 10, 16)
WHITE      = (245, 246, 255)
DIM        = (128, 134, 158)
PANEL      = (22, 24, 36)
GOLD       = (255, 205, 96)
CRIT       = (255, 236, 150)
DANGER     = (232, 78, 78)

SKY_TOP    = (16, 14, 34)
SKY_BOTTOM = (86, 44, 74)
MOUNTAIN_1 = (30, 26, 52)
MOUNTAIN_2 = (44, 34, 66)
GROUND_TOP = (58, 44, 66)
GROUND_LOW = (24, 19, 32)

# --------------------------------------------------------------- weapons ----


@dataclass(frozen=True)
class Weapon:
    """One slot in a fighting style.

    TWO KINDS OF COOLDOWN, and they are not the same thing:

    `cooldown` is the WEAPON cooldown - the anti-spam timer that runs after
    every single use. Every weapon in the game has one.

    `window` / `uses` / `lockout` are the USAGE cooldown, and only the heavy
    weapons carry it. The first shot opens a live window; when that window
    runs out - or when the shots run dry - the weapon locks out completely
    for `lockout` seconds. Basic attacks never have one.
    """
    key: str
    name: str
    short: str
    kind: str                   # "shot" (projectile) or "swing" (melee arc)
    multiplier: float
    cooldown: float             # weapon cooldown: runs after every use
    core: tuple
    glow: tuple
    art: str
    effect: str = ""            # burn / ice / stun / "" 
    ideal_range: tuple = (90, 420)
    # -- shots --
    speed: float = 8.0
    radius: int = 12
    life: float = 2.6           # seconds aloft, so also the effective range
    pellets: int = 1            # >1 fans out into a spray
    spread: float = 0.0         # vertical fan per pellet step
    homing: float = 0.0         # degrees of turn per frame while tracking
    splash: float = 0.0         # blast radius on detonation
    splash_share: float = 0.0   # fraction of the damage the blast carries
    selfharm: float = 0.0       # share of the blast the thrower eats too
    cloud: float = 0.0          # seconds of lingering gas left behind
    drop: float = 0.0           # gravity per frame - makes a shot arc
    boss_only: bool = False     # never appears in a player's style
    # -- swings --
    reach: float = 78           # how far forward the arc extends
    lift: float = 96            # how tall the arc is
    swing: float = 0.18         # how long the arc stays out
    knock: float = 1.0          # knockback multiplier on connect
    # -- usage cooldown --
    uses: int = 0               # shots before lockout; 0 = unlimited
    window: float = 0.0         # seconds live from the first shot; 0 = none
    lockout: float = 0.0        # seconds locked once spent

    @property
    def limited(self):
        """True when this weapon carries a usage cooldown."""
        return bool(self.uses or self.window)


WEAPONS = {
    # ---------------------------------------------------------- sorcerer --
    "fireball": Weapon(
        key="fireball", name="Fireball", short="Fireball", kind="shot",
        multiplier=2.0, cooldown=1.55, speed=7.4, radius=14,
        core=(255, 236, 170), glow=(255, 118, 36), art="fire",
        effect="burn", ideal_range=(130, 430),
    ),
    "ice": Weapon(
        key="ice", name="Ice Blast", short="Ice", kind="shot",
        multiplier=1.5, cooldown=0.95, speed=10.6, radius=11,
        core=(232, 252, 255), glow=(88, 190, 255), art="ice",
        effect="ice", ideal_range=(110, 400),
    ),
    "bolt": Weapon(
        key="bolt", name="Lightning Bolt", short="Bolt", kind="shot",
        multiplier=1.75, cooldown=2.3, speed=17.0, radius=9,
        core=(255, 255, 220), glow=(190, 150, 255), art="bolt",
        effect="stun", ideal_range=(180, 760),
    ),

    # -------------------------------------------------------- gunslinger --
    # The basic attack: no usage cooldown, just a very short weapon cooldown.
    "pistol": Weapon(
        key="pistol", name="Pistol", short="Pistol", kind="shot",
        multiplier=0.34, cooldown=0.25, speed=15.5, radius=5, life=1.5,
        core=(255, 250, 214), glow=(255, 196, 86), art="bullet",
        ideal_range=(80, 560),
    ),
    # Four pellets in a vertical fan - the only shot in the game that can
    # clip a crouching target, and only at knife range.
    "shotgun": Weapon(
        key="shotgun", name="Shotgun", short="Shotgun", kind="shot",
        multiplier=0.60, cooldown=0.85, speed=12.4, radius=6, life=0.34,
        pellets=4, spread=1.55, knock=0.4,
        core=(255, 228, 180), glow=(255, 150, 70), art="pellet",
        ideal_range=(70, 250),
        uses=3, window=4.0, lockout=6.5,
    ),
    # One rocket, then nine seconds of nothing. A proximity fuse means it is
    # the one gun answer to a turtling crouch - for half damage.
    "rocket": Weapon(
        key="rocket", name="Rocket", short="Rocket", kind="shot",
        multiplier=3.0, cooldown=1.4, speed=7.0, radius=13, life=2.4,
        splash=88, splash_share=0.5,
        core=(255, 240, 200), glow=(255, 110, 50), art="rocket",
        ideal_range=(150, 700),
        uses=1, lockout=9.0,
    ),

    # -------------------------------------------------------- melee god ---
    # The basic attack. Long enough that closing the gap is a plan rather
    # than a coin flip - a melee god that has to stand on your toes to swing
    # loses the fight on the way in.
    "bat": Weapon(
        key="bat", name="Baseball Bat", short="Bat", kind="swing",
        multiplier=1.45, cooldown=0.50, reach=124, lift=104, swing=0.20,
        knock=1.55, core=(255, 226, 168), glow=(214, 158, 92), art="bat",
        ideal_range=(0, 124),
    ),
    # A four-second flurry on a medium lockout. Each knife is honest middling
    # damage; the burst is what makes it worth the reload.
    "knives": Weapon(
        key="knives", name="Throwing Knives", short="Knives", kind="shot",
        multiplier=1.10, cooldown=0.32, speed=12.5, radius=6, life=1.7,
        homing=2.2, core=(236, 242, 255), glow=(150, 178, 210), art="knife",
        ideal_range=(90, 520),
        uses=12, window=4.0, lockout=6.5,
    ),
    # The style's heavy hitter, and the only weapon in the game that does not
    # care whose side you are on. It steers, it shatters, it leaves gas, and
    # standing in your own throw hurts.
    "potion": Weapon(
        key="potion", name="Splash Potion", short="Potion", kind="shot",
        multiplier=0.85, cooldown=2.6, speed=7.2, radius=12, life=2.6,
        homing=2.6, splash=78, splash_share=0.75, selfharm=0.40, cloud=3.0,
        core=(238, 196, 255), glow=(168, 92, 220), art="potion",
        effect="toxin", ideal_range=(150, 520),
    ),

    # ------------------------------------------------------------ bosses --
    # None of these are buyable, rollable or selectable. They exist so a boss
    # can do things the styles cannot answer with a straight trade.

    # SENSEI - an open palm that throws you across the arena.
    "palm": Weapon(
        key="palm", name="Open Palm", short="Palm", kind="swing",
        multiplier=1.25, cooldown=0.62, reach=112, lift=108, swing=0.20,
        knock=2.3, core=(255, 226, 200), glow=(255, 132, 96), art="palm",
        ideal_range=(0, 112), boss_only=True,
    ),
    # A wave that runs along the floor. Crouching is the wrong answer; the
    # only clean out is to be in the air when it arrives.
    "wave": Weapon(
        key="wave", name="Ground Wave", short="Wave", kind="shot",
        multiplier=1.5, cooldown=3.1, speed=8.6, radius=30, life=2.2,
        core=(255, 236, 214), glow=(255, 118, 70), art="wave",
        effect="stun", ideal_range=(120, 720), boss_only=True,
    ),
    # Six strikes in three seconds, then he has to breathe.
    "flurry": Weapon(
        key="flurry", name="Flurry", short="Flurry", kind="swing",
        multiplier=0.72, cooldown=0.17, reach=86, lift=104, swing=0.11,
        knock=0.35, core=(255, 244, 226), glow=(255, 168, 120), art="flurry",
        ideal_range=(0, 86), uses=6, window=3.0, lockout=5.0, boss_only=True,
    ),

    # STEVE - an arrow that drops on the way in, so range changes the aim.
    "arrow": Weapon(
        key="arrow", name="Bow", short="Bow", kind="shot",
        multiplier=1.15, cooldown=0.78, speed=13.5, radius=7, life=2.4,
        drop=0.16, core=(238, 226, 196), glow=(160, 134, 92), art="arrow",
        ideal_range=(140, 640), boss_only=True,
    ),
    # Lobbed, fused, and it takes a chunk out of the floor plan.
    "tnt": Weapon(
        key="tnt", name="TNT", short="TNT", kind="shot",
        multiplier=2.4, cooldown=4.2, speed=8.2, radius=15, life=1.5,
        drop=0.30, splash=104, splash_share=0.62,
        core=(255, 232, 214), glow=(226, 74, 58), art="tnt",
        ideal_range=(150, 520), boss_only=True,
    ),
    # A wall. It eats shots until it breaks, and it is the reason a gun
    # cannot simply out-range him.
    "block": Weapon(
        key="block", name="Cobblestone", short="Block", kind="block",
        multiplier=0.0, cooldown=6.0, core=(176, 176, 176), glow=(112, 112, 112),
        art="block", ideal_range=(90, 620), uses=1, lockout=7.5, boss_only=True,
    ),

    # The universal light melee that ranged styles keep on J - the answer to
    # a crouch when every shot you own flies level.
    "strike": Weapon(
        key="strike", name="Strike", short="Strike", kind="swing",
        multiplier=0.85, cooldown=0.46, reach=78, lift=96, swing=0.18,
        core=WHITE, glow=(210, 214, 240), art="strike", ideal_range=(0, 78),
    ),
}


@dataclass(frozen=True)
class Style:
    """A fighting style: three weapons on 1/2/3 and what J does."""
    key: str
    name: str
    title: str
    blurb: str
    weapons: tuple
    strike_key: str             # what the J button swings
    accent: tuple
    move: float = 1.0           # style-wide movement multiplier
    armor: float = 1.0          # style-wide incoming damage multiplier
    knockback: float = 1.0      # style-wide knockback taken


STYLES = {
    "sorcerer": Style(
        key="sorcerer", name="SORCERER", title="THE CASTER",
        blurb="status effects and control",
        weapons=("fireball", "ice", "bolt"), strike_key="strike",
        accent=(190, 150, 255),
    ),
    "gun": Style(
        key="gun", name="GUNSLINGER", title="THE TRIGGER",
        blurb="chip fast, commit hard",
        weapons=("pistol", "shotgun", "rocket"), strike_key="strike",
        accent=(255, 196, 86),
    ),
    # J is the universal light jab - except for the melee god, whose J is
    # their bat. Handing them the jab AS WELL was tested and is badly broken:
    # a melee fighter is always at jab range, so it is a permanent free
    # fourth weapon and puts the style at 63-90% against the field.
    "melee": Style(
        key="melee", name="MELEE GOD", title="THE CLOSER",
        blurb="all of it is in your face",
        weapons=("bat", "knives", "potion"), strike_key="bat",
        accent=(120, 224, 255),
        # No movement bonus. One was needed only while the AI parked itself
        # outside its own reach; once it closes properly, a melee god that
        # also outruns you wins every matchup.
        move=1.0,
        # A melee god plants their feet. Without this, whoever lands first in
        # a melee mirror shoves the other out of reach and never lets them
        # back in - a runaway the low-knockback character always wins.
        knockback=0.55,
    ),
}
# Boss kits live in the same table so they reuse every cooldown, usage and
# HUD path the player styles do - they are simply never offered for choice.
STYLES["sensei"] = Style(
    key="sensei", name="SENSEI", title="THE MASTER",
    blurb="closes any gap you thought you had",
    weapons=("palm", "wave", "flurry"), strike_key="palm",
    accent=(255, 132, 96), move=1.16,
)
STYLES["steve"] = Style(
    key="steve", name="STEVE", title="THE BUILDER",
    blurb="brings the terrain with him",
    weapons=("arrow", "tnt", "block"), strike_key="strike",
    accent=(120, 200, 130), move=0.96,
)

STYLE_ORDER = ["sorcerer", "gun", "melee"]      # player-selectable only

# Status tuning, all in seconds unless noted.
BURN_SECONDS = 3.2
BURN_TICK = 0.4
BURN_DAMAGE = 6                # -> 48 damage over a full burn
STUN_SECONDS = 0.95
SLOW_SECONDS = 2.2
SLOW_FACTOR = 0.45
FREEZE_HITS = 3                # ice hits needed...
FREEZE_WINDOW = 3.5            # ...inside this many seconds...
FREEZE_SECONDS = 1.0           # ...to lock the target down completely
COMBO_WINDOW = 1.3

# SURGE lifesteal (Andy only). A cut of the damage just dealt, capped per
# hit. The cap is what makes this "small but spammy weapons heal a lot,
# heavy weapons only mediocre": a knife for ~15 damage gives back under the
# cap and scales with how often you land it, while a rocket for ~45 damage
# would give back triple the cap if it scaled freely - so it gets clipped to
# the same modest number as everything else. Landing hits heals; the size of
# any single hit barely matters.
LIFESTEAL_PCT = 0.16
LIFESTEAL_CAP = 4

# Splash potion. Two separate stuns: one when the glass breaks, one when the
# gas finally disperses - so standing in the cloud to keep swinging costs you.
POTION_STUN = 0.34             # the impact stun
POTION_CHOKE = 0.42            # the second stun, as the cloud breaks up
POTION_SLOW = 2.6
POTION_BURN = 1.6              # a splash, not a fireball
CLOUD_TICK = 0.45
CLOUD_DAMAGE = 3

# Airdrops. A crate parachutes in mid-round and whoever touches it first
# keeps it - which means breaking off to go and get it, in front of someone
# who would rather you did not.
DROP_FIRST = 11.0              # seconds into the round before the first one
DROP_EVERY = (15.0, 21.0)      # and the gap between the rest
DROP_FALL = 2.4                # descent speed under the chute
DROP_LIFE = 15.0               # how long it waits on the ground
DROP_KINDS = ("health", "boost", "ghost")
PICKUP_HEAL = 72
BOOST_SECONDS = 10.0
BOOST_DAMAGE = 1.22
BOOST_MOVE = 1.16
GHOST_SECONDS = 7.5

# Game modes. Quick is the original best-of-three. Tournament is three
# one-round bouts against three different opponents with a shop in between.
# Boss puts you in front of something that does not play by the style rules.
MODES = {
    "quick": ("QUICK MATCH", "best of three rounds",
              "one opponent, first to two rounds takes it"),
    "tournament": ("TOURNAMENT", "three rounds, shop between",
                   "three opponents, one round each - lose one and you are out"),
    "boss": ("BOSS FIGHT", "it does not fight fair",
             "one boss with moves no style in the game can buy"),
    "endless": ("ENDLESS", "it never stops getting worse",
                "every round the opponent is stronger, and bosses turn up"),
}
# You cannot pick a boss off the menu. Clear the tournament and the CONTINUE
# screen offers them - along with endless, which is where they recur.
MODE_ORDER = ["quick", "tournament"]
CONTINUE_ORDER = ["endless", "boss"]
TOURNAMENT_STAGES = 3

# Endless scaling, compounding per round. The normal climb is steep enough
# that the late rounds are genuinely unwinnable; bosses climb at about half
# that, because they start from a much higher floor already.
# Endless opens below parity on purpose. A single lost round ends the run, so
# starting at even odds means half of all runs die on round one; starting soft
# gives you a ramp to climb and makes the compounding the thing that kills you.
ENDLESS_START = 0.72
ENDLESS_GROWTH = 1.045
# The per-round growth itself grows. A flat compounding rate loses to a player
# who banks shop upgrades every round - runs either died early or snowballed
# forever - so the exponent widens with depth. Early rounds barely move; the
# late ones run away and never come back.
ENDLESS_RAMP = 40
ENDLESS_BOSS_RAMP = 60         # bosses widen slower, as they climb slower
# Bosses have to be a spike, not a rest. The first pass discounted their
# opening AND grew them slower, which stacked into boss rounds that were
# *easier* than the normal rounds either side of them. They now open close to
# full strength and climb at about the same rate, so they stay ahead of the
# curve without running away from it.
ENDLESS_BOSS_START = 0.80
ENDLESS_BOSS_GROWTH = 1.030


def endless_scale_at(stage, boss):
    """How much stronger the round-`stage` opponent is than its base self."""
    n = max(0, stage - 1)
    if boss:
        start, growth, ramp = (ENDLESS_BOSS_START, ENDLESS_BOSS_GROWTH,
                               ENDLESS_BOSS_RAMP)
    else:
        start, growth, ramp = ENDLESS_START, ENDLESS_GROWTH, ENDLESS_RAMP
    return start * growth ** (n * (1 + n / ramp))
ENDLESS_BOSS_EVERY = 4         # rounds 4, 8, 12 ... are boss rounds
GOLD_PER_ENDLESS = 80
# Bosses get a flat edge on hard as well as a sharper brain, so the two
# settings actually feel like two settings rather than one noisy one.
BOSS_EDGE = {"normal": 1.0, "hard": 1.03}

# Boss fights are earned, not picked. Clearing a tournament unlocks them, and
# the unlock is remembered between sessions so you only do it once.
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "arena_save.json")


def load_progress():
    """Read the save file. A missing or broken one just means "new player"."""
    try:
        with open(SAVE_PATH) as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_progress(data):
    """Best effort - a read-only disk must never take the game down."""
    try:
        with open(SAVE_PATH, "w") as fh:
            json.dump(data, fh)
    except OSError:
        pass
# Payouts. Awarded once per cleared bout in next_round() and nowhere else -
# paying again per round made a tournament stage worth more than twice an
# endless round for no reason anybody could see.
GOLD_PER_STAGE = 95

# Shop: flat stats cost gold, upgrade cards are free. Prices climb each time
# you buy the same one so gold never turns into one runaway stat.
SHOP_ITEMS = [("SPEED", "+6% move speed", 45, 25),
              ("DAMAGE", "+8% attack power", 55, 30),
              ("HEALTH", "+34 max HP", 50, 25)]
REROLL_COSTS = [0, 40, 80, 160, 320]     # first one each round is free

# Every rarity is exactly as likely as every other - there is no luck stat
# and no pity timer. Rarity only decides how big the number is.
CARD_RARITIES = ["common", "rare", "epic", "legendary"]
CARD_TIER = {"common": 1.0, "rare": 1.7, "epic": 2.5, "legendary": 3.6}
CARD_COLOR = {"common": (168, 176, 198), "rare": (96, 178, 255),
              "epic": (196, 118, 255), "legendary": (255, 190, 78)}

# (field, label, step, sense) - sense -1 means "lower is better".
CARD_EFFECTS = [
    ("multiplier", "damage", 0.06, 1),
    ("cooldown", "weapon cooldown", 0.05, -1),
    ("reach", "reach", 0.07, 1),
    ("speed", "projectile speed", 0.07, 1),
    ("homing", "tracking", 0.10, 1),
    ("window", "usage window", 0.10, 1),
    ("lockout", "usage lockout", 0.07, -1),
    ("splash", "blast radius", 0.08, 1),
    ("uses_add", "shots per window", 1, 1),
]


@dataclass(frozen=True)
class Card:
    """One upgrade, bound to one weapon. Never to the whole style."""
    weapon: str
    rarity: str
    field: str
    amount: float
    label: str

    @property
    def color(self):
        return CARD_COLOR[self.rarity]


def card_options(w):
    """Which upgrades even make sense for this weapon."""
    out = []
    for field, label, step, sense in CARD_EFFECTS:
        if field == "reach" and w.kind != "swing":
            continue
        # speed/homing/splash only mean anything to something that flies.
        if field in ("speed", "homing", "splash"):
            if w.kind != "shot" or not getattr(w, field):
                continue
        if field in ("window", "lockout", "uses_add") and not w.limited:
            continue
        if field == "uses_add" and not w.uses:
            continue
        if field == "window" and not w.window:
            continue
        if field == "multiplier" and w.kind == "block":
            continue
        out.append((field, label, step, sense))
    return out or [("cooldown", "weapon cooldown", 0.05, -1)]


def roll_card(weapon_key):
    """Roll one card for one weapon. Rarity is a flat 1-in-4, always."""
    w = WEAPONS[weapon_key]
    rarity = random.choice(CARD_RARITIES)
    field, label, step, sense = random.choice(card_options(w))
    tier = CARD_TIER[rarity]
    if field == "uses_add":
        amount = max(1, round(step * tier))
        text_ = f"+{amount} {label}"
    else:
        amount = step * tier
        text_ = f"{'+' if sense > 0 else '-'}{amount * 100:.0f}% {label}"
    return Card(weapon_key, rarity, field, amount * sense, text_)

# Super meter. Fills from damage dealt and taken, then burns down over the
# super's duration - the bar doubles as the timer while it is running.
METER_MAX = 100.0

# Difficulty presets. "hard" is the AI tuning the game was built and balanced
# around; "normal" dials the same skill knob down 28% for a gentler match.
DIFFICULTIES = {"normal": round(0.78 * 0.72, 2), "hard": 0.78}
DIFFICULTY_ORDER = ["normal", "hard"]
SHIELD_DRAIN = 1.4          # super-clock multiplier while the shield is up

# ---------------------------------------------------------------- roster ----


@dataclass(frozen=True)
class Archetype:
    """One selectable character. `hp` and `attack` keep the original scale."""
    name: str
    hp: int
    speed: int
    attack: int
    hp_scale: float
    build: float                # body size multiplier - also the hitbox
    primary: tuple
    secondary: tuple
    title: str
    blurb: str
    knockback: float = 1.0      # multiplier on knockback taken
    armor: float = 1.0          # multiplier on incoming hit damage
    double_jump: bool = False
    # --- super ---
    # The base entries below describe the sorcerer build. A character whose
    # super leans on something a style does not own - Bob inflating shots
    # when a melee god has none to inflate - overrides itself per style in
    # `super_styles`. Anything left out there falls back to the base.
    super_name: str = "SUPER"
    super_blurb: str = ""
    super_time: float = 6.0
    super_kit: tuple = ()       # (key, value) pairs - see Fighter.boost()
    super_styles: dict = field(default_factory=dict)
    meter_dealt: float = 0.20   # meter per point of damage dealt
    meter_taken: float = 0.38   # meter per point of damage taken

    @property
    def boss_style(self):
        return BOSS_STYLES[self.name]

    def super_for(self, style_key):
        """Resolve the super this character runs under a given style."""
        v = self.super_styles.get(style_key, {})
        return (v.get("name", self.super_name),
                v.get("time", self.super_time),
                v.get("blurb", self.super_blurb),
                dict(v.get("kit", self.super_kit)))


ROSTER = [
    # Tuned by simulation - see the balance notes at the bottom of the file.
    Archetype(
        name="Andy", hp=100, speed=6, attack=11, hp_scale=3.35, build=1.0,
        primary=(86, 150, 232), secondary=(140, 226, 255),
        title="THE ALL-ROUNDER",
        blurb="no weakness, no gimmick",
        # Short but broad: every stat lifts at once and the shield comes out.
        # Holding the shield burns the clock, so 4s is plenty. Nothing here
        # assumes a projectile, so all three styles run the same idea - the
        # shield just parries a swing instead of reflecting a shot.
        # SURGE was the shortest super in the game and the shield ate the
        # clock at more than twice speed, so using it cost more than it gave.
        # Twice the duration, and holding the shield is no longer punitive.
        super_name="SURGE", super_time=8.0,
        super_blurb="every stat up + reflect shield",
        super_kit=(("damage", 1.12), ("move", 1.12), ("cooldown", 0.86),
                   ("armor", 0.92), ("shield", 1), ("lifesteal", 1)),
        super_styles={
            # A shield is worth more to a caster who can stand behind it than
            # to a gunslinger who has to keep moving, so the gun build takes
            # its share of SURGE in damage instead.
            "gun": {"blurb": "every stat up + reflect shield + lifesteal",
                    "kit": (("damage", 1.30), ("move", 1.12),
                            ("cooldown", 0.82), ("armor", 0.92),
                            ("shield", 1), ("lifesteal", 1))},
            # A reflect shield is a ranged answer to a ranged problem, and
            # Andy's melee build does not have a ranged problem - it has a
            # "cannot stay in contact" problem. So his melee SURGE drops the
            # shield entirely and buys him the thing he actually lacks: the
            # weight to plant his feet, and long enough to use it.
            "melee": {"time": 7.8, "blurb": "immovable, faster, hits harder, lifesteal",
                      "kit": (("damage", 1.48), ("move", 1.28),
                              ("cooldown", 0.72), ("armor", 0.78),
                              ("knockres", 0.12), ("lifesteal", 1))},
        },
        meter_dealt=0.20, meter_taken=0.38,
    ),
    Archetype(
        name="Bob", hp=140, speed=3, attack=8, hp_scale=2.55, build=1.10,
        primary=(206, 72, 72), secondary=(255, 168, 84),
        title="THE BULWARK",
        blurb="deepest health, shrugs off hits",
        knockback=0.42, armor=0.9,
        # Siege mode is "everything you throw gets bigger". `size` inflates a
        # projectile's radius AND a swing's arc, so the same idea lands for
        # every style - but a gunslinger firing four shots a second cannot
        # have 2.2x shots, and a melee god has almost nothing to inflate.
        # So: sorcerer gets the giant shells, the gun gets its reloads torn
        # out instead, and melee gets a wrecking-ball arc.
        # Siege is meant to feel like the round turning over. It now mends a
        # slab of health on activation and lifts attack, speed and toughness
        # alongside the shot size it always had.
        super_name="SIEGE", super_time=7.5,
        super_blurb="heals, giant shots, heavy damage",
        super_kit=(("damage", 1.69), ("move", 1.27), ("cooldown", 0.80),
                   ("size", 2.16), ("armor", 0.86), ("heal", 69)),
        super_styles={
            "gun": {"time": 6.5, "blurb": "heals, no reloads, wider spray",
                    "kit": (("damage", 1.55), ("move", 1.27),
                            ("cooldown", 0.78), ("size", 1.47),
                            ("armor", 0.86), ("heal", 61), ("nolimit", 1))},
            "melee": {"time": 7.0, "blurb": "heals, wrecking-ball reach",
                      "kit": (("damage", 1.59), ("move", 1.29),
                              ("cooldown", 0.77), ("size", 1.67),
                              ("armor", 0.84), ("heal", 69))},
        },
        meter_dealt=0.15, meter_taken=0.42,     # a tank charges by absorbing
    ),
    Archetype(
        name="Max", hp=75, speed=9, attack=12, hp_scale=2.95, build=0.90,
        primary=(126, 92, 214), secondary=(160, 255, 170),
        title="THE BLUR",
        blurb="double jump, hits hard",
        knockback=1.25, double_jump=True,
        # The longest super in the game: no single overwhelming perk, just a
        # smaller body, a third jump and a floor of 1 HP. That is style-blind
        # already - the only tuning needed is length, because a katana in
        # hyper mode converts immortality into damage far faster than a
        # fireball does.
        # Hyper mode now makes everything he throws hunt. A gunslinger firing
        # four times a second gets a gentler turn rate than a caster lobbing
        # one fireball; a melee god has nothing to home, so the homing is
        # applied to Max himself - every swing drags him onto the target.
        super_name="HYPER MODE", super_time=9.0,
        super_blurb="triple jump, tiny, homing shots, cannot die",
        super_kit=(("damage", 1.25), ("move", 1.24), ("cooldown", 0.80),
                   ("build", 0.70), ("airjumps", 2), ("hpfloor", 1),
                   ("homing", 5.0)),
        super_styles={
            "gun": {"time": 8.5, "blurb": "triple jump, tiny, every round seeks",
                    "kit": (("damage", 1.40), ("move", 1.24),
                            ("cooldown", 0.78), ("build", 0.70),
                            ("airjumps", 2), ("hpfloor", 1),
                            ("homing", 8.0))},
            "melee": {"time": 7.5, "blurb": "triple jump, tiny, swings that hunt",
                      "kit": (("damage", 1.45), ("move", 1.30),
                              ("cooldown", 0.80), ("build", 0.70),
                              ("airjumps", 2), ("hpfloor", 1),
                              ("homing", 5.0), ("lunge", 16.0))},
        },
        meter_dealt=0.30, meter_taken=0.24,     # charges by landing hits
    ),
]

BOSSES = [
    Archetype(
        name="Sensei", hp=150, speed=8, attack=12, hp_scale=2.20, build=1.02,
        primary=(60, 62, 84), secondary=(255, 132, 96),
        title="THE MASTER", blurb="every gap closes",
        knockback=0.62, armor=0.88,
        super_name="THOUSAND HANDS", super_time=6.0,
        super_blurb="flurry never stops, and he is faster",
        super_kit=(("damage", 1.2), ("move", 1.3), ("cooldown", 0.6),
                   ("nolimit", 1)),
        meter_dealt=0.22, meter_taken=0.30,
    ),
    Archetype(
        name="Steve", hp=170, speed=5, attack=12, hp_scale=3.05, build=1.06,
        primary=(78, 140, 96), secondary=(150, 214, 160),
        title="THE BUILDER", blurb="fights behind his own walls",
        knockback=0.5, armor=0.9,
        super_name="CREEPER", super_time=7.0,
        super_blurb="bigger blasts, walls on demand",
        super_kit=(("damage", 1.35), ("size", 1.5), ("cooldown", 0.62),
                   ("nolimit", 1)),
        meter_dealt=0.20, meter_taken=0.34,
    ),
]
# The style each boss fights in, kept beside the roster it belongs to.
BOSS_STYLES = {"Sensei": "sensei", "Steve": "steve"}


# ----------------------------------------------------------------- audio ----

SOUNDS = {}
RATE = 22050


def _render(samples, vol):
    buf = array("h")
    for s in samples:
        buf.append(int(max(-1.0, min(1.0, s * vol)) * 32767))
    return pygame.mixer.Sound(buffer=buf)


def _tone(freq, ms, vol=0.30, sweep=0.0, noise=0.0, harmonics=1, decay=1.6,
          wobble=0.0):
    """A single procedural voice - the workhorse behind most effects."""
    n = max(1, int(RATE * ms / 1000))
    out = []
    for i in range(n):
        p = i / n
        t = i / RATE
        f = freq * (1.0 + sweep * p) * (1.0 + wobble * math.sin(t * 42))
        s = 0.0
        for h in range(1, harmonics + 1):
            s += math.sin(2 * math.pi * f * h * t) / h
        if noise:
            s = s * (1 - noise) + random.uniform(-1, 1) * noise
        env = min(1.0, i / (0.008 * RATE + 1)) * (1.0 - p) ** decay
        out.append(s * env)
    return _render(out, vol)


def _chord(freqs, ms, vol=0.25, decay=1.8, sweep=0.0):
    n = max(1, int(RATE * ms / 1000))
    out = []
    for i in range(n):
        p = i / n
        t = i / RATE
        s = sum(math.sin(2 * math.pi * f * (1 + sweep * p) * t) for f in freqs)
        s /= len(freqs)
        env = min(1.0, i / (0.01 * RATE + 1)) * (1.0 - p) ** decay
        out.append(s * env)
    return _render(out, vol)


def _crackle(ms, vol=0.28, band=0.5, decay=2.0):
    """Filtered noise - ice shattering, impacts, footfalls."""
    n = max(1, int(RATE * ms / 1000))
    out = []
    prev = 0.0
    for i in range(n):
        p = i / n
        raw = random.uniform(-1, 1)
        prev = prev * band + raw * (1 - band)
        env = min(1.0, i / (0.004 * RATE + 1)) * (1.0 - p) ** decay
        out.append(prev * env)
    return _render(out, vol)


def build_audio():
    """Fill SOUNDS. Silently no-ops if this machine has no working mixer."""
    if not pygame.mixer.get_init():
        return
    try:
        SOUNDS.update({
            "fireball": _tone(210, 340, 0.26, sweep=-0.42, noise=0.36, harmonics=3),
            "ice": _tone(920, 240, 0.20, sweep=0.65, noise=0.10, harmonics=2),
            "bolt": _tone(1500, 210, 0.20, sweep=-0.75, noise=0.5),
            "hit": _tone(150, 170, 0.32, sweep=-0.5, noise=0.62),
            "bighit": _tone(96, 300, 0.38, sweep=-0.55, noise=0.5, harmonics=2),
            "melee": _tone(430, 120, 0.22, sweep=-0.6, noise=0.45),
            "strike": _tone(430, 120, 0.22, sweep=-0.6, noise=0.45),
            "pistol": _tone(760, 90, 0.19, sweep=-0.72, noise=0.55, decay=2.6),
            "shotgun": _tone(190, 260, 0.30, sweep=-0.5, noise=0.72, harmonics=2),
            "rocket": _tone(300, 420, 0.24, sweep=0.5, noise=0.55, harmonics=2,
                            decay=1.2),
            "explode": _tone(80, 460, 0.36, sweep=-0.6, noise=0.7, harmonics=3,
                             decay=1.3),
            "hatchet": _tone(560, 180, 0.20, sweep=-0.35, noise=0.3, wobble=0.5),
            "bat": _tone(240, 150, 0.26, sweep=-0.55, noise=0.5, harmonics=2),
            "katana": _tone(1250, 130, 0.20, sweep=-0.8, noise=0.22, harmonics=2,
                            decay=2.6),
            "whiff": _crackle(120, 0.13, band=0.75, decay=3.0),
            "jump": _tone(520, 130, 0.15, sweep=0.9),
            "land": _crackle(140, 0.20, band=0.86, decay=3.2),
            "step": _crackle(60, 0.07, band=0.9, decay=4.0),
            "freeze": _chord([880, 1320, 1760, 2640], 620, 0.24, decay=1.4),
            "shatter": _crackle(340, 0.26, band=0.35, decay=1.6),
            "stun": _tone(300, 260, 0.20, sweep=1.6, noise=0.2, wobble=0.4),
            "burn": _crackle(200, 0.11, band=0.55, decay=2.4),
            "ko": _tone(105, 780, 0.36, sweep=-0.45, noise=0.28, harmonics=3),
            "bell": _chord([523, 784, 1046], 700, 0.22, decay=1.2),
            "warn": _tone(880, 150, 0.18, decay=2.4),
            "select": _tone(660, 90, 0.17, sweep=0.5, harmonics=2),
            "confirm": _chord([523, 659, 784], 380, 0.24, decay=1.6),
            "super": _chord([196, 262, 330, 392, 523], 1100, 0.30, decay=0.8,
                            sweep=0.35),
            "superend": _chord([392, 330, 262], 500, 0.18, decay=1.6, sweep=-0.15),
            "shield": _tone(340, 200, 0.18, sweep=0.3, harmonics=4, decay=2.0),
            "reflect": _tone(1200, 260, 0.24, sweep=-0.5, harmonics=3, decay=1.4),
            "siege": _tone(90, 420, 0.30, sweep=-0.3, noise=0.4, harmonics=3),
            "win": _chord([523, 659, 784, 1046], 900, 0.26, decay=1.0, sweep=0.02),
            "lose": _chord([392, 466, 587], 900, 0.24, decay=1.0, sweep=-0.05),
        })
        # Rising chime per combo step.
        for i in range(6):
            SOUNDS[f"combo{i}"] = _tone(660 * (1.12 ** i), 130, 0.17,
                                        harmonics=2, decay=2.2)
    except pygame.error:
        SOUNDS.clear()


def play(name, volume=1.0):
    sound = SOUNDS.get(name)
    if sound is None:
        return
    sound.set_volume(max(0.0, min(1.0, volume)))
    sound.play()


# ------------------------------------------------------------- fx objects ----


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    color: tuple
    gravity: float = 0.12
    fade_to: tuple = None
    shape: str = "circle"

    def update(self, k):
        self.x += self.vx * k
        self.y += self.vy * k
        self.vy += self.gravity * k
        self.vx *= 1 - 0.03 * k
        self.life -= k / FPS

    def draw(self, surf):
        ratio = max(0.0, self.life / self.max_life)
        color = self.color
        if self.fade_to:
            color = tuple(int(c + (d - c) * (1 - ratio))
                          for c, d in zip(self.color, self.fade_to))
        r = max(1, int(self.size * ratio))
        if self.shape == "shard":
            pts = [(self.x, self.y - r * 1.6), (self.x + r, self.y),
                   (self.x, self.y + r * 1.6), (self.x - r, self.y)]
            pygame.draw.polygon(surf, color, pts)
        else:
            pygame.draw.circle(surf, color, (int(self.x), int(self.y)), r)


@dataclass
class Shockwave:
    """Expanding ring stamped on every solid connection."""
    x: float
    y: float
    color: tuple
    life: float = 0.34
    max_life: float = 0.34
    r0: float = 8
    r1: float = 74
    width: int = 5
    squash: float = 0.62

    def update(self, k):
        self.life -= k / FPS

    def draw(self, surf):
        p = 1 - max(0.0, self.life / self.max_life)
        r = self.r0 + (self.r1 - self.r0) * (p ** 0.55)
        w = max(1, int(self.width * (1 - p)))
        box = pygame.Rect(0, 0, r * 2, r * 2 * self.squash)
        box.center = (self.x, self.y)
        if box.width > 2 and box.height > 2:
            pygame.draw.ellipse(surf, self.color, box, w)


@dataclass
class Afterimage:
    """Ghost of a fast-moving fighter, drawn from a cached body surface."""
    surf: object
    x: float
    y: float
    life: float = 0.26
    max_life: float = 0.26

    def update(self, k):
        self.life -= k / FPS

    def draw(self, surf):
        ratio = max(0.0, self.life / self.max_life)
        ghost = self.surf.copy()
        ghost.set_alpha(int(120 * ratio))
        surf.blit(ghost, ghost.get_rect(center=(self.x, self.y)))


@dataclass
class FloatingText:
    x: float
    y: float
    text: str
    color: tuple
    life: float = 0.9
    max_life: float = 0.9
    size: int = 28
    vy: float = -1.5

    def update(self, k):
        self.y += self.vy * k
        self.vy += 0.045 * k
        self.life -= k / FPS


@dataclass
class Projectile:
    owner: object
    weapon: Weapon
    x: float
    y: float
    vx: float
    vy: float
    target: object = None       # what a homing shot chases
    volley: dict = None         # shared marker for one multi-pellet spray
    life: float = 2.6
    spin: float = 0.0
    scale: float = 1.0
    homing: float = -1.0        # -1 means "use the weapon's own rate"
    trail: list = field(default_factory=list)

    @property
    def turn_rate(self):
        return self.weapon.homing if self.homing < 0 else self.homing

    @property
    def radius(self):
        return self.weapon.radius * self.scale

    def steer(self, k):
        """Turn toward the target, but only so far per frame.

        That cap is the entire balance of the hatchet. It will chase you
        across the arena, and it will still sail past anyone who breaks its
        turn radius instead of backing away in a straight line.
        """
        t = self.target
        want = math.atan2(t.cy - self.y, t.x - self.x)
        now = math.atan2(self.vy, self.vx)
        diff = (want - now + math.pi) % math.tau - math.pi
        limit = math.radians(self.turn_rate) * k
        now += max(-limit, min(limit, diff))
        speed = math.hypot(self.vx, self.vy)
        self.vx = math.cos(now) * speed
        self.vy = math.sin(now) * speed

    def update(self, k):
        if self.weapon.drop:
            self.vy += self.weapon.drop * k        # arcing shot
        if self.turn_rate and self.target is not None and self.target.is_alive():
            self.steer(k)
        self.trail.append((self.x, self.y))
        if len(self.trail) > 10:
            self.trail.pop(0)
        self.x += self.vx * k
        self.y += self.vy * k
        self.spin += 0.25 * k
        self.life -= k / FPS

    def rect(self):
        r = self.radius
        return pygame.Rect(self.x - r, self.y - r, r * 2, r * 2)


@dataclass
class Wall:
    """Steve's cobblestone. Eats shots until it runs out of hit points."""
    x: float
    y: float
    owner: object
    hp: int = 3
    life: float = 9.0
    max_life: float = 9.0
    flash: float = 0.0

    def rect(self):
        return pygame.Rect(self.x - 26, self.y - 104, 52, 104)

    def update(self, k):
        self.life -= k / FPS
        self.flash = max(0.0, self.flash - k / FPS)


@dataclass
class Airdrop:
    """A supply crate: falls, lands, and waits to be walked into."""
    kind: str
    x: float
    y: float
    vy: float = 0.0
    landed: bool = False
    life: float = DROP_LIFE
    spin: float = 0.0
    flash: float = 0.0

    COLORS = {"health": ((120, 240, 150), (36, 120, 70)),
              "boost": ((255, 214, 110), (150, 96, 24)),
              "ghost": ((190, 200, 255), (74, 78, 140))}

    @property
    def core(self):
        return self.COLORS[self.kind][0]

    @property
    def shade(self):
        return self.COLORS[self.kind][1]

    def rect(self):
        return pygame.Rect(self.x - 22, self.y - 24, 44, 46)

    def update(self, k):
        self.spin += 0.02 * k
        self.flash = max(0.0, self.flash - k / FPS)
        if self.landed:
            self.life -= k / FPS
            return
        self.vy = min(DROP_FALL, self.vy + 0.05 * k)
        self.y += self.vy * k
        if self.y >= GROUND_Y - 12:
            self.y = GROUND_Y - 12
            self.landed = True
            self.flash = 0.4


@dataclass
class Cloud:
    """Splash-potion gas. Slows and burns whoever stands in it - including
    the fighter who threw it, which is the whole point of the weapon."""
    x: float
    y: float
    radius: float
    owner: object
    weapon: object
    life: float = 3.0
    max_life: float = 3.0
    tick: float = 0.0
    spin: float = 0.0

    def holds(self, f):
        return math.hypot(f.x - self.x, f.cy - self.y) < self.radius

    def update(self, k):
        """Spin only - Game.update_clouds owns the lifetime, because the
        dispersal stun has to fire on the exact frame the gas runs out."""
        self.spin += 0.012 * k


@dataclass
class Slash:
    """A melee arc. Tall enough to catch a crouching opponent."""
    owner: object
    facing: int
    weapon: Weapon
    life: float = 0.18
    max_life: float = 0.18
    hit: bool = False

    def span(self):
        """Arc scale: mostly the weapon, only a little the fighter."""
        build = 1 + (self.owner.build - 1) * REACH_BUILD
        return build * self.owner.boost("size")

    def rect(self):
        s = self.span()
        reach = self.owner.wstat(self.weapon.key, "reach")
        w, h = int(reach * s), int(self.weapon.lift * s)
        x = self.owner.x + (4 if self.facing > 0 else -w - 4)
        return pygame.Rect(x, self.owner.y - h, w, h)


# --------------------------------------------------------------- fighter ----


class Fighter:
    """A combatant: a character, a fighting style, a body and a stance."""

    def __init__(self, arch, style_key="sorcerer"):
        self.arch = arch
        self.name = arch.name
        self.style = STYLES[style_key]
        # HP is scaled up from the original values - a real-time fight needs far
        # more than the three or four exchanges the turn-based version ran on.
        self.max_hp = int(arch.hp * arch.hp_scale)
        self.hp = self.max_hp
        self.speed = arch.speed
        self.attack_damage = arch.attack
        self.primary = arch.primary
        self.secondary = arch.secondary
        self._build = arch.build
        self.knockback = arch.knockback
        self.armor = arch.armor
        self.double_jump = arch.double_jump

        # --- kit -----------------------------------------------------------
        self.kit = list(self.style.weapons)          # slots 1 / 2 / 3
        self.strike_key = self.style.strike_key      # what J swings
        keys = list(dict.fromkeys(self.kit + [self.strike_key]))
        self.cooldowns = {k: 0.0 for k in keys}      # weapon cooldown
        self.uses_left = {k: WEAPONS[k].uses for k in keys}   # usage cooldown
        self.window = {k: 0.0 for k in keys}
        self.lock = {k: 0.0 for k in keys}
        # Upgrade cards live here, per weapon, so a card bought for the bat
        # never quietly improves the potion as well.
        self.wmod = {k: {} for k in keys}

        self.move_speed = (2.9 + arch.speed * 0.28) * self.style.move
        self.x = WIDTH / 2
        self.y = GROUND_Y
        self.vx = 0.0
        self.vy = 0.0
        self.facing = 1
        self.on_ground = True
        self.jumps_left = 0

        self.crouch = 0.0            # smoothed 0..1
        self.want_crouch = False
        self.aim = (1.0, 0.0)        # unit vector the next shot leaves on
        self.buff = 0.0              # airdrop stat boost, seconds left
        self.invis = 0.0             # ghost potion, seconds left

        self.status = {"burn": 0.0, "slow": 0.0, "stun": 0.0, "freeze": 0.0}
        self.ice_hits = []
        self.burn_tick = 0.0
        self.hit_flash = 0.0
        self.cast_anim = 0.0
        self.swing_art = None        # which weapon the current animation is
        self.walk_phase = 0.0
        self.step_timer = 0.0
        self.anim_t = random.random() * 10
        self.hp_lag = float(self.hp)
        self.rounds_won = 0

        name, time_, blurb, kit = arch.super_for(style_key)
        self.super_name = name
        self.super_time = time_
        self.super_blurb = blurb
        self.super_kit = kit
        self.meter = 0.0
        self.super_timer = 0.0
        self.shielding = False
        self.shield_flash = 0.0
        self.aura_timer = 0.0
        self.combo = 0
        self.combo_timer = 0.0
        self.ghost_timer = 0.0

    # -- super -------------------------------------------------------------

    @property
    def in_super(self):
        return self.super_timer > 0

    def boost(self, key, default=1.0):
        """Look up a super perk, or the neutral value when not supered."""
        return self.super_kit.get(key, default) if self.in_super else default

    @property
    def build(self):
        return self._build * self.boost("build")

    @property
    def super_ready(self):
        return self.meter >= METER_MAX and not self.in_super

    def can_shield(self):
        return self.in_super and "shield" in self.super_kit

    def shield_rect(self):
        s = self.build
        w, h = int(30 * s), int(96 * s)
        x = self.x + (10 * s if self.facing > 0 else -w - 10 * s)
        return pygame.Rect(x, self.y - h - 4, w, h)

    def gain_meter(self, amount):
        if not self.in_super:
            self.meter = min(METER_MAX, self.meter + amount)

    def activate_super(self, game):
        if not self.super_ready or not self.can_act():
            return False
        self.super_timer = self.super_time
        self.meter = METER_MAX
        # Some kits come with a slab of health attached. Read straight from
        # the kit rather than through boost(), because this fires once on
        # activation instead of applying for the duration.
        mend = self.super_kit.get("heal", 0)
        if mend:
            healed = min(int(mend), self.max_hp - self.hp)
            if healed > 0:
                self.hp += healed
                game.texts.append(FloatingText(
                    self.x, self.y - self.height - 22, f"+{healed} HP",
                    (120, 240, 150), size=26, life=1.1, max_life=1.1))
        game.shake = max(game.shake, 16)
        game.hitstop = max(game.hitstop, 0.12)
        game.sky_flash = max(game.sky_flash, 0.6)
        game.super_flash = 0.8
        game.super_owner = self
        game.texts.append(FloatingText(self.x, self.y - self.height - 52,
                                       self.super_name, self.secondary,
                                       size=40, life=1.6, max_life=1.6))
        game.shockwaves.append(Shockwave(self.x, self.cy, self.secondary,
                                         r1=170, width=11, life=0.5,
                                         max_life=0.5, squash=1.0))
        game.shockwaves.append(Shockwave(self.x, self.cy, WHITE, r0=4, r1=110,
                                         width=5, life=0.34, max_life=0.34,
                                         squash=1.0))
        for _ in range(46):
            ang = random.uniform(0, math.tau)
            mag = random.uniform(2, 7)
            game.particles.append(Particle(
                self.x, self.cy, math.cos(ang) * mag, math.sin(ang) * mag,
                0.9, 0.9, 7, self.secondary, gravity=-0.04,
                fade_to=self.primary))
        play("super", 0.9)
        if "size" in self.super_kit:
            play("siege", 0.6)
        return True

    # -- geometry ----------------------------------------------------------

    def height_at(self, crouch):
        return 92 * self.build * (1 - CROUCH_SQUASH * crouch)

    @property
    def height(self):
        return self.height_at(self.crouch)

    def rect(self):
        w = 52 * self.build
        h = self.height
        return pygame.Rect(self.x - w / 2, self.y - h, w, h)

    @property
    def cx(self):
        return self.x

    @property
    def cy(self):
        return self.y - self.height * 0.5

    def aim_level(self):
        """Straight ahead - what everything except the player's cursor uses."""
        self.aim = (float(self.facing), 0.0)

    def set_aim(self, tx, ty):
        """Point the next shot at a world position, inside the aim arc.

        Worked out in a facing-relative frame so the clamp behaves the same
        pointing left as right; anything behind you snaps to straight ahead.
        """
        hx, hy = self.hand_pos()
        fx = (tx - hx) * self.facing
        fy = ty - hy
        if fx <= 0 and fy == 0:
            self.aim = (float(self.facing), 0.0)
            return
        ang = math.atan2(fy, max(fx, 1e-6))
        ang = max(-AIM_ARC, min(AIM_ARC, ang))
        self.aim = (math.cos(ang) * self.facing, math.sin(ang))

    def hand_pos(self):
        """Where shots leave from - drops to knee height in a crouch."""
        s = self.build
        squash = 1 - CROUCH_SQUASH * self.crouch
        return (self.x + self.facing * 31 * s, self.y - 68 * s * squash)

    # -- state -------------------------------------------------------------

    def is_alive(self):
        return self.hp > 0

    def reset(self, x, facing):
        self.hp = self.max_hp
        self.hp_lag = float(self.max_hp)
        self.x, self.y = x, GROUND_Y
        self.vx = self.vy = 0.0
        self.facing = facing
        self.on_ground = True
        self.jumps_left = 0
        self.crouch = 0.0
        self.want_crouch = False
        self.aim = (float(facing), 0.0)
        self.buff = 0.0
        self.invis = 0.0
        for key in self.cooldowns:
            self.cooldowns[key] = 0.0
            self.refill(key)
        self.status = {k: 0.0 for k in self.status}
        self.ice_hits.clear()
        self.hit_flash = 0.0
        self.cast_anim = 0.0
        self.combo = 0
        self.super_timer = 0.0      # meter itself carries across rounds
        self.shielding = False

    def is_ghost(self):
        return self.invis > 0

    def frozen(self):
        return self.status["freeze"] > 0

    def can_act(self):
        return (self.status["stun"] <= 0 and self.status["freeze"] <= 0
                and self.is_alive())

    def speed_factor(self):
        f = self.boost("move") * (BOOST_MOVE if self.buff > 0 else 1.0)
        if self.status["slow"] > 0:
            f *= SLOW_FACTOR
        f *= 1 - 0.62 * self.crouch
        if self.shielding:
            f *= 0.45                      # bracing behind the shield is slow
        return f

    # -- usage cooldown ----------------------------------------------------
    #
    # Distinct from the weapon cooldown above. A limited weapon opens a live
    # window on its first shot; when the window runs out - or the shots do -
    # it locks out entirely for `lockout` seconds.

    def wstat(self, key, field):
        """A weapon stat as THIS fighter has it, after any upgrade cards."""
        base = getattr(WEAPONS[key], field)
        mod = self.wmod.get(key, {})
        if field == "uses":
            return int(base + mod.get("uses_add", 0)) if base else base
        return base * mod.get(field, 1.0)

    def take_card(self, card):
        slot = self.wmod.setdefault(card.weapon, {})
        if card.field == "uses_add":
            slot["uses_add"] = slot.get("uses_add", 0) + card.amount
        else:
            slot[card.field] = slot.get(card.field, 1.0) * (1 + card.amount)
        self.refill(card.weapon)

    def refill(self, key):
        self.uses_left[key] = self.wstat(key, "uses")
        self.window[key] = 0.0
        self.lock[key] = 0.0

    def lock_out(self, key, game=None):
        w = WEAPONS[key]
        self.uses_left[key] = self.wstat(key, "uses")
        self.window[key] = 0.0
        self.lock[key] = self.wstat(key, "lockout") * self.boost("cooldown")
        if game is not None:
            game.texts.append(FloatingText(
                self.x, self.y - self.height - 26, f"{w.short.upper()} SPENT",
                (255, 150, 90), size=17, life=0.75, max_life=0.75))

    def ready(self, key):
        """Off weapon cooldown, not locked out, and free to act."""
        return (self.cooldowns.get(key, 0.0) <= 0
                and self.lock.get(key, 0.0) <= 0
                and self.can_act() and not self.shielding)

    def tick_usage(self, dt, game):
        if self.boost("nolimit", 0):
            # Bob's gun siege tears the reloads out for the duration.
            for key in self.lock:
                self.refill(key)
            return
        for key in list(self.window):
            if self.lock[key] > 0:
                self.lock[key] = max(0.0, self.lock[key] - dt)
            elif self.window[key] > 0:
                self.window[key] -= dt
                if self.window[key] <= 0:
                    self.lock_out(key, game)

    # -- actions -----------------------------------------------------------

    def set_crouch(self, flag):
        self.want_crouch = bool(flag) and self.on_ground and self.can_act()

    def jump(self, game=None):
        if not self.can_act():
            return False
        if self.on_ground:
            self.vy = JUMP_VELOCITY
            self.on_ground = False
            self.want_crouch = False
            self.jumps_left = int(self.boost("airjumps",
                                             1 if self.double_jump else 0))
            play("jump", 0.45)
            if game:
                game.spawn_burst(self.x, GROUND_Y, GROUND_TOP, 8, spread=2.2, size=4)
            return True
        if self.jumps_left > 0:
            self.jumps_left -= 1
            self.vy = JUMP_VELOCITY * 0.86
            play("jump", 0.35)
            if game:
                game.shockwaves.append(Shockwave(self.x, self.y - 20,
                                                 self.secondary, r1=44,
                                                 width=3, max_life=0.28,
                                                 life=0.28))
                game.spawn_burst(self.x, self.y - 10, self.secondary, 10,
                                 spread=2.4, size=4)
            return True
        return False

    def roll_damage(self, multiplier):
        """The original formula, with the flat bonus tied to the multiplier.

        A pistol firing four times a second cannot carry the same flat +2..4
        a fireball does - the bonus would be most of its damage, and every
        character would hit for near enough the same number. Scaling it only
        below 1.0x leaves every original spell exactly as it was.
        """
        variety = random.randint(2, 4) * min(1.0, multiplier)
        gain = self.boost("damage") * (BOOST_DAMAGE if self.buff > 0 else 1.0)
        return max(1, round(self.attack_damage * gain * multiplier + variety))

    def use(self, key, game):
        """Fire or swing slot `key`, paying both kinds of cooldown."""
        w = WEAPONS[key]
        if not self.ready(key):
            return False
        free = bool(self.boost("nolimit", 0))
        self.cooldowns[key] = self.wstat(key, "cooldown") * self.boost("cooldown")
        if w.limited and not free:
            if w.window and self.window[key] <= 0:
                self.window[key] = self.wstat(key, "window")
            if w.uses:
                self.uses_left[key] -= 1
        if w.kind == "swing":
            self.do_swing(w, game)
        elif w.kind == "block":
            self.do_block(w, game)
        else:
            self.do_shoot(w, game)
        if w.limited and not free and w.uses and self.uses_left[key] <= 0:
            self.lock_out(key, game)
        return True

    def seek(self, w):
        """This shot's turn rate: the weapon's, unless a super overrides it.

        HYPER MODE makes everything Max throws chase - a straight-flying
        fireball becomes something you have to break line of sight from.
        """
        own = self.wstat(w.key, "homing")
        hyper = self.boost("homing", 0.0)
        return max(own, hyper) if hyper else own

    def do_shoot(self, w, game):
        self.cast_anim = 0.30
        self.swing_art = None
        hx, hy = self.hand_pos()
        scale = self.boost("size")
        speed = self.wstat(w.key, "speed")
        # One shared marker per spray, so four pellets do not read as a
        # four-hit combo or stack four screen shakes.
        volley = {"hit": False} if w.pellets > 1 else None
        target = game.other(self)
        ax, ay = self.aim
        for i in range(w.pellets):
            # Spread fans out perpendicular to wherever the shot is aimed.
            off = (i - (w.pellets - 1) / 2) * w.spread
            game.projectiles.append(Projectile(
                self, w, hx, hy,
                speed * ax - off * ay, speed * ay + off * ax,
                target=target, volley=volley, life=w.life, scale=scale,
                homing=self.seek(w)))
        game.spawn_burst(hx, hy, w.glow, 14, spread=3.0, size=5)
        game.shockwaves.append(Shockwave(hx, hy, w.glow, r1=40, width=3,
                                         life=0.26, max_life=0.26, squash=1.0))
        play(w.key, 0.7)

    def do_block(self, w, game):
        """Drop a wall a little way in front, between us and them."""
        self.cast_anim = 0.26
        x = self.x + self.facing * 96
        x = max(WALL_MARGIN + 30, min(WIDTH - WALL_MARGIN - 30, x))
        game.walls.append(Wall(x, GROUND_Y, self))
        game.spawn_burst(x, GROUND_Y - 50, w.glow, 18, spread=3.5, size=6)
        game.shockwaves.append(Shockwave(x, GROUND_Y - 50, w.core, r1=70,
                                         width=4, life=0.3, max_life=0.3))
        play("land", 0.7)

    def do_swing(self, w, game):
        self.cast_anim = w.swing
        self.swing_art = w.art
        # A bat cannot home, so hyper mode homes the fighter instead: every
        # swing drags Max onto the target. Same idea, applied to the body.
        pull = self.boost("lunge", 0.0)
        if pull:
            t = game.other(self)
            if t is not None and t.is_alive():
                dx = t.x - self.x
                gap = abs(dx) - w.reach * 0.55
                if gap > 0:
                    self.vx += math.copysign(min(pull, gap * 0.22), dx)
                    game.ghosts.append(Afterimage(body_surface(self, game.t),
                                                  self.x, self.y - 95 * self.build + 20))
        game.slashes.append(Slash(self, self.facing, w, life=w.swing,
                                  max_life=w.swing))
        play(w.key, 0.5)

    def strike(self, game):
        """The J button. A melee god swings their bat; everyone else jabs."""
        return self.use(self.strike_key, game)

    def register_hit(self, game):
        """Attacker-side combo bookkeeping."""
        self.combo = self.combo + 1 if self.combo_timer > 0 else 1
        self.combo_timer = COMBO_WINDOW
        if self.combo >= 2:
            game.combo_owner = self
            game.combo_flash = 0.9
            play(f"combo{min(5, self.combo - 2)}", 0.5)

    def take_damage(self, amount, direction, game, label=None, knock=1.0,
                    quiet=False):
        if not self.is_alive():
            return
        amount = max(1, round(amount * self.armor * self.style.armor
                              * self.boost("armor")))
        floor = 1 if self.boost("hpfloor", 0) else 0
        self.hp = max(floor, self.hp - amount)
        self.gain_meter(amount * self.arch.meter_taken)
        self.hit_flash = 0.2
        self.vx += (direction * 3.4 * self.knockback * self.style.knockback
                    * self.boost("knockres") * knock)
        if quiet:
            # One pellet out of a spray: take the damage, skip the fanfare.
            game.texts.append(FloatingText(
                self.x + random.uniform(-14, 14), self.y - self.height - 8,
                str(amount), WHITE, size=19, life=0.5, max_life=0.5))
            game.spawn_burst(self.x, self.cy, self.secondary, 5, spread=3, size=4)
            game.shake = max(game.shake, 3)
            play("hit", 0.28)
            return
        if self.on_ground and amount > 22 and self.knockback > 0.6 and knock >= 1:
            self.vy = -4.0
            self.on_ground = False
        color = CRIT if amount >= 30 else WHITE
        game.texts.append(FloatingText(self.x, self.y - self.height - 14,
                                       label or str(amount), color,
                                       size=34 if amount >= 30 else 26))
        game.spawn_burst(self.x, self.cy, self.secondary, 18, spread=4.5, size=6)
        game.shockwaves.append(Shockwave(self.x, self.cy, WHITE,
                                         r1=54 + amount, width=4))
        game.shake = max(game.shake, 5 + min(10, amount * 0.24))
        if amount >= 26:
            game.hitstop = max(game.hitstop, 0.07)
            play("bighit", 0.6)
        else:
            play("hit", 0.55)

    def leech(self, damage, game):
        """SURGE lifesteal: capped per hit, so volume is what heals - not
        the size of any one hit. Only fires while lifesteal is active in
        the current super, and only on damage actually dealt to a foe."""
        share = self.boost("lifesteal", 0)
        if not share or not self.is_alive():
            return
        healed = min(max(1, round(min(LIFESTEAL_CAP, damage * LIFESTEAL_PCT))),
                     self.max_hp - self.hp)
        if healed <= 0:
            return
        self.hp += healed
        game.texts.append(FloatingText(
            self.x + random.uniform(-10, 10), self.y - self.height - 18,
            f"+{healed}", (255, 110, 150), size=17, life=0.55, max_life=0.55))

    def apply_status(self, effect, duration):
        self.status[effect] = max(self.status[effect], duration)

    def register_ice_hit(self, game):
        """Three ice hits inside FREEZE_WINDOW lock the target solid."""
        self.ice_hits = [t for t in self.ice_hits if game.t - t < FREEZE_WINDOW]
        self.ice_hits.append(game.t)
        if len(self.ice_hits) >= FREEZE_HITS:
            self.ice_hits.clear()
            self.apply_status("freeze", FREEZE_SECONDS)
            self.status["slow"] = 0.0
            self.vx = 0.0
            self.want_crouch = False
            game.freeze_flash = 0.5
            game.shake = max(game.shake, 12)
            game.texts.append(FloatingText(self.x, self.y - self.height - 44,
                                           "FROZEN!", (200, 245, 255),
                                           size=32, life=1.2, max_life=1.2))
            game.shockwaves.append(Shockwave(self.x, self.cy, (190, 240, 255),
                                             r1=120, width=6, life=0.5,
                                             max_life=0.5, squash=1.0))
            for _ in range(30):
                ang = random.uniform(0, math.tau)
                game.particles.append(Particle(
                    self.x + math.cos(ang) * 20, self.cy + math.sin(ang) * 26,
                    math.cos(ang) * 3.4, math.sin(ang) * 3.4 - 1,
                    0.7, 0.7, 6, (215, 248, 255), gravity=0.16,
                    fade_to=(90, 150, 200), shape="shard"))
            play("freeze", 0.85)
        else:
            self.apply_status("slow", SLOW_SECONDS)

    # -- per-frame ---------------------------------------------------------

    def update(self, dt, k, game):
        self.anim_t += dt
        for key in self.cooldowns:
            self.cooldowns[key] = max(0.0, self.cooldowns[key] - dt)
        self.tick_usage(dt, game)
        self.cast_anim = max(0.0, self.cast_anim - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.buff = max(0.0, self.buff - dt)
        self.invis = max(0.0, self.invis - dt)
        self.combo_timer = max(0.0, self.combo_timer - dt)
        if self.combo_timer <= 0:
            self.combo = 0

        if self.in_super:
            # Blocking is not free: the shield eats the super clock.
            drain = dt * (SHIELD_DRAIN if self.shielding else 1.0)
            self.super_timer = max(0.0, self.super_timer - drain)
            self.meter = METER_MAX * (self.super_timer / self.super_time)
            self.aura_timer -= dt
            if self.aura_timer <= 0:
                self.aura_timer = 0.03
                ang = random.uniform(0, math.tau)
                game.particles.append(Particle(
                    self.x + math.cos(ang) * 22 * self.build,
                    self.cy + math.sin(ang) * 34 * self.build,
                    -self.vx * 0.2, random.uniform(-1.4, -0.4),
                    0.5, 0.5, 5, self.secondary, gravity=-0.05,
                    fade_to=self.primary))
            if not self.in_super:
                self.meter = 0.0
                self.shielding = False
                play("superend", 0.5)
        if not self.can_shield():
            self.shielding = False
        self.shield_flash = max(0.0, self.shield_flash - dt)

        was_frozen = self.frozen()
        for effect in self.status:
            self.status[effect] = max(0.0, self.status[effect] - dt)
        if was_frozen and not self.frozen():
            play("shatter", 0.6)
            game.shake = max(game.shake, 7)
            for _ in range(22):
                ang = random.uniform(0, math.tau)
                game.particles.append(Particle(
                    self.x, self.cy, math.cos(ang) * 4, math.sin(ang) * 4 - 1.5,
                    0.6, 0.6, 5, (220, 250, 255), gravity=0.2,
                    fade_to=(70, 120, 170), shape="shard"))

        # Burn: steady damage over time, with embers.
        if self.status["burn"] > 0:
            self.burn_tick -= dt
            if self.burn_tick <= 0:
                self.burn_tick = BURN_TICK
                floor = 1 if self.boost("hpfloor", 0) else 0
                self.hp = max(floor, self.hp - BURN_DAMAGE)
                self.gain_meter(BURN_DAMAGE * self.arch.meter_taken)
                game.texts.append(FloatingText(
                    self.x + random.uniform(-12, 12), self.y - self.height + 6,
                    str(BURN_DAMAGE), (255, 150, 60), size=20, life=0.6,
                    max_life=0.6))
                if random.random() < 0.5:
                    play("burn", 0.25)
            for _ in range(2):
                if random.random() < 0.5:
                    game.particles.append(Particle(
                        self.x + random.uniform(-16, 16),
                        self.y - random.uniform(6, self.height),
                        random.uniform(-0.35, 0.35), random.uniform(-1.8, -0.7),
                        0.55, 0.55, 5, (255, 180, 70), gravity=-0.03,
                        fade_to=(120, 30, 10)))
        else:
            self.burn_tick = 0.0

        if self.status["slow"] > 0 and random.random() < 0.25:
            game.particles.append(Particle(
                self.x + random.uniform(-18, 18),
                self.y - random.uniform(0, self.height),
                random.uniform(-0.4, 0.4), random.uniform(-0.4, 0.4),
                0.6, 0.6, 3, (150, 225, 255), gravity=0.01))

        if self.frozen():
            self.vx *= 1 - 0.4 * k
            self.want_crouch = False
            if random.random() < 0.3:
                game.particles.append(Particle(
                    self.x + random.uniform(-20, 20),
                    self.y - random.uniform(0, self.height),
                    0, random.uniform(-0.3, 0.3), 0.5, 0.5, 3,
                    (200, 240, 255), gravity=0.02))

        # Stance blending.
        target = 1.0 if (self.want_crouch and self.on_ground and self.can_act()) else 0.0
        self.crouch += (target - self.crouch) * min(1.0, 12.0 * dt)

        # Physics.
        self.x += self.vx * k
        self.vx *= 1 - 0.16 * k
        if abs(self.vx) < 0.05:
            self.vx = 0.0
        self.y += self.vy * k
        if not self.on_ground:
            self.vy += GRAVITY * k
        if self.y >= GROUND_Y:
            if not self.on_ground and self.vy > 3:
                game.spawn_burst(self.x, GROUND_Y, GROUND_TOP, 10, spread=2.8, size=5)
                game.shockwaves.append(Shockwave(self.x, GROUND_Y, (150, 130, 150),
                                                 r1=60, width=3, life=0.26,
                                                 max_life=0.26))
                play("land", 0.35)
            self.y = GROUND_Y
            self.vy = 0.0
            self.on_ground = True
            self.jumps_left = 0
        self.x = max(WALL_MARGIN, min(WIDTH - WALL_MARGIN, self.x))

        # Footfalls and dust while running.
        if abs(self.vx) > 0.4 and self.on_ground:
            self.walk_phase += 0.28 * k * (abs(self.vx) / 4)
            self.step_timer -= dt
            if self.step_timer <= 0:
                self.step_timer = 0.26
                play("step", 0.2)
                game.particles.append(Particle(
                    self.x - self.facing * 10, GROUND_Y - 2,
                    -self.facing * random.uniform(0.3, 1.0), -random.uniform(0.2, 0.8),
                    0.4, 0.4, 4, (120, 100, 120), gravity=0.06))
        else:
            self.walk_phase *= 1 - 0.15 * k

        self.hp_lag += (self.hp - self.hp_lag) * min(1.0, 4.0 * dt)

    def walk(self, direction, k):
        if not self.can_act():
            return
        limit = self.move_speed * self.speed_factor()
        self.vx += direction * self.move_speed * 0.55 * self.speed_factor() * k
        self.vx = max(-limit, min(limit, self.vx))


# ------------------------------------------------------------------- ai ----


class Brain:
    """Opponent controller. Reads stance the same way a player has to."""

    # Where each style wants to stand. A melee god that keeps its distance
    # is a melee god that does nothing, so its band sits on top of you.
    BANDS = {"sorcerer": (150, 400), "gun": (130, 400), "melee": (40, 150)}

    def __init__(self, fighter, target, skill=0.78):
        self.f = fighter
        self.target = target
        self.skill = skill
        self.think = 0.0
        self.intent = "hold"
        # A style built on swings has to stand inside its own reach. Reading
        # the band off a fixed table instead parks it 190px away swinging at
        # air, and quietly hands the matchup to whoever has the longest arms.
        swings = [WEAPONS[k] for k in fighter.kit if WEAPONS[k].kind == "swing"]
        if swings:
            span = max(w.reach for w in swings) * fighter.build
            self.band = (span * 0.35, span * 0.92)
            self.slack = (12, 34)       # close early, back off late
        else:
            self.band = self.BANDS[fighter.style.key]
            self.slack = (40, 60)
        self.want_range = sum(self.band) / 2
        self.react = 0.0
        self.crouch_hold = 0.0
        self.rush = 0.0
        self.lost = 0.0
        self.seen_x = fighter.x

    # Would a level shot leaving our hand right now connect? The cursor is
    # the player's advantage; a brain still has to line the shot up with its
    # stance, which is what keeps crouching and jumping worth doing.
    def lined_up(self, w):
        hy = self.f.hand_pos()[1]
        tr = self.target.rect()
        return tr.top - w.radius < hy < tr.bottom

    def incoming(self, game):
        """Nearest threat: (hits_us_standing, hits_us_crouched, distance).

        Shots are aimed now, so reading the height they left at is not enough
        - this walks each one forward to our own x and asks where it will
        actually be when it arrives.
        """
        f = self.f
        best = None
        for p in game.projectiles:
            if p.owner is f:
                continue
            dx = p.x - f.x
            if dx * p.vx > 0:                      # travelling away
                continue
            dist = abs(dx)
            if dist > 320 or abs(p.vx) < 0.01:
                continue
            r = p.radius
            yhit = p.y + p.vy * (dist / abs(p.vx))
            stand_top = f.y - f.height_at(0.0)
            crouch_top = f.y - f.height_at(1.0)
            # A homing shot or a blast radius cannot be ducked, so treat both
            # as a threat in either stance - the answer is to move, not squat.
            unduckable = bool(p.turn_rate or p.weapon.splash)
            hits_stand = unduckable or stand_top - r < yhit < f.y
            hits_crouch = unduckable or crouch_top - r < yhit < f.y
            if best is None or dist < best[2]:
                best = (hits_stand, hits_crouch, dist)
        return best

    def options(self, dist):
        """Every slot that could land right now."""
        f, t = self.f, self.target
        out = []
        for key in f.kit:
            w = WEAPONS[key]
            if not f.ready(key):
                continue
            if w.kind == "swing":
                span = w.reach * (1 + (f.build - 1) * REACH_BUILD) * f.boost("size")
                if dist <= span * 1.02 and abs(t.y - f.y) < 76:
                    out.append(key)
            else:
                lo, hi = w.ideal_range
                if not lo <= dist <= hi:
                    continue
                # Throwing a splash potion at your own feet is a way to lose
                # a round, so keep clear of your own blast radius.
                if w.selfharm and dist < w.splash * 1.25:
                    continue
                # A spray, a homing throw and a blast all forgive bad aim.
                if w.homing or w.pellets > 1 or w.splash or self.lined_up(w):
                    out.append(key)
        return out

    def wants_drop(self, game):
        """The nearest landed crate we could plausibly reach first."""
        f, t = self.f, self.target
        best = None
        for d in game.drops:
            if not d.landed or d.life < 1.0:
                continue
            mine = abs(d.x - f.x)
            if mine > 470 or mine > abs(d.x - t.x) + 130 or mine < 30:
                continue
            if best is None or mine < abs(best.x - f.x):
                best = d
        return best

    def choose(self, ready):
        """Pick a slot: spend an open window first, else hit hardest."""
        f = self.f
        live = [k for k in ready if f.window[k] > 0]
        if live and random.random() < 0.8:
            return live[0]          # use-it-or-lose-it, the clock is running
        if "ice" in ready and len(self.target.ice_hits) >= FREEZE_HITS - 1:
            return "ice"            # one hit from a freeze
        if random.random() < 0.35 + 0.45 * self.skill:
            return max(ready, key=lambda k: WEAPONS[k].multiplier)
        return random.choice(ready)

    def update(self, dt, k, game):
        f, t = self.f, self.target
        if not f.can_act() or not t.is_alive():
            return

        # An invisible opponent is tracked from the last place we saw them,
        # so a ghost potion buys real distance rather than just a visual.
        if t.is_ghost():
            self.lost += dt
        else:
            self.lost = 0.0
            self.seen_x = t.x
        tx = self.seen_x if self.lost > 0.3 else t.x
        dx = tx - f.x
        dist = abs(dx)
        f.facing = 1 if dx >= 0 else -1
        self.crouch_hold = max(0.0, self.crouch_hold - dt)
        self.rush = max(0.0, self.rush - dt)
        melee_style = f.style.key == "melee"

        # --- super: spend it once it is charged ---------------------------
        if f.super_ready and random.random() < 0.035 * (1 + self.skill):
            f.activate_super(game)

        # --- stance: dodging comes first ---------------------------------
        threat = self.incoming(game)

        # A shield beats ducking, so use it when one is available.
        if f.can_shield():
            f.shielding = bool(threat and threat[2] < 210
                               and (threat[0] or threat[1]))
        if f.shielding:
            self.crouch_hold = 0.0
            f.set_crouch(False)
            if dist > 150:
                f.walk(f.facing, k)
            return

        crouching = False
        if threat and threat[2] < 230 and random.random() < 0.5 + 0.5 * self.skill:
            hits_stand, hits_crouch, _ = threat
            if hits_crouch and f.on_ground:
                f.jump(game)                        # low shot: go over it
            elif hits_stand:
                crouching = True                    # high shot: duck under it
                self.crouch_hold = 0.32
        if self.crouch_hold > 0:
            crouching = True

        # --- stance: line up our own shots -------------------------------
        # Crouching to fire low is a caster's trick. A melee god has nothing
        # to line up and simply wants to be standing on top of you.
        if melee_style:
            crouching = False
            if dist > self.band[1]:
                self.rush = 0.6
        elif not crouching and t.crouch > 0.6 and f.on_ground and self.rush <= 0:
            if random.random() < 0.5:
                crouching = True                    # crouch and fire low
            else:
                self.rush = 1.1                     # or charge in for melee
        f.set_crouch(crouching)

        # --- movement -----------------------------------------------------
        self.think -= dt
        if self.think <= 0:
            self.think = random.uniform(0.22, 0.5)
            self.want_range = random.uniform(*self.band)
            near, far = self.slack
            if dist > self.want_range + near:
                self.intent = "approach"
            elif dist < self.want_range - far:
                self.intent = "retreat"
            else:
                self.intent = random.choice(["hold", "hold", "approach"])
        if self.rush > 0:
            self.intent = "approach"
        grab = self.wants_drop(game)
        if grab is not None:
            # A crate is worth breaking off the fight for.
            f.set_crouch(False)
            f.walk(1 if grab.x > f.x else -1, k)
        elif self.intent == "approach":
            f.walk(f.facing, k)
        elif self.intent == "retreat":
            f.walk(-f.facing, k)

        # --- attacks ------------------------------------------------------
        # Ranged styles keep the universal jab for anyone who gets inside.
        # A melee god's J is their bat, so it goes through the slot logic.
        if not melee_style and dist < 70 * f.build and abs(t.y - f.y) < 70:
            f.strike(game)

        self.react -= dt
        if self.react <= 0:
            self.react = random.uniform(0.12, 0.4) * (2.0 - self.skill)
            ready = self.options(dist)
            sighted = 0.35 if self.lost > 0.3 else 1.0
            if ready and random.random() < (0.55 + 0.4 * self.skill) * sighted:
                f.aim_level()
                f.use(self.choose(ready), game)


class BossBrain(Brain):
    """A boss plays the same game with two extra verbs.

    Sensei can close a gap instantly, which is the answer to being kited.
    Steve puts a wall up when he wants the trade to stop. Neither is on any
    style card, so neither can be learned by copying him.
    """

    BANDS = dict(Brain.BANDS, sensei=(40, 170), steve=(200, 430))

    def __init__(self, fighter, target, skill=0.78):
        super().__init__(fighter, target, skill)
        self.band = self.BANDS[fighter.style.key]
        self.want_range = sum(self.band) / 2
        self.special = random.uniform(1.6, 3.0)

    def dash(self, game):
        """Sensei's step-in: cover the gap and arrive already swinging."""
        f, t = self.f, self.target
        f.facing = 1 if t.x >= f.x else -1
        for i in range(6):
            ghost = body_surface(f, game.t)
            game.ghosts.append(Afterimage(
                ghost, f.x + f.facing * i * 22, f.y - 95 * f.build + 20))
        f.x += f.facing * min(240, max(0, abs(t.x - f.x) - 70))
        f.x = max(WALL_MARGIN, min(WIDTH - WALL_MARGIN, f.x))
        f.vx = f.facing * 3.0
        game.shockwaves.append(Shockwave(f.x, f.cy, f.secondary, r1=90,
                                         width=5, life=0.3, max_life=0.3))
        game.spawn_burst(f.x, f.cy, f.secondary, 22, spread=4.5, size=6)
        play("jump", 0.6)

    def update(self, dt, k, game):
        f, t = self.f, self.target
        if not f.can_act() or not t.is_alive():
            return
        self.special -= dt
        if self.special <= 0:
            self.special = random.uniform(2.6, 4.6) * (2.0 - self.skill)
            gap = abs(t.x - f.x)
            if f.style.key == "sensei" and gap > 190:
                self.dash(game)
            elif f.style.key == "steve" and gap < 260 and f.ready("block"):
                f.aim_level()
                f.use("block", game)
        super().update(dt, k, game)


# -------------------------------------------------------------- art bits ----

FONTS = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in FONTS:
        FONTS[key] = pygame.font.SysFont("arialroundedmtbold,arial,helvetica",
                                         size, bold=bold)
    return FONTS[key]


def text(surf, message, pos, size=24, color=WHITE, bold=False,
         center=False, shadow=True):
    f = font(size, bold)
    if shadow:
        s = f.render(message, True, (0, 0, 0))
        r = s.get_rect(center=(pos[0] + 2, pos[1] + 2)) if center else \
            s.get_rect(topleft=(pos[0] + 2, pos[1] + 2))
        surf.blit(s, r)
    img = f.render(message, True, color)
    rect = img.get_rect(center=pos) if center else img.get_rect(topleft=pos)
    surf.blit(img, rect)
    return rect


def glow_circle(surf, center, radius, color, layers=6, strength=0.85):
    """Soft additive glow: concentric discs that brighten toward the middle.

    The colours are pre-multiplied and blitted with BLEND_RGB_ADD - blending
    RGBA would add the full colour on every pixel and paint a solid blob.
    """
    r0 = max(2, int(radius))
    g = pygame.Surface((r0 * 2 + 2, r0 * 2 + 2), pygame.SRCALPHA)
    for i in range(layers, 0, -1):
        f = i / layers
        b = strength * (1.05 - f) ** 2
        c = tuple(min(255, int(ch * b)) for ch in color)
        pygame.draw.circle(g, (*c, 255), (r0 + 1, r0 + 1), max(1, int(r0 * f)))
    surf.blit(g, (center[0] - r0 - 1, center[1] - r0 - 1),
              special_flags=pygame.BLEND_RGB_ADD)


def build_background():
    """Pre-render the static arena so only the live bits cost anything."""
    bg = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / HEIGHT
        color = tuple(int(a + (b - a) * t) for a, b in zip(SKY_TOP, SKY_BOTTOM))
        pygame.draw.line(bg, color, (0, y), (WIDTH, y))

    glow_circle(bg, (790, 118), 96, (120, 104, 92), layers=7, strength=0.6)
    pygame.draw.circle(bg, (250, 240, 220), (790, 118), 44)
    pygame.draw.circle(bg, (232, 220, 202), (776, 106), 8)
    pygame.draw.circle(bg, (232, 220, 202), (806, 136), 5)
    pygame.draw.circle(bg, (232, 220, 202), (798, 96), 4)

    for _ in range(110):
        x, y = random.randint(0, WIDTH), random.randint(0, 320)
        b = random.randint(120, 235)
        pygame.draw.circle(bg, (b, b, min(255, b + 18)), (x, y),
                           random.choice([1, 1, 1, 2]))

    def ridge(color, base, amp, step, seed):
        rng = random.Random(seed)
        pts = [(0, HEIGHT)]
        x = 0
        while x <= WIDTH:
            pts.append((x, base + rng.randint(-amp, amp)))
            x += step
        pts.append((WIDTH, HEIGHT))
        pygame.draw.polygon(bg, color, pts)

    ridge((24, 21, 44), 300, 54, 110, 13)
    ridge(MOUNTAIN_1, 336, 46, 90, 7)
    ridge(MOUNTAIN_2, 388, 30, 70, 3)

    # Distant spires poking out of the far ridge.
    for sx, sh in ((180, 96), (250, 62), (860, 78), (930, 54)):
        pygame.draw.polygon(bg, (34, 28, 54), [
            (sx - 12, 392), (sx, 392 - sh), (sx + 12, 392)])

    pygame.draw.rect(bg, GROUND_TOP, (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))
    pygame.draw.rect(bg, GROUND_LOW, (0, GROUND_Y + 16, WIDTH, HEIGHT - GROUND_Y))
    pygame.draw.line(bg, (120, 96, 130), (0, GROUND_Y), (WIDTH, GROUND_Y), 3)
    for i in range(30):
        x = random.randint(0, WIDTH)
        pygame.draw.line(bg, (16, 12, 22), (x, GROUND_Y + 18),
                         (x + random.randint(-14, 14), HEIGHT), 2)
    for i in range(0, WIDTH, 64):
        pygame.draw.line(bg, (74, 58, 84), (i, GROUND_Y + 4), (i + 10, GROUND_Y + 4), 6)

    pygame.draw.ellipse(bg, (96, 74, 118), (WIDTH // 2 - 200, GROUND_Y + 6, 400, 40), 2)
    pygame.draw.ellipse(bg, (72, 56, 92), (WIDTH // 2 - 150, GROUND_Y + 14, 300, 26), 2)

    for px in (70, WIDTH - 70):
        pygame.draw.rect(bg, (38, 30, 50), (px - 26, 250, 52, GROUND_Y - 250))
        pygame.draw.rect(bg, (54, 42, 70), (px - 26, 250, 12, GROUND_Y - 250))
        pygame.draw.rect(bg, (46, 36, 60), (px - 34, 236, 68, 20), border_radius=4)
    return bg


def draw_torch_flame(surf, x, y, t, seed):
    flicker = math.sin(t * 9 + seed) * 0.5 + math.sin(t * 21 + seed * 2) * 0.5
    h = 26 + flicker * 6
    glow_circle(surf, (x, y - 8), 30, (255, 150, 50), layers=5)
    pygame.draw.polygon(surf, (255, 140, 40), [
        (x - 10, y), (x, y - h), (x + 10, y), (x, y - 6)])
    pygame.draw.polygon(surf, (255, 220, 120), [
        (x - 5, y), (x + flicker * 2, y - h * 0.6), (x + 5, y)])


def draw_body(surf, f, t, fx, feet, shadow=True):
    """Draw a fighter from primitives at an arbitrary spot on any surface."""
    flash = f.hit_flash > 0 and int(f.hit_flash * 40) % 2 == 0
    # Flash bright but keep the character's accent, so a clinch stays readable.
    body = tuple(min(255, int(c * 0.3 + 200)) for c in f.primary) if flash \
        else f.primary
    trim = f.secondary
    S = f.build
    face = f.facing
    c = f.crouch
    vs = 1 - CROUCH_SQUASH * c

    airborne = not f.on_ground
    bob = 0 if airborne else math.sin(f.anim_t * 2.4) * 1.9
    swing = math.sin(f.walk_phase) * (16 if not airborne else 7) * S

    hip = feet - 40 * S * vs + bob
    shoulder = feet - 71 * S * vs + bob
    head_y = feet - 85 * S * vs + bob
    lean = face * 5 * c * S

    if shadow:
        lift = max(0.0, (GROUND_Y - feet) / 120)
        sh = pygame.Surface((int(82 * S), 22), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, int(115 * max(0.15, 1 - lift * 0.7))),
                            (0, 0, int(82 * S), 22))
        sh = pygame.transform.smoothscale(
            sh, (max(8, int(82 * S * (1 - lift * 0.35))), 16))
        surf.blit(sh, sh.get_rect(center=(fx, GROUND_Y + 6)))

    # Cape.
    wave = math.sin(t * 4 + f.anim_t) * 6 + -f.vx * 2.2
    cape = [(fx - face * 7 * S, shoulder - 4),
            (fx - face * (30 + abs(wave) * 0.6) * S, hip + 7 + wave * 0.3),
            (fx - face * (17 + abs(wave) * 0.3) * S, feet - 7),
            (fx + face * 2 * S, hip)]
    pygame.draw.polygon(surf, trim, cape)
    pygame.draw.polygon(surf, (0, 0, 0), cape, 2)

    # Legs - they fold forward as the fighter drops into a crouch.
    for side, offset in ((1, swing), (-1, -swing)):
        knee = (fx + offset * 0.5 + face * 12 * c * S, hip + 21 * S * vs)
        foot = (fx + offset, feet - 2 + (0 if not airborne else -7 * side))
        pygame.draw.line(surf, body, (fx + lean, hip), knee, int(9 * S))
        pygame.draw.line(surf, body, knee, foot, int(8 * S))
        pygame.draw.line(surf, trim, foot, (foot[0] + face * 10 * S, foot[1]),
                         int(7 * S))

    # Torso, widening slightly when compressed.
    tw = (1 + 0.18 * c)
    torso = [(fx - 18 * S * tw + lean, hip + 2), (fx - 15 * S * tw + lean, shoulder),
             (fx + 15 * S * tw + lean, shoulder), (fx + 18 * S * tw + lean, hip + 2)]
    pygame.draw.polygon(surf, body, torso)
    pygame.draw.polygon(surf, (0, 0, 0), torso, 2)
    pygame.draw.line(surf, trim, (fx - 14 * S + lean, shoulder + 9 * S * vs),
                     (fx + 14 * S + lean, shoulder + 9 * S * vs), int(6 * S))
    pygame.draw.circle(surf, trim, (int(fx + lean), int(shoulder + 19 * S * vs)),
                       int(6 * S))

    back_x = fx - face * 14 * S + lean
    pygame.draw.line(surf, trim, (fx - face * 9 * S + lean, shoulder + 5),
                     (back_x - swing * 0.4, shoulder + 31 * S * vs), int(8 * S))

    cast = min(1.0, f.cast_anim / 0.30) if f.cast_anim > 0 else 0.0
    hand = (fx + face * (21 + 12 * cast) * S + lean,
            shoulder + (26 - 31 * cast) * S * vs)
    pygame.draw.line(surf, body, (fx + face * 9 * S + lean, shoulder + 5), hand,
                     int(9 * S))

    hx = fx + lean + face * 4 * c * S
    pygame.draw.circle(surf, body, (int(hx), int(head_y)), int(15 * S))
    pygame.draw.circle(surf, (0, 0, 0), (int(hx), int(head_y)), int(15 * S), 2)
    pygame.draw.line(surf, trim, (hx - 14 * S, head_y - 12 * S),
                     (hx + 14 * S, head_y - 14 * S), int(6 * S))
    visor = pygame.Rect(hx - 2 * S + face * 5 * S, head_y - 5 * S, 14 * S, 6 * S)
    pygame.draw.rect(surf, WHITE if flash else (255, 240, 180), visor,
                     border_radius=2)

    if cast > 0:
        glow_circle(surf, hand, int((14 + 10 * cast) * S), trim, strength=1.0)
        pygame.draw.circle(surf, WHITE, (int(hand[0]), int(hand[1])),
                           int((4 + 5 * cast) * S))
    return (hx, head_y)


def draw_shield(surf, f, t):
    """Andy's super shield: a bright barrier that throws shots back."""
    r = f.shield_rect()
    flash = min(1.0, f.shield_flash / 0.28)
    color = f.secondary
    s = pygame.Surface(r.size, pygame.SRCALPHA)
    pygame.draw.ellipse(s, (*color, int(80 + 130 * flash)), s.get_rect())
    pygame.draw.ellipse(s, (255, 255, 255, int(150 + 105 * flash)),
                        s.get_rect(), 3)
    for i in range(3):
        yy = r.h * (0.28 + 0.22 * i) + math.sin(t * 6 + i) * 3
        pygame.draw.line(s, (255, 255, 255, 110), (5, yy), (r.w - 5, yy), 2)
    surf.blit(s, r.topleft)
    glow_circle(surf, r.center, int(r.h * 0.55), color,
                strength=0.5 + 0.7 * flash)


def draw_fighter(surf, f, t):
    if f.is_ghost():
        # Drawn through a surface so the whole body fades as one, and given a
        # shimmer so it is findable if you are actually watching for it.
        body = body_surface(f, t)
        alpha = 46 + int(26 * (0.5 + 0.5 * math.sin(t * 3)))
        if f.invis < 1.6:
            alpha += int(70 * (1 - f.invis / 1.6))
        body.set_alpha(alpha)
        w, h = body.get_size()
        surf.blit(body, (f.x - w // 2, f.y - (h - 20)))
        if f.shielding:
            draw_shield(surf, f, t)
        return
    if f.in_super:
        pulse = 0.5 + 0.5 * math.sin(t * 9)
        glow_circle(surf, (f.x, f.y - f.height * 0.5),
                    int((44 + 9 * pulse) * f.build), f.secondary,
                    strength=0.45 + 0.15 * pulse)
    head = draw_body(surf, f, t, f.x, f.y)

    if f.status["stun"] > 0 and not f.frozen():
        for i in range(3):
            a = t * 6 + i * 2.1
            sx = head[0] + math.cos(a) * 24
            sy = head[1] - 26 + math.sin(a) * 7
            pygame.draw.circle(surf, GOLD, (int(sx), int(sy)), 3)

    if f.status["slow"] > 0 and not f.frozen():
        pygame.draw.circle(surf, (140, 220, 255),
                           (int(f.x), int(f.y - f.height * 0.5)),
                           int(40 * f.build), 1)

    if f.frozen():
        draw_ice_block(surf, f, t)
    if f.shielding:
        draw_shield(surf, f, t)


def draw_ice_block(surf, f, t):
    """Solid ice casing over a frozen fighter."""
    r = f.rect().inflate(26, 24)
    r.bottom = f.y + 6
    block = pygame.Surface(r.size, pygame.SRCALPHA)
    pygame.draw.polygon(block, (150, 225, 255, 105), [
        (r.w * 0.5, 0), (r.w, r.h * 0.24), (r.w * 0.86, r.h),
        (r.w * 0.14, r.h), (0, r.h * 0.24)])
    pygame.draw.polygon(block, (225, 250, 255, 190), [
        (r.w * 0.5, 0), (r.w, r.h * 0.24), (r.w * 0.86, r.h),
        (r.w * 0.14, r.h), (0, r.h * 0.24)], 3)
    for i in range(4):
        x1 = r.w * (0.2 + 0.2 * i)
        pygame.draw.line(block, (255, 255, 255, 120), (x1, r.h * 0.1),
                         (x1 + (8 if i % 2 else -8), r.h * 0.9), 2)
    surf.blit(block, r.topleft)
    glow_circle(surf, r.center, int(r.w * 0.9), (70, 150, 200), strength=0.5)
    shimmer = (math.sin(t * 8) * 0.5 + 0.5)
    pygame.draw.circle(surf, (255, 255, 255),
                       (int(r.centerx + math.sin(t * 3) * r.w * 0.3),
                        int(r.top + r.h * 0.2)), int(2 + 2 * shimmer))


def body_surface(f, t):
    """Snapshot of the body alone - used for ghosts and the downed pose."""
    w, h = int(200 * f.build), int(190 * f.build)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    draw_body(s, f, t, w // 2, h - 20, shadow=False)
    return s


def draw_downed(surf, f, t):
    """A knocked-out fighter lies on the floor instead of standing there."""
    pad = body_surface(f, t)
    pad = pygame.transform.rotate(pad, 82 * (1 if f.facing > 0 else -1))
    pad.set_alpha(215)
    surf.blit(pad, pad.get_rect(center=(f.x, GROUND_Y - 20)))
    sh = pygame.Surface((110, 20), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 120), (0, 0, 110, 20))
    surf.blit(sh, sh.get_rect(center=(f.x, GROUND_Y + 6)))


def _oriented(cx, cy, ang, pts, scale=1.0):
    """Rotate (forward, side) offsets into screen points around cx, cy."""
    ca, sa = math.cos(ang), math.sin(ang)
    return [(cx + (fx * ca - fy * sa) * scale,
             cy + (fx * sa + fy * ca) * scale) for fx, fy in pts]


def draw_projectile(surf, p, t):
    w = p.weapon
    rad = p.radius
    ang = math.atan2(p.vy, p.vx)
    for i, (tx, ty) in enumerate(p.trail):
        ratio = (i + 1) / len(p.trail)
        pygame.draw.circle(surf, w.glow, (int(tx), int(ty)),
                           max(1, int(rad * ratio * 0.85)))
    glow_circle(surf, (p.x, p.y), int(rad + 8), w.glow, layers=5)

    if w.art == "bolt":
        for branch in range(2):
            pts = []
            for i in range(6):
                d = i * 11 * p.scale
                off = 0 if i == 0 else random.uniform(-7, 7) * (1 + branch) * p.scale
                pts.append((p.x - math.cos(ang) * d - math.sin(ang) * off,
                            p.y - math.sin(ang) * d + math.cos(ang) * off))
            pygame.draw.lines(surf, w.core if branch == 0 else w.glow,
                              False, pts, max(1, int((3 - branch) * p.scale)))
        pygame.draw.circle(surf, w.core, (int(p.x), int(p.y)), int(rad - 2))
    elif w.art == "ice":
        for i in range(3):
            a = p.spin + i * math.pi / 3
            dx, dy = math.cos(a) * rad, math.sin(a) * rad
            pygame.draw.line(surf, w.core, (p.x - dx, p.y - dy),
                             (p.x + dx, p.y + dy), max(2, int(3 * p.scale)))
        pygame.draw.circle(surf, WHITE, (int(p.x), int(p.y)), int(4 * p.scale))
    elif w.art in ("bullet", "pellet"):
        # A tracer: a bright head with a hot streak dragged behind it.
        length = (18 if w.art == "bullet" else 11) * p.scale
        tail = _oriented(p.x, p.y, ang, [(-length, 0)])[0]
        pygame.draw.line(surf, w.glow, tail, (p.x, p.y),
                         max(2, int(rad * 0.8)))
        pygame.draw.circle(surf, w.core, (int(p.x), int(p.y)),
                           max(2, int(rad)))
    elif w.art == "rocket":
        flame = _oriented(p.x, p.y, ang, [
            (-13, -5), (-26 - random.random() * 12, 0), (-13, 5)], p.scale)
        pygame.draw.polygon(surf, (255, 196, 92), flame)
        fins = _oriented(p.x, p.y, ang, [(-7, -12), (-15, 0), (-7, 12)], p.scale)
        pygame.draw.polygon(surf, (146, 152, 176), fins)
        body = _oriented(p.x, p.y, ang, [
            (15, 0), (3, -7), (-13, -6), (-13, 6), (3, 7)], p.scale)
        pygame.draw.polygon(surf, (230, 234, 244), body)
        pygame.draw.polygon(surf, (52, 52, 70), body, 2)
        nose = _oriented(p.x, p.y, ang, [(11, 0)], p.scale)[0]
        pygame.draw.circle(surf, DANGER, (int(nose[0]), int(nose[1])),
                           max(2, int(3.5 * p.scale)))
    elif w.art == "wave":
        # A crescent of floor, not a ball - it reads as something to jump.
        for i in range(3):
            rr = rad * (1.0 - i * 0.22)
            box = pygame.Rect(0, 0, rr * 1.3, rr * 2.1)
            box.center = (p.x - i * 5 * (1 if p.vx > 0 else -1), p.y)
            pygame.draw.ellipse(surf, w.core if i == 0 else w.glow, box,
                                max(2, int(4 - i)))
        pygame.draw.line(surf, w.core, (p.x - rad, GROUND_Y),
                         (p.x + rad, GROUND_Y), 3)
    elif w.art == "arrow":
        shaft = _oriented(p.x, p.y, ang, [(-16, 0), (12, 0)], p.scale)
        pygame.draw.line(surf, (150, 118, 78), shaft[0], shaft[1],
                         max(2, int(3 * p.scale)))
        pygame.draw.polygon(surf, w.core, _oriented(p.x, p.y, ang, [
            (16, 0), (7, -4), (7, 4)], p.scale))
        for side in (-1, 1):
            tail, vane = _oriented(p.x, p.y, ang,
                                   [(-16, 0), (-9, side * 5)], p.scale)
            pygame.draw.line(surf, (236, 236, 240), tail, vane, 2)
    elif w.art == "tnt":
        spin = p.spin * 1.6
        box = _oriented(p.x, p.y, spin, [
            (-11, -11), (11, -11), (11, 11), (-11, 11)], p.scale)
        pygame.draw.polygon(surf, (198, 66, 54), box)
        pygame.draw.polygon(surf, (30, 24, 28), box, 2)
        band = _oriented(p.x, p.y, spin, [(-11, -2), (11, -2)], p.scale)
        pygame.draw.line(surf, (240, 240, 236), band[0], band[1],
                         max(3, int(6 * p.scale)))
        fuse = _oriented(p.x, p.y, spin, [(0, -11), (3, -19)], p.scale)
        pygame.draw.line(surf, (60, 50, 40), fuse[0], fuse[1], 2)
        if int(p.life * 12) % 2 == 0:
            pygame.draw.circle(surf, (255, 220, 120),
                               (int(fuse[1][0]), int(fuse[1][1])), 4)
    elif w.art == "knife":
        # Point-first, with a slight wobble so a volley does not look stamped.
        wob = math.sin(p.spin * 6) * 0.12
        blade = _oriented(p.x, p.y, ang + wob, [
            (14, 0), (2, -4), (-6, -3), (-6, 3), (2, 4)], p.scale)
        pygame.draw.polygon(surf, w.core, blade)
        pygame.draw.polygon(surf, (70, 76, 96), blade, 1)
        grip = _oriented(p.x, p.y, ang + wob, [(-6, 0), (-13, 0)], p.scale)
        pygame.draw.line(surf, (86, 92, 116), grip[0], grip[1],
                         max(2, int(3 * p.scale)))
    elif w.art == "potion":
        spin = p.spin * 3.2
        body = _oriented(p.x, p.y, spin, [
            (-7, -9), (7, -9), (10, 4), (0, 12), (-10, 4)], p.scale)
        pygame.draw.polygon(surf, (206, 150, 245), body)
        pygame.draw.polygon(surf, (60, 30, 80), body, 2)
        neck = _oriented(p.x, p.y, spin, [(-4, -14), (4, -14)], p.scale)
        pygame.draw.line(surf, (150, 110, 74), neck[0], neck[1],
                         max(2, int(5 * p.scale)))
        # The liquid always hangs down, whatever the flask is doing.
        pygame.draw.circle(surf, w.core, (int(p.x), int(p.y + 3 * p.scale)),
                           max(2, int(5 * p.scale)))
    else:
        r = rad + math.sin(t * 22) * 1.5
        pygame.draw.circle(surf, w.glow, (int(p.x), int(p.y)), int(r))
        pygame.draw.circle(surf, w.core, (int(p.x), int(p.y)), int(r * 0.55))
        for i in range(2):
            a = t * 9 + i * 3.1
            pygame.draw.circle(surf, w.core,
                               (int(p.x - p.vx * 0.6 + math.cos(a) * 6 * p.scale),
                                int(p.y + math.sin(a) * 6 * p.scale)),
                               max(1, int(2 * p.scale)))
    # Oversized siege shots get an extra warning ring.
    if p.scale > 1.4:
        pygame.draw.circle(surf, w.core, (int(p.x), int(p.y)), int(rad + 4), 2)


def draw_crosshair(surf, pos, fighter, t):
    """The cursor, and a short tick showing where the shot will actually go."""
    x, y = pos
    col = fighter.style.accent
    spin = t * 1.6
    for i in range(4):
        a = spin + i * math.pi / 2
        pygame.draw.line(surf, col,
                         (x + math.cos(a) * 7, y + math.sin(a) * 7),
                         (x + math.cos(a) * 14, y + math.sin(a) * 14), 2)
    pygame.draw.circle(surf, WHITE, (int(x), int(y)), 2)
    pygame.draw.circle(surf, col, (int(x), int(y)), 16, 1)
    # The aim arc is capped, so show the line the shot really takes.
    hx, hy = fighter.hand_pos()
    ax, ay = fighter.aim
    pygame.draw.line(surf, (*col, 90), (hx, hy), (hx + ax * 34, hy + ay * 34), 2)


def draw_wall(surf, w, t):
    """Cobblestone, cracking as it takes hits and fading as it times out."""
    r = w.rect()
    fade = 1.0 if w.life > 1.6 else max(0.2, w.life / 1.6)
    base = (146, 146, 150) if w.flash <= 0 else (236, 236, 240)
    body = pygame.Surface(r.size, pygame.SRCALPHA)
    rng = random.Random(int(w.x))
    for row in range(0, r.h, 26):
        for col in range(0, r.w, 26):
            shade = rng.randint(-26, 26)
            c = tuple(max(0, min(255, v + shade)) for v in base)
            pygame.draw.rect(body, (*c, int(235 * fade)),
                             (col + 1, row + 1, 24, 24), border_radius=3)
    body.set_alpha(int(255 * fade))
    surf.blit(body, r.topleft)
    pygame.draw.rect(surf, (40, 40, 48), r, 2, border_radius=4)
    # One crack per point of damage taken.
    for i in range(3 - w.hp):
        rng2 = random.Random(i * 31 + int(w.x))
        x0 = r.x + rng2.randint(6, r.w - 6)
        pygame.draw.line(surf, (30, 30, 36), (x0, r.y + 8),
                         (x0 + rng2.randint(-14, 14), r.bottom - 8), 3)


def draw_airdrop(surf, d, t):
    """Crate under a chute on the way down, glowing box once it lands."""
    if not d.landed:
        sway = math.sin(t * 2.2 + d.x) * 9
        top = d.y - 62
        canopy = pygame.Rect(0, 0, 86, 44)
        canopy.center = (d.x + sway, top)
        pygame.draw.ellipse(surf, d.core, canopy)
        pygame.draw.ellipse(surf, d.shade, canopy, 3)
        for side in (-1, 1):
            pygame.draw.line(surf, (222, 226, 240),
                             (d.x + sway + side * 40, top + 6),
                             (d.x + side * 15, d.y - 20), 2)
    else:
        # A landed crate hums, so it is obvious it is still there to take.
        pulse = 0.5 + 0.5 * math.sin(t * 5)
        fading = d.life < 3.5 and int(d.life * 6) % 2 == 0
        glow_circle(surf, (d.x, d.y), int(34 + 8 * pulse), d.core,
                    layers=5, strength=0.30 + 0.25 * pulse)
        if fading:
            return

    box = pygame.Rect(d.x - 21, d.y - 22, 42, 42)
    pygame.draw.rect(surf, d.shade, box, border_radius=5)
    pygame.draw.rect(surf, d.core, box.inflate(-10, -10), border_radius=4)
    pygame.draw.rect(surf, (16, 16, 26), box, 2, border_radius=5)
    cx, cy = box.center
    if d.kind == "health":
        pygame.draw.rect(surf, (24, 60, 40), (cx - 3, cy - 10, 6, 20))
        pygame.draw.rect(surf, (24, 60, 40), (cx - 10, cy - 3, 20, 6))
    elif d.kind == "boost":
        pygame.draw.polygon(surf, (110, 66, 12), [
            (cx + 3, cy - 12), (cx - 7, cy + 2), (cx - 1, cy + 2),
            (cx - 3, cy + 12), (cx + 8, cy - 3), (cx + 1, cy - 3)])
    else:
        pygame.draw.circle(surf, (50, 54, 104), (cx, cy - 3), 8)
        pygame.draw.polygon(surf, (50, 54, 104), [
            (cx - 8, cy - 3), (cx - 8, cy + 10), (cx - 4, cy + 6),
            (cx, cy + 10), (cx + 4, cy + 6), (cx + 8, cy + 10), (cx + 8, cy - 3)])
        pygame.draw.circle(surf, d.core, (cx - 3, cy - 4), 2)
        pygame.draw.circle(surf, d.core, (cx + 3, cy - 4), 2)


def draw_cloud(surf, c, t):
    """Rolling gas - dense while it is fresh, ragged as it disperses."""
    ratio = max(0.0, c.life / c.max_life)
    r = c.radius
    glow_circle(surf, (c.x, c.y), int(r * 0.85), c.weapon.glow,
                layers=5, strength=0.30 + 0.30 * ratio)
    puff = pygame.Surface((int(r * 2.4), int(r * 2.0)), pygame.SRCALPHA)
    for i in range(9):
        ang = c.spin * 6 + i * math.tau / 9
        wob = 0.72 + 0.28 * math.sin(t * 2.2 + i)
        px = puff.get_width() / 2 + math.cos(ang) * r * 0.52 * wob
        py = puff.get_height() / 2 + math.sin(ang) * r * 0.38 * wob
        pygame.draw.circle(puff, (*c.weapon.glow, int(66 * ratio + 22)),
                           (int(px), int(py)),
                           int(r * 0.42 * (0.6 + 0.4 * ratio)))
    surf.blit(puff, puff.get_rect(center=(int(c.x), int(c.y))))
    pygame.draw.ellipse(surf, c.weapon.core,
                        pygame.Rect(0, 0, int(r * 2), int(r * 1.5)).move(
                            int(c.x - r), int(c.y - r * 0.75)), 1)


def draw_slash(surf, s):
    """A crescent that sweeps closed as the strike finishes."""
    ratio = s.life / s.max_life
    w = s.weapon
    S = s.span()
    cx = s.owner.x + s.facing * 14 * S
    cy = s.owner.y - s.owner.height * 0.55
    span = w.reach * S * 1.67
    box = pygame.Rect(0, 0, span, span)
    box.center = (cx, cy)
    start = -0.95 if s.facing > 0 else math.pi - 0.95
    end = 0.95 if s.facing > 0 else math.pi + 0.95
    sweep = (1 - ratio) * 0.5
    accent = s.owner.secondary if w.art == "strike" else w.glow
    for width, color in ((8, WHITE), (3, accent)):
        pygame.draw.arc(surf, color, box, start + sweep, end - sweep,
                        max(1, int(width * ratio)))

    # The weapon itself, riding the arc it is carving.
    if w.art in ("bat", "katana"):
        a = start + (end - start) * (1 - ratio)
        reach = w.reach * S
        tip = (cx + math.cos(a) * reach, cy + math.sin(a) * reach)
        if w.art == "bat":
            grip = (cx + math.cos(a) * reach * 0.2, cy + math.sin(a) * reach * 0.2)
            pygame.draw.line(surf, (150, 110, 74), grip, tip, max(3, int(7 * S)))
            pygame.draw.circle(surf, w.core, (int(tip[0]), int(tip[1])),
                               max(3, int(7 * S)))
        else:
            grip = (cx + math.cos(a) * reach * 0.1, cy + math.sin(a) * reach * 0.1)
            pygame.draw.line(surf, w.core, grip, tip, max(2, int(4 * S)))
            glow_circle(surf, tip, int(9 * S), w.glow, layers=4)


# ------------------------------------------------------------------ hud ----


def panel(surf, rect, alpha=175, border=(90, 96, 130)):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, (*PANEL, alpha), s.get_rect(), border_radius=10)
    surf.blit(s, rect.topleft)
    pygame.draw.rect(surf, border, rect, 2, border_radius=10)


def health_bar(surf, fighter, side, to_win=ROUNDS_TO_WIN):
    w, h = 356, 26
    x = 26 if side == "left" else WIDTH - 26 - w
    y = 24
    panel(surf, pygame.Rect(x - 4, y - 4, w + 8, h + 29), 190)

    ratio = max(0.0, fighter.hp / fighter.max_hp)
    lag = max(0.0, fighter.hp_lag / fighter.max_hp)
    pygame.draw.rect(surf, (14, 14, 22), (x, y, w, h), border_radius=5)

    def bar(portion, color):
        bw = int(w * portion)
        if bw <= 0:
            return
        bx = x if side == "left" else x + w - bw
        pygame.draw.rect(surf, color, (bx, y, bw, h), border_radius=5)

    bar(lag, (210, 160, 60))
    top = (96, 214, 130) if ratio > 0.45 else (238, 190, 70) if ratio > 0.2 else DANGER
    bar(ratio, top)
    # Ticks every 100 HP so the pools stay comparable between characters.
    for hp in range(100, fighter.max_hp, 100):
        tx = x + w * (hp / fighter.max_hp) if side == "left" else \
            x + w - w * (hp / fighter.max_hp)
        pygame.draw.line(surf, (0, 0, 0), (tx, y + 4), (tx, y + h - 4), 1)
    pygame.draw.rect(surf, (0, 0, 0), (x, y, w, h), 2, border_radius=5)

    # --- super meter, doubling as the super timer while it runs ---------
    my = y + h + 4
    mh = 15
    pygame.draw.rect(surf, (12, 12, 20), (x, my, w, mh), border_radius=4)
    frac = max(0.0, min(1.0, fighter.meter / METER_MAX))
    if frac > 0:
        mw = int(w * frac)
        mx = x if side == "left" else x + w - mw
        color = fighter.secondary
        if fighter.super_ready:
            pulse = 0.7 + 0.3 * math.sin(pygame.time.get_ticks() * 0.012)
            color = tuple(min(255, int(c * pulse + 90)) for c in fighter.secondary)
        pygame.draw.rect(surf, color, (mx, my, mw, mh), border_radius=4)
    pygame.draw.rect(surf, (0, 0, 0), (x, my, w, mh), 2, border_radius=4)
    if fighter.in_super:
        text(surf, f"{fighter.super_name}  {fighter.super_timer:.1f}s",
             (x + w // 2, my + mh // 2), 13, WHITE, True, center=True)
    elif fighter.super_ready:
        text(surf, "SUPER READY  -  Q", (x + w // 2, my + mh // 2), 13,
             (20, 20, 30), True, center=True, shadow=False)

    name_pos = (x, y + h + 26) if side == "left" else (x + w, y + h + 26)
    label = font(22, True).render(fighter.name.upper(), True, fighter.secondary)
    rect = label.get_rect(topleft=name_pos) if side == "left" else \
        label.get_rect(topright=name_pos)
    surf.blit(label, rect)

    img = font(18).render(f"{int(fighter.hp)} / {fighter.max_hp}", True, DIM)
    r = img.get_rect(topright=(x + w, y + h + 28)) if side == "left" else \
        img.get_rect(topleft=(x, y + h + 28))
    surf.blit(img, r)

    for i in range(to_win):
        px = (x + 6 + i * 20) if side == "left" else (x + w - 6 - i * 20)
        color = GOLD if i < fighter.rounds_won else (60, 62, 82)
        pygame.draw.circle(surf, color, (px, y - 14), 6)
        pygame.draw.circle(surf, (0, 0, 0), (px, y - 14), 6, 2)

    chips = []
    if fighter.frozen():
        chips.append(((190, 240, 255), "FROZEN"))
    if fighter.status["burn"] > 0:
        chips.append(((255, 150, 60), "BURN"))
    if fighter.status["slow"] > 0:
        chips.append(((120, 210, 255), "SLOW"))
    if fighter.status["stun"] > 0:
        chips.append((GOLD, "STUN"))
    if fighter.buff > 0:
        chips.append(((255, 214, 110), "POWER"))
    if fighter.invis > 0:
        chips.append(((190, 200, 255), "GHOST"))
    for i, (color, name) in enumerate(chips):
        cw = 66
        ix = (x + i * (cw + 6)) if side == "left" else (x + w - cw - i * (cw + 6))
        r = pygame.Rect(ix, y + h + 50, cw, 20)
        chip = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(chip, (*color, 55), chip.get_rect(), border_radius=5)
        surf.blit(chip, r.topleft)
        pygame.draw.rect(surf, color, r, 2, border_radius=5)
        text(surf, name, r.center, 15, color, True, center=True, shadow=False)

    # Ice stacks building toward a freeze.
    if fighter.ice_hits and not fighter.frozen():
        for i in range(FREEZE_HITS):
            px = (x + 8 + i * 16) if side == "left" else (x + w - 8 - i * 16)
            on = i < len(fighter.ice_hits)
            pygame.draw.circle(surf, (150, 225, 255) if on else (48, 56, 72),
                               (px, y + h + 80), 5)


def round_timer(surf, seconds):
    low = seconds <= 10
    color = DANGER if low else WHITE
    size = 44 + (int(math.sin(seconds * 12) * 4) if low else 0)
    box = pygame.Rect(WIDTH // 2 - 60, 16, 120, 46)
    panel(surf, box, 170)
    text(surf, f"{int(math.ceil(max(0, seconds)))}", box.center, size, color,
         True, center=True)


def round_badge(surf, player, cpu, title, to_win=ROUNDS_TO_WIN):
    """Corner marker: which bout this is, and who has taken what."""
    box = pygame.Rect(24, HEIGHT - 92, 176, 66)
    panel(surf, box, 175, (110, 96, 140))
    size = 19
    while size > 11 and font(size, True).size(title)[0] > box.w - 14:
        size -= 1
    text(surf, title, (box.centerx, box.y + 18), size, GOLD, True, center=True)
    for i in range(to_win):
        pygame.draw.circle(surf, player.secondary if i < player.rounds_won
                           else (56, 58, 78), (box.x + 30 + i * 22, box.y + 45), 7)
        pygame.draw.circle(surf, cpu.secondary if i < cpu.rounds_won
                           else (56, 58, 78), (box.right - 30 - i * 22, box.y + 45), 7)
    text(surf, "vs", (box.centerx, box.y + 45), 16, DIM, center=True)


def endless_tag(surf, scale, boss):
    """How far the endless treadmill has tilted, shown as a plain multiplier."""
    color = DANGER if boss else (255, 170, 90)
    box = pygame.Rect(24, HEIGHT - 124, 176, 28)
    panel(surf, box, 175, color)
    label = f"{'BOSS' if boss else 'ENEMY'}  x{scale:.2f}"
    text(surf, label, box.center, 17, color, True, center=True)


def difficulty_tag(surf, difficulty):
    hard = difficulty == "hard"
    color = DANGER if hard else (110, 210, 140)
    box = pygame.Rect(WIDTH - 200, HEIGHT - 92, 176, 32)
    panel(surf, box, 170, color)
    text(surf, f"{difficulty.upper()} MODE", box.center, 17, color, True,
         center=True)


def weapon_icon(surf, r, w, ready):
    """A small glyph per weapon so the slots read at a glance."""
    live = w.glow if ready else (78, 78, 96)
    core = w.core if ready else (108, 108, 128)
    wood = (150, 112, 74) if ready else (74, 66, 60)
    cx, cy = r.center
    if w.art in ("fire", "ice", "bolt"):
        pygame.draw.circle(surf, live, r.center, 15)
        pygame.draw.circle(surf, core, r.center, 7)
    elif w.art == "bullet":
        pygame.draw.line(surf, live, (cx - 14, cy + 6), (cx + 6, cy - 3), 4)
        pygame.draw.circle(surf, core, (cx + 10, cy - 5), 5)
    elif w.art == "pellet":
        for dx, dy in ((-10, -8), (-2, 1), (5, -6), (11, 5), (-1, 10)):
            pygame.draw.circle(surf, core, (cx + dx, cy + dy), 3)
        pygame.draw.line(surf, live, (cx - 17, cy + 11), (cx - 8, cy + 6), 3)
    elif w.art == "rocket":
        pygame.draw.polygon(surf, live, _oriented(cx, cy, -0.6, [
            (-12, -4), (-22, 0), (-12, 4)]))
        body = _oriented(cx, cy, -0.6, [(15, 0), (3, -6), (-12, -5),
                                        (-12, 5), (3, 6)])
        pygame.draw.polygon(surf, core, body)
        pygame.draw.polygon(surf, live, body, 2)
    elif w.art in ("wave", "palm", "flurry"):
        pygame.draw.arc(surf, core, r.inflate(-10, -16), -1.1, 1.1, 4)
        pygame.draw.arc(surf, live, r.inflate(-22, -26), -1.1, 1.1, 3)
    elif w.art == "arrow":
        pygame.draw.line(surf, wood, (cx - 13, cy + 11), (cx + 8, cy - 7), 3)
        pygame.draw.polygon(surf, core, [(cx + 13, cy - 12), (cx + 4, cy - 8),
                                         (cx + 9, cy - 3)])
    elif w.art == "tnt":
        pygame.draw.rect(surf, (198, 66, 54), (cx - 11, cy - 9, 22, 20),
                         border_radius=3)
        pygame.draw.line(surf, (240, 240, 236), (cx - 11, cy), (cx + 11, cy), 6)
        pygame.draw.line(surf, (60, 50, 40), (cx, cy - 9), (cx + 3, cy - 16), 2)
    elif w.art == "block":
        for row in range(2):
            for col in range(2):
                pygame.draw.rect(surf, core if (row + col) % 2 else live,
                                 (cx - 13 + col * 13, cy - 13 + row * 13, 12, 12))
    elif w.art == "knife":
        for off, ang in ((-9, -0.7), (0, -0.5), (9, -0.3)):
            blade = _oriented(cx + off, cy + off * 0.4, ang, [
                (9, 0), (1, -3), (-5, -2), (-5, 2), (1, 3)])
            pygame.draw.polygon(surf, core, blade)
    elif w.art == "potion":
        body = [(cx - 7, cy - 6), (cx + 7, cy - 6), (cx + 10, cy + 6),
                (cx, cy + 13), (cx - 10, cy + 6)]
        pygame.draw.polygon(surf, live, body)
        pygame.draw.polygon(surf, core, body, 2)
        pygame.draw.line(surf, wood, (cx - 4, cy - 11), (cx + 4, cy - 11), 5)
        pygame.draw.circle(surf, core, (cx, cy + 4), 4)
    elif w.art == "bat":
        pygame.draw.line(surf, wood, (cx - 13, cy + 12), (cx + 5, cy - 5), 5)
        pygame.draw.circle(surf, core, (cx + 9, cy - 9), 7)
    elif w.art == "katana":
        pygame.draw.line(surf, core, (cx - 12, cy + 12), (cx + 13, cy - 12), 4)
        pygame.draw.line(surf, live, (cx - 16, cy + 14), (cx - 8, cy + 7), 5)
    else:
        pygame.draw.arc(surf, core, r.inflate(-14, -14), -0.9, 0.9, 4)


def usage_marks(surf, r, fighter, key, w):
    """The usage cooldown, drawn on top of the slot.

    Pips along the bottom are shots left; the amber bar is the live window
    counting down; a red slot with a number on it is a full lockout.
    """
    if not w.limited:
        return
    locked = fighter.lock[key] > 0
    live = fighter.window[key] > 0
    if locked:
        veil = pygame.Surface(r.size, pygame.SRCALPHA)
        veil.fill((150, 30, 30, 120))
        surf.blit(veil, r.topleft)
        text(surf, f"{fighter.lock[key]:.1f}", r.center, 20, (255, 190, 190),
             True, center=True)
        return
    if live and w.window:
        frac = max(0.0, min(1.0, fighter.window[key] / w.window))
        bar = pygame.Rect(r.x + 4, r.y + 4, int((r.w - 8) * frac), 4)
        pygame.draw.rect(surf, (255, 176, 70), bar, border_radius=2)
    if w.uses:
        gap = 9
        total = w.uses * gap
        for i in range(w.uses):
            px = r.centerx - total // 2 + gap // 2 + i * gap
            on = i < fighter.uses_left[key]
            pygame.draw.circle(surf, (255, 214, 120) if on else (58, 56, 72),
                               (px, r.bottom - 7), 3)


def weapon_bar(surf, fighter):
    """The style's three slots, the jab, the super, and any shield."""
    size, gap = 54, 22
    slots = list(fighter.kit)
    jab = fighter.strike_key not in fighter.kit
    count = len(slots) + (1 if jab else 0) + 1 + (1 if "shield" in fighter.super_kit else 0)
    total = count * size + (count - 1) * gap
    x0 = WIDTH // 2 - total // 2
    y0 = HEIGHT - 76

    def slot(i):
        return pygame.Rect(x0 + i * (size + gap), y0, size, size)

    def fit(msg, limit=size + gap - 6, start=15):
        s = start
        while s > 9 and font(s).size(msg)[0] > limit:
            s -= 1
        return s

    def cooldown_veil(r, frac):
        if frac <= 0:
            return
        fill = pygame.Surface((size, int(size * min(1.0, frac))), pygame.SRCALPHA)
        fill.fill((0, 0, 0, 165))
        surf.blit(fill, (r.x, r.y))

    i = 0
    for i, key in enumerate(slots):
        w = WEAPONS[key]
        r = slot(i)
        ready = fighter.ready(key)
        pygame.draw.rect(surf, (18, 18, 28), r, border_radius=8)
        weapon_icon(surf, r, w, ready)
        cooldown_veil(r, fighter.cooldowns[key] / w.cooldown)
        if fighter.cooldowns[key] > 0:
            text(surf, f"{fighter.cooldowns[key]:.1f}", r.center, 18, WHITE,
                 True, center=True)
        usage_marks(surf, r, fighter, key, w)
        pygame.draw.rect(surf, GOLD if ready else (70, 72, 96), r, 2,
                         border_radius=8)
        # A melee god's bat is also the J button, so it says so.
        tag = f"{i + 1} J" if key == fighter.strike_key else str(i + 1)
        text(surf, tag, (r.x + 5, r.y + 2), 15, WHITE, True, shadow=False)
        text(surf, w.short, (r.centerx, r.bottom + 11), fit(w.short),
             WHITE if ready else DIM, center=True)

    if jab:
        i += 1
        r = slot(i)
        w = WEAPONS[fighter.strike_key]
        ready = fighter.ready(fighter.strike_key)
        pygame.draw.rect(surf, (18, 18, 28), r, border_radius=8)
        weapon_icon(surf, r, w, ready)
        cooldown_veil(r, fighter.cooldowns[fighter.strike_key] / w.cooldown)
        pygame.draw.rect(surf, GOLD if ready else (70, 72, 96), r, 2,
                         border_radius=8)
        text(surf, "J", (r.x + 5, r.y + 2), 15, WHITE, True, shadow=False)
        text(surf, w.short, (r.centerx, r.bottom + 11), 15,
             WHITE if ready else DIM, center=True)

    # Super.
    i += 1
    r = slot(i)
    charged = fighter.super_ready
    running = fighter.in_super
    pygame.draw.rect(surf, (18, 18, 28), r, border_radius=8)
    spin = pygame.time.get_ticks() * 0.004
    pts = []
    for j in range(10):
        ang = spin + j * math.pi / 5
        rad = 18 if j % 2 == 0 else 8
        pts.append((r.centerx + math.cos(ang) * rad,
                    r.centery + math.sin(ang) * rad))
    pygame.draw.polygon(surf, fighter.secondary if (charged or running)
                        else (66, 66, 84), pts)
    if not (charged or running):
        cooldown_veil(r, 1 - fighter.meter / METER_MAX)
        text(surf, f"{int(fighter.meter)}%", r.center, 16, WHITE, True,
             center=True)
    elif running:
        text(surf, f"{fighter.super_timer:.1f}", r.center, 18, (20, 20, 30),
             True, center=True, shadow=False)
    pygame.draw.rect(surf, GOLD if (charged or running) else (70, 72, 96), r, 2,
                     border_radius=8)
    text(surf, "Q", (r.x + 5, r.y + 2), 15, WHITE, True, shadow=False)
    slabel = fighter.super_name if (charged or running) else "Super"
    text(surf, slabel, (r.centerx, r.bottom + 11), fit(slabel),
         GOLD if (charged or running) else DIM, center=True)

    # Shield, only for kits that carry one.
    if "shield" in fighter.super_kit:
        i += 1
        r = slot(i)
        live = fighter.can_shield()
        pygame.draw.rect(surf, (18, 18, 28), r, border_radius=8)
        col = fighter.secondary if live else (70, 70, 88)
        pygame.draw.ellipse(surf, col, r.inflate(-24, -12))
        pygame.draw.ellipse(surf, WHITE if fighter.shielding else (30, 30, 44),
                            r.inflate(-24, -12), 2)
        pygame.draw.rect(surf, GOLD if live else (70, 72, 96), r, 2,
                         border_radius=8)
        text(surf, "K", (r.x + 5, r.y + 2), 15, WHITE, True, shadow=False)
        text(surf, "Shield", (r.centerx, r.bottom + 11), 15,
             WHITE if live else DIM, center=True)


def stat_row(surf, x, y, label, value, maximum, color, dim=False):
    text(surf, label, (x, y), 16, DIM)
    bar = pygame.Rect(x + 52, y + 4, 124, 10)
    pygame.draw.rect(surf, (16, 16, 26), bar, border_radius=5)
    fill = pygame.Rect(bar.x, bar.y, int(bar.w * min(1.0, value / maximum)), bar.h)
    pygame.draw.rect(surf, tuple(c // 2 for c in color) if dim else color, fill,
                     border_radius=5)
    pygame.draw.rect(surf, (0, 0, 0), bar, 1, border_radius=5)


def vignette(surf, strength, color=DANGER):
    """Pulsing edge tint - used when the player is nearly out of health."""
    if strength <= 0:
        return
    v = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    steps = 8
    for i in range(steps):
        a = int(strength * 26 * (1 - i / steps))
        pygame.draw.rect(v, (*color, a), (i * 4, i * 4,
                                          WIDTH - i * 8, HEIGHT - i * 8),
                         border_radius=18)
    surf.blit(v, (0, 0))


# ----------------------------------------------------------------- game ----


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.bg = build_background()
        self.t = 0.0

        self.scene = "menu"
        self.phase = "intro"
        self.paused = False
        self.selection = 0          # which character
        self.style_index = 0        # which fighting style
        self.mode_index = 0         # which game mode
        self.boss_index = 0         # Sensei or Steve, in boss mode
        self.continue_index = 0     # endless or boss, after a tournament
        self.best_round = 0         # deepest endless round reached
        self.progress = load_progress()
        self.boss_unlocked = bool(self.progress.get("boss_unlocked"))
        self.best_endless = int(self.progress.get("best_endless", 0))
        self.just_unlocked = False
        self.mode = "quick"
        self.stage = 1              # tournament progress
        self.gold = 0
        self.shop_cards = []
        self.card_index = 0
        self.rerolls = 0            # resets every shop visit; first is free
        self.shop_bought = [0, 0, 0]
        self.shop_msg = ""
        self.to_win = ROUNDS_TO_WIN
        self.difficulty = "normal"
        self.menu_fighters = [Fighter(a) for a in ROSTER]
        for f, x in zip(self.menu_fighters, (200, 500, 800)):
            f.x, f.y = x, GROUND_Y
        self.menu_fighters[0].facing = 1
        self.menu_fighters[1].facing = 1
        self.menu_fighters[2].facing = -1

        self.player = self.cpu = self.brain = None
        self.projectiles = []
        self.particles = []
        self.texts = []
        self.slashes = []
        self.clouds = []
        self.drops = []
        self.walls = []
        self.next_drop = DROP_FIRST
        self.shockwaves = []
        self.ghosts = []
        self.embers = [self._new_ember() for _ in range(38)]
        self.fog = [[random.uniform(0, WIDTH), random.uniform(300, 430),
                     random.uniform(0.12, 0.34), random.uniform(120, 260)]
                    for _ in range(6)]

        self.shake = 0.0
        self.hitstop = 0.0
        self.time_scale = 1.0
        self.banner = ""
        self.banner_timer = 0.0
        self.phase_timer = 0.0
        self.round_no = 1
        self.round_time = ROUND_SECONDS
        self.last_beep = 99
        self.winner = None
        self.combo_owner = None
        self.combo_flash = 0.0
        self.freeze_flash = 0.0
        self.super_flash = 0.0
        self.super_owner = None
        self.sky_flash = 0.0
        self.next_sky = random.uniform(6, 14)

    # -- helpers -----------------------------------------------------------

    def _new_ember(self):
        return Particle(random.uniform(0, WIDTH), random.uniform(0, HEIGHT),
                        random.uniform(-0.25, 0.25), random.uniform(-0.7, -0.2),
                        99, 99, random.uniform(1.4, 3.0),
                        random.choice([(255, 170, 90), (255, 120, 70), (200, 160, 255)]),
                        gravity=0.0)

    def spawn_burst(self, x, y, color, count, spread=3.0, size=6, gravity=0.14):
        for _ in range(count):
            ang = random.uniform(0, math.tau)
            mag = random.uniform(0.3, 1.0) * spread
            life = random.uniform(0.28, 0.7)
            self.particles.append(Particle(
                x, y, math.cos(ang) * mag, math.sin(ang) * mag - 0.6,
                life, life, random.uniform(size * 0.5, size), color,
                gravity=gravity, fade_to=(40, 24, 30)))

    def set_banner(self, message, seconds):
        self.banner, self.banner_timer = message, seconds

    # -- match flow --------------------------------------------------------

    def modes(self):
        """The modes on offer. Boss only appears once it has been earned."""
        return [m for m in MODE_ORDER
                if m != "boss" or self.boss_unlocked]

    def unlock_bosses(self):
        if self.boss_unlocked:
            return
        self.boss_unlocked = True
        self.just_unlocked = True
        self.progress["boss_unlocked"] = True
        save_progress(self.progress)

    def other(self, f):
        """The fighter opposite `f` - what its shots chase and collide with."""
        return self.cpu if f is self.player else self.player

    def start_match(self, index, style_key, mode="quick"):
        self.mode = mode
        self.stage = 1
        self.gold = 0
        self.shop_bought = [0, 0, 0]
        self.player = Fighter(ROSTER[index], style_key)
        self.build_opponent()
        self.round_no = 1
        self.scene = "fight"
        self.winner = None
        self.start_round()

    def endless_boss_round(self):
        """Is this endless round one of the recurring boss rounds?"""
        return self.mode == "endless" and self.stage % ENDLESS_BOSS_EVERY == 0

    def scale_cpu(self, factor):
        """Scale the opponent. Endless is entirely built on this.

        Factors below 1.0 are as meaningful as those above - endless opens
        with a handicap and grows through it - so only an exact 1.0 is a
        no-op here.
        """
        if factor == 1.0:
            return
        self.cpu.max_hp = int(self.cpu.max_hp * factor)
        self.cpu.hp = self.cpu.max_hp
        self.cpu.hp_lag = float(self.cpu.hp)
        self.cpu.attack_damage *= factor

    def build_opponent(self):
        """Pick who is across from us, and how many rounds this bout runs."""
        skill = DIFFICULTIES[self.difficulty]
        boss_round = self.mode == "boss" or self.endless_boss_round()
        if boss_round:
            # A dedicated boss fight is best-of-three; a boss that turns up
            # mid-endless is a single round, which is what keeps it survivable
            # as a recurring event rather than a run-ender.
            self.to_win = 1 if self.mode == "endless" else ROUNDS_TO_WIN
            arch = (BOSSES[self.boss_index] if self.mode == "boss"
                    else random.choice(BOSSES))
            self.cpu = Fighter(arch, arch.boss_style)
            self.brain = BossBrain(self.cpu, self.player, skill=skill)
            self.scale_cpu(BOSS_EDGE[self.difficulty])
            if self.mode == "endless":
                self.scale_cpu(endless_scale_at(self.stage, True))
        else:
            # A tournament and endless both run separate one-round bouts.
            self.to_win = 1 if self.mode in ("tournament", "endless") else ROUNDS_TO_WIN
            pool = [a for a in ROSTER if a.name != self.player.name]
            self.cpu = Fighter(random.choice(pool), random.choice(STYLE_ORDER))
            self.brain = Brain(self.cpu, self.player, skill=skill)
            if self.mode == "endless":
                self.scale_cpu(endless_scale_at(self.stage, False))
        self.player.rounds_won = 0
        self.cpu.rounds_won = 0

    def start_round(self):
        self.player.reset(300, 1)
        self.cpu.reset(WIDTH - 300, -1)
        for group in (self.projectiles, self.particles, self.texts,
                      self.slashes, self.clouds, self.shockwaves, self.ghosts,
                      self.drops, self.walls):
            group.clear()
        self.next_drop = DROP_FIRST
        self.phase = "intro"
        self.phase_timer = 1.7
        self.time_scale = 1.0
        self.hitstop = 0.0
        self.round_time = ROUND_SECONDS
        self.last_beep = 99
        self.combo_flash = 0.0
        self.set_banner(self.bout_label(), 1.7)
        play("bell", 0.6)

    def bout_label(self):
        """What this bout is called, everywhere it gets named."""
        if self.mode == "tournament":
            return f"STAGE {self.stage} OF {TOURNAMENT_STAGES}"
        if self.mode == "endless":
            kind = "BOSS ROUND" if self.endless_boss_round() else "ROUND"
            return f"{kind} {self.stage}"
        if self.mode == "boss":
            return f"BOSS  -  ROUND {self.round_no}"
        return f"ROUND {self.round_no}"

    def end_round(self, winner, loser, reason=""):
        self.phase = "ko"
        self.phase_timer = 2.5
        self.time_scale = 0.3
        winner.rounds_won += 1
        self.shake = 18
        self.sky_flash = max(self.sky_flash, 0.45)
        self.set_banner(reason or f"{winner.name.upper()} WINS THE ROUND", 2.5)
        self.spawn_burst(loser.x, loser.cy, loser.secondary, 70, spread=7.5, size=10)
        self.shockwaves.append(Shockwave(loser.x, loser.cy, WHITE, r1=240,
                                         width=9, life=0.7, max_life=0.7,
                                         squash=0.9))
        play("ko", 0.85)

    def next_round(self):
        if max(self.player.rounds_won, self.cpu.rounds_won) < self.to_win:
            self.round_no += 1
            self.start_round()
            return

        won = self.player.rounds_won > self.cpu.rounds_won
        # A tournament run only ends when you lose or clear all three stages.
        if self.mode == "tournament" and won and self.stage < TOURNAMENT_STAGES:
            self.gold += GOLD_PER_STAGE
            self.stage += 1
            self.open_shop()
            return
        # Endless never ends on a win - it just gets worse.
        if self.mode == "endless" and won:
            self.gold += GOLD_PER_ENDLESS
            self.best_round = max(self.best_round, self.stage)
            if self.stage > self.best_endless:
                self.best_endless = self.stage
                self.progress["best_endless"] = self.stage
                save_progress(self.progress)
            self.stage += 1
            self.open_shop()
            return
        # Clearing the tournament is what earns the CONTINUE screen, and the
        # bosses with it. You keep your upgrades and your gold either way.
        if self.mode == "tournament" and won:
            self.unlock_bosses()
            self.gold += GOLD_PER_STAGE
            self.scene = "continue"
            self.continue_index = 0
            self.time_scale = 1.0
            play("win", 0.8)
            return
        self.winner = self.player if won else self.cpu
        self.scene = "matchend"
        self.time_scale = 1.0
        play("win" if won else "lose", 0.8)

    def endless_scale(self):
        """What the current endless opponent is multiplied by."""
        if self.mode != "endless":
            return 1.0
        return endless_scale_at(self.stage, self.endless_boss_round())

    def continue_run(self, choice):
        """Carry the built-up fighter into endless, or straight at a boss."""
        self.mode = choice
        self.stage = 1
        self.round_no = 1
        self.best_round = max(self.best_round, 0)
        self.player.rounds_won = 0
        self.player.hp = self.player.max_hp
        self.player.hp_lag = float(self.player.max_hp)
        self.build_opponent()
        self.scene = "fight"
        self.winner = None
        self.start_round()

    def open_shop(self):
        """Rest time between tournament rounds."""
        self.scene = "shop"
        self.rerolls = 0
        self.card_index = 0
        self.shop_msg = ""
        self.roll_cards()
        self.time_scale = 1.0
        play("bell", 0.7)

    def roll_cards(self):
        """One card per weapon slot - never three of the same weapon."""
        self.shop_cards = [roll_card(k) for k in self.player.kit]

    def shop_price(self, i):
        _, _, base, step = SHOP_ITEMS[i]
        return base + step * self.shop_bought[i]

    def buy_stat(self, i):
        price = self.shop_price(i)
        if self.gold < price:
            self.shop_msg = "not enough gold"
            play("whiff", 0.5)
            return
        self.gold -= price
        self.shop_bought[i] += 1
        p = self.player
        if i == 0:
            p.move_speed *= 1.06
        elif i == 1:
            p.attack_damage *= 1.08
        else:
            p.max_hp += 34
            p.hp = min(p.max_hp, p.hp + 34)
        self.shop_msg = f"{SHOP_ITEMS[i][0].lower()} up"
        play("confirm", 0.7)

    def reroll_cards(self):
        cost = REROLL_COSTS[min(self.rerolls, len(REROLL_COSTS) - 1)]
        if cost and self.gold < cost:
            self.shop_msg = f"reroll costs {cost} gold"
            play("whiff", 0.5)
            return
        self.gold -= cost
        self.rerolls += 1
        self.roll_cards()
        self.shop_msg = "rerolled" if cost else "free reroll used"
        play("select", 0.7)

    def take_card_and_go(self):
        card = self.shop_cards[self.card_index]
        self.player.take_card(card)
        play("confirm", 0.9)
        self.build_opponent()
        self.round_no = 1
        self.scene = "fight"
        self.start_round()

    def timeout(self):
        p = self.player.hp / self.player.max_hp
        c = self.cpu.hp / self.cpu.max_hp
        winner, loser = ((self.player, self.cpu) if p >= c
                         else (self.cpu, self.player))
        self.end_round(winner, loser, f"TIME UP - {winner.name.upper()} LEADS")

    # -- input -------------------------------------------------------------

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type != pygame.KEYDOWN:
            return True
        key = event.key

        if self.scene == "menu":
            if key in (pygame.K_LEFT, pygame.K_a):
                self.selection = (self.selection - 1) % len(ROSTER)
                play("select", 0.5)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.selection = (self.selection + 1) % len(ROSTER)
                play("select", 0.5)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                play("confirm", 0.9)
                self.scene = "style"        # character first, then style
            elif key == pygame.K_TAB:
                i = DIFFICULTY_ORDER.index(self.difficulty)
                self.difficulty = DIFFICULTY_ORDER[(i + 1) % len(DIFFICULTY_ORDER)]
                play("select", 0.6)
            elif key == pygame.K_ESCAPE:
                return False
            return True

        if self.scene == "style":
            if key in (pygame.K_LEFT, pygame.K_a):
                self.style_index = (self.style_index - 1) % len(STYLE_ORDER)
                play("select", 0.5)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.style_index = (self.style_index + 1) % len(STYLE_ORDER)
                play("select", 0.5)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                play("confirm", 0.9)
                self.scene = "mode"
            elif key in (pygame.K_BACKSPACE, pygame.K_ESCAPE):
                self.scene = "menu"
                play("select", 0.5)
            return True

        if self.scene == "mode":
            modes = self.modes()
            self.mode_index = min(self.mode_index, len(modes) - 1)
            if key in (pygame.K_LEFT, pygame.K_a):
                self.mode_index = (self.mode_index - 1) % len(modes)
                play("select", 0.5)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.mode_index = (self.mode_index + 1) % len(modes)
                play("select", 0.5)
            elif key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                # Only meaningful on the boss card, harmless elsewhere.
                if self.boss_unlocked:
                    self.boss_index = (self.boss_index + 1) % len(BOSSES)
                    play("select", 0.6)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                play("confirm", 0.9)
                self.start_match(self.selection, STYLE_ORDER[self.style_index],
                                 modes[self.mode_index])
            elif key in (pygame.K_BACKSPACE, pygame.K_ESCAPE):
                self.scene = "style"
                play("select", 0.5)
            return True

        if self.scene == "shop":
            if key in (pygame.K_LEFT, pygame.K_a):
                self.card_index = (self.card_index - 1) % len(self.shop_cards)
                play("select", 0.4)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.card_index = (self.card_index + 1) % len(self.shop_cards)
                play("select", 0.4)
            elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
                self.buy_stat(key - pygame.K_1)
            elif key == pygame.K_r:
                self.reroll_cards()
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.take_card_and_go()
            elif key == pygame.K_ESCAPE:
                return False
            return True

        if self.scene == "continue":
            if key in (pygame.K_LEFT, pygame.K_a):
                self.continue_index = (self.continue_index - 1) % len(CONTINUE_ORDER)
                play("select", 0.5)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.continue_index = (self.continue_index + 1) % len(CONTINUE_ORDER)
                play("select", 0.5)
            elif key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                self.boss_index = (self.boss_index + 1) % len(BOSSES)
                play("select", 0.6)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                play("confirm", 0.9)
                self.continue_run(CONTINUE_ORDER[self.continue_index])
            elif key == pygame.K_r:
                # Bank the win and go back to the roster instead.
                self.winner = self.player
                self.scene = "matchend"
            elif key == pygame.K_ESCAPE:
                return False
            return True

        if self.scene == "matchend":
            if key == pygame.K_r:
                self.scene = "menu"
                self.just_unlocked = False
            elif key == pygame.K_ESCAPE:
                return False
            return True

        if key in (pygame.K_p, pygame.K_ESCAPE):
            self.paused = not self.paused
            return True
        if self.paused:
            if key == pygame.K_q:
                self.scene = "menu"
                self.paused = False
            return True
        if self.phase != "active":
            return True

        if key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
            self.player.jump(self)
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.player.use(self.player.kit[key - pygame.K_1], self)
        elif key in (pygame.K_j, pygame.K_f):
            self.player.strike(self)
        elif key in (pygame.K_q, pygame.K_LSHIFT, pygame.K_RSHIFT):
            self.player.activate_super(self)
        return True

    def read_input(self, k):
        held = pygame.key.get_pressed()
        left = held[pygame.K_a] or held[pygame.K_LEFT]
        right = held[pygame.K_d] or held[pygame.K_RIGHT]
        self.player.set_crouch(held[pygame.K_s] or held[pygame.K_DOWN])
        self.player.shielding = (self.player.can_shield()
                                 and (held[pygame.K_k] or held[pygame.K_e]))
        if left and not right:
            self.player.walk(-1, k)
        elif right and not left:
            self.player.walk(1, k)
        # The cursor is the crosshair: it turns you and it aims your shots.
        mx, my = pygame.mouse.get_pos()
        if self.player.can_act():
            self.player.facing = 1 if mx >= self.player.x else -1
            self.player.set_aim(mx, my)

    # -- simulation --------------------------------------------------------

    def update(self, dt):
        self.t += dt
        k = dt * FPS

        for e in self.embers:
            e.x += e.vx * k
            e.y += e.vy * k
            if e.y < -10:
                e.x, e.y = random.uniform(0, WIDTH), HEIGHT + 8
        for band in self.fog:
            band[0] += band[2] * k
            if band[0] - band[3] > WIDTH:
                band[0] = -band[3]

        self.shake = max(0.0, self.shake - 34 * dt)
        self.banner_timer = max(0.0, self.banner_timer - dt)
        self.combo_flash = max(0.0, self.combo_flash - dt)
        self.freeze_flash = max(0.0, self.freeze_flash - dt)
        self.super_flash = max(0.0, self.super_flash - dt * 1.6)
        self.sky_flash = max(0.0, self.sky_flash - dt * 2.2)

        self.next_sky -= dt
        if self.next_sky <= 0:
            self.next_sky = random.uniform(7, 16)
            self.sky_flash = 0.55
            play("ko", 0.18)

        # Every scene that is not a live fight stops here. Miss one - "shop"
        # was missing once - and the round logic below keeps running behind
        # it: phase is still "ko" with an expired timer, so next_round() fires
        # every frame and the stage counter and gold climb while you shop.
        if self.scene in ("menu", "style", "mode", "shop", "continue",
                          "matchend"):
            for f in self.menu_fighters:
                f.anim_t += dt
            return
        if self.paused:
            return

        # Impact freeze-frames land harder than any particle effect.
        if self.hitstop > 0:
            self.hitstop = max(0.0, self.hitstop - dt)
            return

        if self.phase == "intro":
            self.phase_timer -= dt
            if self.phase_timer <= 0:
                self.phase = "active"
                self.set_banner("FIGHT!", 0.9)
                play("confirm", 0.6)
        elif self.phase == "ko":
            self.phase_timer -= dt
            self.time_scale = min(1.0, self.time_scale + dt * 0.35)
            if self.phase_timer <= 0:
                self.next_round()
                return

        sdt = dt * self.time_scale
        sk = sdt * FPS

        if self.phase == "active":
            self.read_input(sk)
            self.brain.update(sdt, sk, self)
            self.round_time -= dt
            if self.round_time <= 6 and int(self.round_time) != self.last_beep:
                self.last_beep = int(self.round_time)
                if self.round_time > 0:
                    play("warn", 0.4)
            if self.round_time <= 0:
                self.timeout()

        for f in (self.player, self.cpu):
            f.update(sdt, sk, self)
            self.emit_ghost(f, sdt)
        self.separate(self.player, self.cpu, sk)

        self.update_projectiles(sk)
        self.update_slashes(sdt)
        self.update_clouds(sdt)
        self.update_drops(sdt, sk)
        for w in self.walls:
            w.update(sk)
        self.walls = [w for w in self.walls if w.life > 0 and w.hp > 0]

        for group in (self.particles, self.shockwaves, self.ghosts):
            for item in group:
                item.update(sk)
        self.particles = [p for p in self.particles if p.life > 0]
        self.shockwaves = [s for s in self.shockwaves if s.life > 0]
        self.ghosts = [g for g in self.ghosts if g.life > 0]
        for t_ in self.texts:
            t_.update(sk)
        self.texts = [t_ for t_ in self.texts if t_.life > 0]

        if self.phase == "active" and (not self.player.is_alive()
                                       or not self.cpu.is_alive()):
            if self.player.is_alive():
                self.end_round(self.player, self.cpu)
            else:
                self.end_round(self.cpu, self.player)

    def emit_ghost(self, f, dt):
        """Speed trails - Max leaves them constantly, everyone else when quick."""
        f.ghost_timer -= dt
        threshold = 3.0 if f.double_jump else 4.2
        if abs(f.vx) > threshold and f.ghost_timer <= 0:
            f.ghost_timer = 0.045
            self.ghosts.append(Afterimage(body_surface(f, self.t), f.x,
                                          f.y - 95 * f.build + 20))

    def separate(self, a, b, k):
        overlap = 46 * max(a.build, b.build) - abs(a.x - b.x)
        if overlap > 0 and abs(a.y - b.y) < 60:
            push = overlap * 0.08 * k
            direction = 1 if a.x >= b.x else -1
            a.x += push * direction * (2 - a.build)
            b.x -= push * direction * (2 - b.build)

    def update_projectiles(self, k):
        alive = []
        for p in self.projectiles:
            p.update(k)
            if random.random() < 0.6:
                self.particles.append(Particle(
                    p.x, p.y, random.uniform(-0.4, 0.4), random.uniform(-0.4, 0.4),
                    0.32, 0.32, p.weapon.radius * 0.5, p.weapon.glow,
                    gravity=-0.02, fade_to=(30, 20, 40)))

            # A wall in the way stops the shot, whoever fired it.
            blocked = False
            for wall in self.walls:
                if wall.owner is not p.owner and p.rect().colliderect(wall.rect()):
                    wall.hp -= 1
                    wall.flash = 0.25
                    self.spawn_burst(p.x, p.y, (190, 190, 190), 16, spread=3.5)
                    play("land", 0.4)
                    if p.weapon.splash:
                        self.detonate(p, None)
                    blocked = True
                    break
            if blocked:
                continue

            target = self.other(p.owner)
            if (target.shielding and target.is_alive()
                    and p.rect().colliderect(target.shield_rect())):
                self.reflect(p, target)
                alive.append(p)
                continue
            if target.is_alive() and p.rect().colliderect(target.rect()):
                self.resolve_hit(p, target)
                continue
            # A rocket does not have to touch you. Its fuse trips on the way
            # past, which is the gun style's only answer to a stance its
            # level shots cannot reach - and it pays half damage for it.
            if (p.weapon.splash and target.is_alive()
                    and math.hypot(p.x - target.x, p.y - target.cy)
                    < p.weapon.splash * 0.6 * p.scale):
                self.detonate(p, target)
                continue
            if p.life > 0 and -60 < p.x < WIDTH + 60:
                alive.append(p)
            else:
                # A rocket that runs out of fuel still goes off - pass the
                # target so anyone standing in the blast takes it. detonate()
                # does its own radius check.
                if p.weapon.splash:
                    self.detonate(p, target)
                self.spawn_burst(p.x, p.y, p.weapon.glow, 8, spread=2.5)
        self.projectiles = alive

    def reflect(self, p, blocker):
        """Shield contact sends the shot back at whoever fired it."""
        p.owner = blocker
        p.target = self.other(blocker)
        p.vx = -p.vx * 1.2
        p.life = max(p.life, 2.0)
        p.trail.clear()
        direction = 1 if p.vx > 0 else -1
        p.x = blocker.x + direction * (46 * blocker.build + p.radius + 2)
        blocker.shield_flash = 0.28
        blocker.gain_meter(6)
        self.shake = max(self.shake, 7)
        self.hitstop = max(self.hitstop, 0.04)
        self.spawn_burst(p.x, p.y, WHITE, 20, spread=4.5, size=6)
        self.shockwaves.append(Shockwave(p.x, p.y, blocker.secondary, r1=80,
                                         width=4, squash=1.0))
        self.texts.append(FloatingText(blocker.x, blocker.y - blocker.height - 30,
                                       "REFLECT!", blocker.secondary, size=24,
                                       life=0.8, max_life=0.8))
        play("reflect", 0.7)

    def resolve_hit(self, p, target):
        w = p.weapon
        if w.splash:
            self.detonate(p, target, direct=True)
            return
        # Only the first pellet of a spray gets the full treatment - four of
        # them would otherwise read as a four-hit combo and shake the screen
        # four times for one trigger pull.
        first = p.volley is None or not p.volley["hit"]
        if p.volley is not None:
            p.volley["hit"] = True
        damage = p.owner.roll_damage(p.owner.wstat(w.key, "multiplier"))
        p.owner.gain_meter(damage * p.owner.arch.meter_dealt)
        target.take_damage(damage, 1 if p.vx > 0 else -1, self,
                           knock=w.knock, quiet=not first)
        p.owner.leech(damage, self)
        if first:
            p.owner.register_hit(self)
        if w.effect == "burn":
            target.apply_status("burn", BURN_SECONDS)
        elif w.effect == "stun":
            target.apply_status("stun", STUN_SECONDS)
            play("stun", 0.5)
            self.sky_flash = max(self.sky_flash, 0.3)
        elif w.effect == "ice":
            target.register_ice_hit(self)
        self.spawn_burst(p.x, p.y, w.core, 28 if first else 8, spread=5.5, size=7)
        if first:
            self.shockwaves.append(Shockwave(p.x, p.y, w.glow, r1=90, width=5,
                                             squash=1.0))
            self.texts.append(FloatingText(
                target.x, target.y - target.height - 40, w.name.upper(),
                w.glow, size=18, life=0.7, max_life=0.7))

    def detonate(self, p, target, direct=False):
        """A blast goes off: full damage on contact, a share in the radius."""
        w = p.weapon
        radius = p.owner.wstat(w.key, "splash") * p.scale
        self.shake = max(self.shake, 14)
        self.hitstop = max(self.hitstop, 0.08)
        self.sky_flash = max(self.sky_flash, 0.25)
        self.spawn_burst(p.x, p.y, w.core, 44, spread=7.5, size=9)
        self.shockwaves.append(Shockwave(p.x, p.y, w.glow, r1=radius * 1.6,
                                         width=7, life=0.42, max_life=0.42,
                                         squash=1.0))
        play("shatter" if w.effect == "toxin" else "explode", 0.8)

        if w.cloud:
            self.clouds.append(Cloud(p.x, p.y, radius * 0.92, p.owner, w,
                                     life=w.cloud, max_life=w.cloud))

        if target is not None and target.is_alive():
            near = math.hypot(p.x - target.x, p.y - target.cy) <= radius
            if direct or near:
                share = 1.0 if direct else w.splash_share
                damage = max(1, round(p.owner.roll_damage(
                    p.owner.wstat(w.key, "multiplier")) * share))
                p.owner.gain_meter(damage * p.owner.arch.meter_dealt)
                target.take_damage(damage, 1 if p.x < target.x else -1, self)
                p.owner.leech(damage, self)
                p.owner.register_hit(self)
                if w.effect == "toxin":
                    self.apply_toxin(target, impact=True)
                self.texts.append(FloatingText(
                    target.x, target.y - target.height - 40,
                    "DIRECT HIT" if direct else "BLAST", w.glow, size=18,
                    life=0.7, max_life=0.7))

        # Your own potion does not care that you threw it.
        thrower = p.owner
        if w.selfharm and thrower.is_alive():
            if math.hypot(p.x - thrower.x, p.y - thrower.cy) <= radius:
                hurt = max(1, round(thrower.roll_damage(
                    thrower.wstat(w.key, "multiplier")) * w.selfharm))
                thrower.take_damage(hurt, 1 if p.x < thrower.x else -1, self)
                if w.effect == "toxin":
                    self.apply_toxin(thrower, impact=False)
                self.texts.append(FloatingText(
                    thrower.x, thrower.y - thrower.height - 40, "CAUGHT IN IT!",
                    (255, 140, 160), size=19, life=0.9, max_life=0.9))

    def apply_toxin(self, f, impact):
        """Slow and a short burn on everyone; the stun only on a clean hit."""
        f.apply_status("slow", POTION_SLOW)
        f.apply_status("burn", POTION_BURN)
        if impact:
            f.apply_status("stun", POTION_STUN)
            play("stun", 0.4)

    def update_drops(self, dt, k):
        """Spawn crates on a timer, then let either fighter walk into one."""
        if self.phase == "active":
            self.next_drop -= dt
            if self.next_drop <= 0:
                self.next_drop = random.uniform(*DROP_EVERY)
                self.spawn_drop()
        alive = []
        for d in self.drops:
            d.update(k)
            if d.landed:
                grabbed = None
                for f in (self.player, self.cpu):
                    if f.is_alive() and f.rect().colliderect(d.rect()):
                        grabbed = f
                        break
                if grabbed is not None:
                    self.collect(d, grabbed)
                    continue
            if d.life > 0:
                alive.append(d)
            else:
                self.spawn_burst(d.x, d.y, d.shade, 12, spread=2.5)
        self.drops = alive

    def spawn_drop(self):
        """Drop it away from both fighters so neither just walks into it."""
        best, best_gap = WIDTH / 2, -1
        for _ in range(8):
            x = random.uniform(WALL_MARGIN + 60, WIDTH - WALL_MARGIN - 60)
            gap = min(abs(x - self.player.x), abs(x - self.cpu.x))
            if gap > best_gap:
                best, best_gap = x, gap
        kind = random.choice(DROP_KINDS)
        self.drops.append(Airdrop(kind, best, -40.0))
        self.texts.append(FloatingText(best, 120, "AIRDROP INBOUND",
                                       Airdrop.COLORS[kind][0], size=22,
                                       life=1.4, max_life=1.4, vy=-0.3))
        play("warn", 0.35)

    def collect(self, d, f):
        """Apply a crate. Health is instant; the other two run on a clock."""
        if d.kind == "health":
            healed = min(PICKUP_HEAL, f.max_hp - f.hp)
            f.hp += healed
            f.hp_lag = min(f.hp_lag, f.hp)
            label = f"+{healed} HP" if healed else "FULL HEALTH"
        elif d.kind == "boost":
            f.buff = BOOST_SECONDS
            label = "POWER UP"
        else:
            f.invis = GHOST_SECONDS
            label = "GHOST"
        self.texts.append(FloatingText(f.x, f.y - f.height - 44, label,
                                       d.core, size=28, life=1.2, max_life=1.2))
        self.shockwaves.append(Shockwave(d.x, d.y, d.core, r1=110, width=6,
                                         life=0.42, max_life=0.42, squash=1.0))
        self.spawn_burst(d.x, d.y, d.core, 30, spread=5.0, size=7)
        play("confirm", 0.7)

    def update_clouds(self, dt):
        """Gas ticks on anyone inside, then chokes them as it disperses."""
        for c in self.clouds:
            c.update(dt * FPS)
            c.tick -= dt
            tick = c.tick <= 0
            if tick:
                c.tick = CLOUD_TICK
            for f in (self.player, self.cpu):
                if not f.is_alive() or not c.holds(f):
                    continue
                f.apply_status("slow", POTION_SLOW * 0.5)
                if tick:
                    f.take_damage(CLOUD_DAMAGE, 0, self, quiet=True)
            if random.random() < 0.7:
                ang = random.uniform(0, math.tau)
                rad = c.radius * random.uniform(0.2, 1.0)
                self.particles.append(Particle(
                    c.x + math.cos(ang) * rad, c.y + math.sin(ang) * rad * 0.7,
                    random.uniform(-0.3, 0.3), random.uniform(-0.5, -0.1),
                    0.7, 0.7, 7, c.weapon.glow, gravity=-0.02,
                    fade_to=(60, 30, 80)))
            c.life -= dt
            if c.life <= 0:
                # The gas breaking up is the second stun.
                for f in (self.player, self.cpu):
                    if f.is_alive() and c.holds(f):
                        f.apply_status("stun", POTION_CHOKE)
                        self.texts.append(FloatingText(
                            f.x, f.y - f.height - 30, "CHOKED", c.weapon.glow,
                            size=20, life=0.8, max_life=0.8))
                        play("stun", 0.45)
        self.clouds = [c for c in self.clouds if c.life > 0]

    def update_slashes(self, dt):
        for s in self.slashes:
            s.life -= dt
            if s.hit:
                continue
            target = self.cpu if s.owner is self.player else self.player
            if (target.shielding and target.is_alive()
                    and s.rect().colliderect(target.shield_rect())):
                s.hit = True
                target.shield_flash = 0.28
                target.gain_meter(5)
                s.owner.vx -= s.facing * 4.0
                # A shot gets thrown back; a swing gets parried. Without the
                # stagger the shield would be dead weight against a melee god.
                s.owner.apply_status("stun", 0.22)
                self.spawn_burst(target.shield_rect().centerx,
                                 target.shield_rect().centery, WHITE, 14, spread=3.5)
                self.texts.append(FloatingText(
                    target.x, target.y - target.height - 30, "PARRY!",
                    target.secondary, size=22, life=0.7, max_life=0.7))
                play("shield", 0.6)
                continue
            if target.is_alive() and s.rect().colliderect(target.rect()):
                s.hit = True
                damage = s.owner.roll_damage(
                    s.owner.wstat(s.weapon.key, "multiplier"))
                s.owner.gain_meter(damage * s.owner.arch.meter_dealt)
                target.take_damage(damage, s.facing, self, knock=s.weapon.knock)
                s.owner.leech(damage, self)
                s.owner.register_hit(self)
                self.spawn_burst(target.x, target.cy, s.weapon.core, 16, spread=4)
            elif s.life <= 0:
                play("whiff", 0.25)
        self.slashes = [s for s in self.slashes if s.life > 0]

    # -- rendering ---------------------------------------------------------

    def draw(self):
        c = self.canvas
        c.blit(self.bg, (0, 0))

        for x, y, speed, w in self.fog:
            band = pygame.Surface((int(w), 46), pygame.SRCALPHA)
            pygame.draw.ellipse(band, (150, 130, 180, 26), band.get_rect())
            c.blit(band, (x - w, y))

        for e in self.embers:
            pygame.draw.circle(c, e.color, (int(e.x), int(e.y)), int(e.size))
        draw_torch_flame(c, 70, 240, self.t, 0.0)
        draw_torch_flame(c, WIDTH - 70, 240, self.t, 2.4)

        if self.sky_flash > 0:
            flash = pygame.Surface((WIDTH, GROUND_Y), pygame.SRCALPHA)
            flash.fill((190, 190, 255, int(70 * min(1.0, self.sky_flash))))
            c.blit(flash, (0, 0))

        if self.scene == "menu":
            self.draw_menu(c)
        elif self.scene == "style":
            self.draw_style_select(c)
        elif self.scene == "mode":
            self.draw_mode_select(c)
        elif self.scene == "shop":
            self.draw_shop(c)
        else:
            for g in self.ghosts:
                g.draw(c)
            for p in self.particles:
                p.draw(c)
            for s in self.shockwaves:
                s.draw(c)
            for wall in self.walls:
                draw_wall(c, wall, self.t)
            for d in self.drops:
                draw_airdrop(c, d, self.t)
            for cl in self.clouds:
                draw_cloud(c, cl, self.t)
            for s in self.slashes:
                draw_slash(c, s)
            for f in sorted((self.player, self.cpu), key=lambda f: f.y):
                if f.is_alive():
                    draw_fighter(c, f, self.t)
                else:
                    draw_downed(c, f, self.t)
            for p in self.projectiles:
                draw_projectile(c, p, self.t)
            for t_ in self.texts:
                alpha = max(0.0, t_.life / t_.max_life)
                img = font(t_.size, True).render(t_.text, True, t_.color)
                img.set_alpha(int(255 * alpha))
                c.blit(img, img.get_rect(center=(t_.x, t_.y)))

        if self.super_flash > 0 and self.super_owner:
            tint = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            tint.fill((*self.super_owner.secondary,
                       int(95 * min(1.0, self.super_flash))))
            c.blit(tint, (0, 0))

        if self.freeze_flash > 0:
            tint = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            tint.fill((150, 225, 255, int(80 * min(1.0, self.freeze_flash * 2))))
            c.blit(tint, (0, 0))

        ox = random.uniform(-self.shake, self.shake)
        oy = random.uniform(-self.shake, self.shake)
        self.screen.fill(BLACK)
        self.screen.blit(c, (ox, oy))

        if self.scene == "fight":
            low = 1 - self.player.hp / self.player.max_hp
            if low > 0.75:
                vignette(self.screen, (low - 0.75) * 4 *
                         (0.6 + 0.4 * math.sin(self.t * 6)))
            health_bar(self.screen, self.player, "left", self.to_win)
            health_bar(self.screen, self.cpu, "right", self.to_win)
            weapon_bar(self.screen, self.player)
            if self.phase == "active" and self.player.is_alive():
                draw_crosshair(self.screen, pygame.mouse.get_pos(),
                               self.player, self.t)
            round_timer(self.screen, self.round_time)
            label = self.bout_label()
            if self.mode == "quick":
                label += f" OF {ROUNDS_TO_WIN + 1}"
            round_badge(self.screen, self.player, self.cpu, label, self.to_win)
            if self.mode == "endless":
                endless_tag(self.screen, self.endless_scale(),
                            self.endless_boss_round())
            difficulty_tag(self.screen, self.difficulty)
            self.draw_combo(self.screen)
        elif self.scene == "continue":
            self.draw_continue(self.screen)
        elif self.scene == "matchend":
            self.draw_matchend(self.screen)

        if self.banner_timer > 0 and self.scene == "fight":
            self.draw_banner(self.screen)
        if self.paused:
            self.draw_pause(self.screen)

        pygame.display.flip()

    def draw_combo(self, surf):
        if self.combo_flash <= 0 or not self.combo_owner:
            return
        owner = self.combo_owner
        if owner.combo < 2:
            return
        side = 250 if owner is self.player else WIDTH - 250
        pop = max(0.0, self.combo_flash - 0.7) * 3
        size = int(34 + 16 * pop + min(12, owner.combo * 2))
        alpha = min(1.0, self.combo_flash * 1.6)
        img = font(size, True).render(f"{owner.combo} HIT COMBO", True, GOLD)
        img.set_alpha(int(255 * alpha))
        shadow = font(size, True).render(f"{owner.combo} HIT COMBO", True, (0, 0, 0))
        shadow.set_alpha(int(255 * alpha))
        surf.blit(shadow, shadow.get_rect(center=(side + 3, 143)))
        surf.blit(img, img.get_rect(center=(side, 140)))

    def draw_banner(self, surf):
        ratio = self.banner_timer / max(0.001, 1.7)
        scale = 1.0 + 0.25 * max(0.0, min(1.0, ratio - 0.75)) * 4
        size = int(58 * min(1.6, scale))
        while size > 20 and font(size, True).size(self.banner)[0] > WIDTH - 90:
            size -= 2
        img = font(size, True).render(self.banner, True, GOLD)
        img.set_alpha(int(255 * min(1.0, self.banner_timer * 2.2)))
        shadow = font(size, True).render(self.banner, True, (0, 0, 0))
        shadow.set_alpha(img.get_alpha())
        center = (WIDTH // 2, 200)
        surf.blit(shadow, shadow.get_rect(center=(center[0] + 3, center[1] + 3)))
        surf.blit(img, img.get_rect(center=center))

    def draw_menu(self, surf):
        for i, f in enumerate(self.menu_fighters):
            chosen = i == self.selection
            arch = ROSTER[i]
            if chosen:
                pulse = 32 + math.sin(self.t * 4) * 6
                glow_circle(surf, (f.x, f.y - 46), int(pulse * 1.6),
                            f.secondary, strength=0.55)
                pygame.draw.ellipse(surf, f.secondary,
                                    (f.x - 60, GROUND_Y - 8, 120, 26), 3)
            draw_fighter(surf, f, self.t)

            card = pygame.Rect(f.x - 116, 132, 232, 210)
            panel(surf, card, 200 if chosen else 125,
                  f.secondary if chosen else (66, 70, 94))
            text(surf, arch.name.upper(), (card.centerx, card.y + 22), 30,
                 f.secondary if chosen else DIM, True, center=True)
            text(surf, arch.title, (card.centerx, card.y + 46), 14,
                 GOLD if chosen else (110, 100, 80), True, center=True)
            stat_row(surf, card.x + 20, card.y + 62, "HP", f.max_hp, 400,
                     (96, 214, 130), not chosen)
            stat_row(surf, card.x + 20, card.y + 86, "SPD", arch.speed, 10,
                     (120, 200, 255), not chosen)
            stat_row(surf, card.x + 20, card.y + 110, "PWR", arch.attack, 14,
                     (255, 160, 90), not chosen)

            def fit(msg, limit, start=15):
                s = start
                while s > 10 and font(s).size(msg)[0] > limit:
                    s -= 1
                return s

            text(surf, arch.blurb, (card.centerx, card.y + 136),
                 fit(arch.blurb, card.w - 18), WHITE if chosen else DIM,
                 center=True)
            pygame.draw.line(surf, (70, 74, 100), (card.x + 16, card.y + 154),
                             (card.right - 16, card.y + 154), 1)
            label = f"SUPER  -  {arch.super_name}  {arch.super_time:g}s"
            text(surf, label, (card.centerx, card.y + 172),
                 fit(label, card.w - 18), GOLD if chosen else (110, 100, 80),
                 True, center=True)
            text(surf, arch.super_blurb, (card.centerx, card.y + 192),
                 fit(arch.super_blurb, card.w - 18),
                 WHITE if chosen else DIM, center=True)
            if chosen:
                dip = math.sin(self.t * 5) * 4
                tip = card.y - 8 + dip
                pygame.draw.polygon(surf, GOLD, [
                    (card.centerx - 12, tip - 15), (card.centerx + 12, tip - 15),
                    (card.centerx, tip)])

        text(surf, "ARENA CLASH", (WIDTH // 2, 42), 58, GOLD, True, center=True)
        text(surf, "choose your fighter", (WIDTH // 2, 80), 21, WHITE, center=True)
        text(surf, "A / D to pick     ENTER to choose a style     ESC to quit",
             (WIDTH // 2, 106), 18, DIM, center=True)

        hard = self.difficulty == "hard"
        badge = pygame.Rect(0, 0, 190, 30)
        badge.topright = (WIDTH - 22, 22)
        color = DANGER if hard else (110, 210, 140)
        chip = pygame.Surface(badge.size, pygame.SRCALPHA)
        pygame.draw.rect(chip, (*color, 55), chip.get_rect(), border_radius=8)
        surf.blit(chip, badge.topleft)
        pygame.draw.rect(surf, color, badge, 2, border_radius=8)
        text(surf, f"TAB  -  {self.difficulty.upper()} MODE", badge.center, 16,
             color, True, center=True)
        text(surf, "crouch ducks under shots   -   jumping clears them   -   "
                   "a strike beats a crouch",
             (WIDTH // 2, HEIGHT - 52), 18, (190, 180, 220), center=True)
        text(surf, "each character can be run in any of the three fighting "
                   "styles - and their super changes to suit it",
             (WIDTH // 2, HEIGHT - 26), 17, (150, 156, 185), center=True)

    @staticmethod
    def weapon_line(w):
        """One line of stats for a weapon on the style card."""
        base = f"x{w.multiplier:g} dmg  -  {w.cooldown:g}s cooldown"
        if w.kind == "swing":
            return base + f"  -  reach {int(w.reach)}"
        if w.pellets > 1:
            return base + f"  -  {w.pellets} pellets"
        if w.homing:
            return base + "  -  homing"
        if w.selfharm:
            return base + "  -  gas, hurts you too"
        if w.splash:
            return base + "  -  blast"
        return base

    @staticmethod
    def usage_line(w):
        """The second line: the usage cooldown, when the weapon carries one."""
        if not w.limited:
            return "no usage cooldown"
        if w.uses and w.window:
            return f"USAGE  {w.uses} in {w.window:g}s, lock {w.lockout:g}s"
        if w.uses:
            shots = "shot" if w.uses == 1 else "shots"
            return f"USAGE  {w.uses} {shots}, lock {w.lockout:g}s"
        return f"USAGE  {w.window:g}s live, lock {w.lockout:g}s"

    def draw_style_select(self, surf):
        arch = ROSTER[self.selection]

        def fit(msg, limit, start=15):
            s = start
            while s > 9 and font(s).size(msg)[0] > limit:
                s -= 1
            return s

        text(surf, "CHOOSE YOUR STYLE", (WIDTH // 2, 40), 46, GOLD, True,
             center=True)
        text(surf, f"{arch.name.upper()}  -  {arch.title}", (WIDTH // 2, 76),
             21, arch.secondary, True, center=True)
        text(surf, "A / D to pick     ENTER to fight     BACKSPACE for the roster",
             (WIDTH // 2, 100), 17, DIM, center=True)

        cw, gap = 300, 20
        x0 = WIDTH // 2 - (3 * cw + 2 * gap) // 2
        for i, key in enumerate(STYLE_ORDER):
            st = STYLES[key]
            chosen = i == self.style_index
            card = pygame.Rect(x0 + i * (cw + gap), 116, cw, 362)
            panel(surf, card, 205 if chosen else 130,
                  st.accent if chosen else (66, 70, 94))
            text(surf, st.name, (card.centerx, card.y + 22), 27,
                 st.accent if chosen else DIM, True, center=True)
            text(surf, st.title, (card.centerx, card.y + 46), 13,
                 GOLD if chosen else (110, 100, 80), True, center=True)
            text(surf, st.blurb, (card.centerx, card.y + 66), 14,
                 WHITE if chosen else DIM, center=True)
            pygame.draw.line(surf, (70, 74, 100), (card.x + 14, card.y + 86),
                             (card.right - 14, card.y + 86), 1)

            for j, wkey in enumerate(st.weapons):
                w = WEAPONS[wkey]
                row = card.y + 96 + j * 62
                box = pygame.Rect(card.x + 16, row, 44, 44)
                pygame.draw.rect(surf, (18, 18, 28), box, border_radius=7)
                weapon_icon(surf, box, w, chosen)
                pygame.draw.rect(surf, (70, 72, 96), box, 2, border_radius=7)
                tag = f"{j + 1}  {w.name}"
                if wkey == st.strike_key:
                    tag += "   (J)"
                text(surf, tag, (box.right + 12, row), 17,
                     WHITE if chosen else DIM, True)
                text(surf, self.weapon_line(w), (box.right + 12, row + 19), 12,
                     (172, 178, 206) if chosen else (92, 96, 118))
                line = self.usage_line(w)
                text(surf, line, (box.right + 12, row + 33), 12,
                     ((255, 176, 90) if w.limited else (120, 190, 140))
                     if chosen else (96, 92, 104))

            name, secs, blurb, _kit = arch.super_for(key)
            pygame.draw.line(surf, (70, 74, 100), (card.x + 14, card.y + 284),
                             (card.right - 14, card.y + 284), 1)
            label = f"{arch.name.upper()}'S SUPER  -  {name}  {secs:g}s"
            text(surf, label, (card.centerx, card.y + 300),
                 fit(label, cw - 20), GOLD if chosen else (110, 100, 80),
                 True, center=True)
            text(surf, blurb, (card.centerx, card.y + 324),
                 fit(blurb, cw - 20), WHITE if chosen else DIM, center=True)

            if chosen:
                dip = math.sin(self.t * 5) * 4
                tip = card.y - 8 + dip
                pygame.draw.polygon(surf, GOLD, [
                    (card.centerx - 12, tip - 15), (card.centerx + 12, tip - 15),
                    (card.centerx, tip)])

        text(surf, "the weapon cooldown stops you spamming a slot   -   the "
                   "usage cooldown locks a heavy weapon out once it is spent",
             (WIDTH // 2, HEIGHT - 34), 17, (150, 156, 185), center=True)

    def draw_mode_select(self, surf):
        arch = ROSTER[self.selection]
        style = STYLES[STYLE_ORDER[self.style_index]]
        text(surf, "CHOOSE YOUR MODE", (WIDTH // 2, 40), 46, GOLD, True,
             center=True)
        text(surf, f"{arch.name.upper()}  -  {style.name}", (WIDTH // 2, 76),
             21, style.accent, True, center=True)
        text(surf, "A / D to pick     ENTER to fight     BACKSPACE for styles",
             (WIDTH // 2, 100), 17, DIM, center=True)

        modes = self.modes()
        self.mode_index = min(self.mode_index, len(modes) - 1)
        cw, gap = 300, 20
        x0 = WIDTH // 2 - (len(modes) * cw + (len(modes) - 1) * gap) // 2
        for i, key in enumerate(modes):
            name, tag, blurb = MODES[key]
            chosen = i == self.mode_index
            card = pygame.Rect(x0 + i * (cw + gap), 130, cw, 300)
            panel(surf, card, 205 if chosen else 130,
                  GOLD if chosen else (66, 70, 94))
            text(surf, name, (card.centerx, card.y + 26), 28,
                 GOLD if chosen else DIM, True, center=True)
            text(surf, tag, (card.centerx, card.y + 54), 15,
                 WHITE if chosen else DIM, True, center=True)
            pygame.draw.line(surf, (70, 74, 100), (card.x + 16, card.y + 76),
                             (card.right - 16, card.y + 76), 1)

            lines = self.mode_lines(key)
            for j, line in enumerate(lines):
                text(surf, line, (card.centerx, card.y + 96 + j * 24), 15,
                     (180, 186, 214) if chosen else (92, 96, 118), center=True)

            if key == "boss":
                boss = BOSSES[self.boss_index]
                bx = pygame.Rect(card.x + 22, card.bottom - 92, cw - 44, 70)
                panel(surf, bx, 180 if chosen else 110,
                      boss.secondary if chosen else (66, 70, 94))
                text(surf, boss.name.upper(), (bx.centerx, bx.y + 18), 24,
                     boss.secondary if chosen else DIM, True, center=True)
                text(surf, boss.blurb, (bx.centerx, bx.y + 42), 14,
                     WHITE if chosen else DIM, center=True)
                if chosen:
                    text(surf, "W / S to switch boss",
                         (bx.centerx, bx.bottom + 10), 13, GOLD, center=True)
            else:
                text(surf, blurb, (card.centerx, card.bottom - 46),
                     13, (150, 156, 185) if chosen else (86, 90, 112),
                     center=True)
            if chosen:
                dip = math.sin(self.t * 5) * 4
                tip = card.y - 8 + dip
                pygame.draw.polygon(surf, GOLD, [
                    (card.centerx - 12, tip - 15), (card.centerx + 12, tip - 15),
                    (card.centerx, tip)])

        if not self.boss_unlocked:
            text(surf, "clear a TOURNAMENT run to unlock the boss fights",
                 (WIDTH // 2, HEIGHT - 60), 19, GOLD, True, center=True)
        hard = self.difficulty == "hard"
        text(surf, f"difficulty is {self.difficulty.upper()} - "
                   f"{'bosses hit harder and think faster' if hard else 'a gentler brain across the board'}",
             (WIDTH // 2, HEIGHT - 34), 17, DANGER if hard else (110, 210, 140),
             center=True)

    @staticmethod
    def mode_lines(key):
        if key == "quick":
            return ["one opponent, picked at random",
                    "first to two rounds takes the match",
                    "", "no shop, no gold - just the fight"]
        if key == "tournament":
            return ["three opponents, one round each",
                    "lose a single round and the run ends",
                    "",
                    "a shop between every round:",
                    "gold for flat stats, plus a free",
                    "upgrade card for each of your weapons"]
        return ["one boss, best of three rounds",
                "moves no style in the game has",
                "", "beatable - but it will not be quick"]

    def shop_header(self):
        """What is coming after this rest - the shop serves both modes."""
        if self.mode == "endless":
            if self.stage % ENDLESS_BOSS_EVERY == 0:
                return f"ROUND {self.stage} NEXT  -  BOSS  (x{self.endless_scale():.2f})"
            return f"ROUND {self.stage} NEXT  -  ENEMY x{self.endless_scale():.2f}"
        return f"STAGE {self.stage} OF {TOURNAMENT_STAGES} NEXT"

    def draw_shop(self, surf):
        p = self.player
        text(surf, "REST", (WIDTH // 2, 34), 44, GOLD, True, center=True)
        text(surf, self.shop_header(), (WIDTH // 2, 66), 19, WHITE, True,
             center=True)
        gbox = pygame.Rect(0, 0, 176, 34)
        gbox.topright = (WIDTH - 24, 22)
        panel(surf, gbox, 190, GOLD)
        text(surf, f"{self.gold} GOLD", gbox.center, 21, GOLD, True, center=True)

        # ---- gold shop: flat stats -----------------------------------
        shop = pygame.Rect(30, 96, 290, 250)
        panel(surf, shop, 200, (90, 96, 130))
        text(surf, "SPEND GOLD", (shop.centerx, shop.y + 22), 23, WHITE, True,
             center=True)
        text(surf, "flat stats, they stack all run",
             (shop.centerx, shop.y + 46), 13, DIM, center=True)
        for i, (name, blurb, _b, _s) in enumerate(SHOP_ITEMS):
            row = pygame.Rect(shop.x + 16, shop.y + 70 + i * 58, shop.w - 32, 50)
            price = self.shop_price(i)
            afford = self.gold >= price
            pygame.draw.rect(surf, (20, 20, 30), row, border_radius=7)
            pygame.draw.rect(surf, GOLD if afford else (72, 74, 96), row, 2,
                             border_radius=7)
            text(surf, f"{i + 1}", (row.x + 9, row.y + 5), 15, WHITE, True,
                 shadow=False)
            text(surf, name, (row.x + 30, row.y + 6), 18,
                 WHITE if afford else DIM, True)
            text(surf, blurb, (row.x + 30, row.y + 27), 13,
                 (170, 176, 205) if afford else (86, 90, 112))
            text(surf, f"{price}g", (row.right - 34, row.y + 15), 18,
                 GOLD if afford else (100, 92, 70), True, center=True)
            if self.shop_bought[i]:
                text(surf, f"x{self.shop_bought[i]}", (row.right - 34, row.y + 36),
                     12, DIM, center=True)

        # ---- free upgrade cards --------------------------------------
        # The moon sits right behind this header, so give it its own ground.
        head = pygame.Rect(0, 0, 470, 54)
        head.center = (682, 130)
        panel(surf, head, 195, (90, 96, 130))
        text(surf, "UPGRADE CARDS  -  FREE", (682, 120), 23, WHITE, True,
             center=True)
        text(surf, "one card per weapon, one weapon per rest - take one",
             (682, 143), 14, DIM, center=True)
        cw, gap = 176, 14
        x0 = 682 - (3 * cw + 2 * gap) // 2
        for i, card in enumerate(self.shop_cards):
            chosen = i == self.card_index
            w = WEAPONS[card.weapon]
            box = pygame.Rect(x0 + i * (cw + gap), 162, cw, 184)
            panel(surf, box, 210 if chosen else 130,
                  card.color if chosen else (66, 70, 94))
            text(surf, card.rarity.upper(), (box.centerx, box.y + 16), 15,
                 card.color if chosen else DIM, True, center=True)
            icon = pygame.Rect(box.centerx - 22, box.y + 38, 44, 44)
            pygame.draw.rect(surf, (18, 18, 28), icon, border_radius=7)
            weapon_icon(surf, icon, w, chosen)
            pygame.draw.rect(surf, card.color if chosen else (70, 72, 96), icon,
                             2, border_radius=7)
            text(surf, w.name, (box.centerx, box.y + 92), 16,
                 WHITE if chosen else DIM, True, center=True)
            # wrap the effect onto two lines
            words = card.label.split()
            mid = len(words) // 2 + 1
            text(surf, " ".join(words[:mid]), (box.centerx, box.y + 120), 17,
                 card.color if chosen else (92, 96, 118), True, center=True)
            text(surf, " ".join(words[mid:]), (box.centerx, box.y + 142), 17,
                 card.color if chosen else (92, 96, 118), True, center=True)
            if chosen:
                text(surf, "ENTER to take", (box.centerx, box.bottom - 20), 14,
                     GOLD, True, center=True)

        cost = REROLL_COSTS[min(self.rerolls, len(REROLL_COSTS) - 1)]
        label = "R  -  REROLL (free)" if cost == 0 else f"R  -  REROLL ({cost}g)"
        text(surf, label, (682, 366), 20, GOLD if (not cost or self.gold >= cost)
             else (110, 100, 80), True, center=True)
        text(surf, "the first reroll each rest is free - the next ones climb",
             (682, 390), 13, DIM, center=True)

        if self.shop_msg:
            text(surf, self.shop_msg, (WIDTH // 2, HEIGHT - 76), 19, GOLD,
                 True, center=True)
        text(surf, "1 / 2 / 3 buy     A / D pick a card     R reroll     "
                   "ENTER take it and fight",
             (WIDTH // 2, HEIGHT - 44), 18, (170, 176, 205), center=True)
        # A reminder of what the run has done to your fighter so far.
        text(surf, f"{p.name.upper()}  {p.style.name}   -   "
                   f"{int(p.hp)}/{p.max_hp} HP", (WIDTH // 2, HEIGHT - 20), 15,
             p.style.accent, center=True)

    def draw_continue(self, surf):
        """Offered the moment a tournament run is cleared."""
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((6, 6, 12, 205))
        surf.blit(overlay, (0, 0))
        pulse = 0.6 + 0.4 * math.sin(self.t * 4)
        text(surf, "TOURNAMENT CLEARED", (WIDTH // 2, 62), 52,
             tuple(min(255, int(c * pulse + 60)) for c in GOLD), True, center=True)
        text(surf, f"{self.player.name.upper()} / {self.player.style.name}"
                   f"   -   {self.gold} gold banked   -   keep every upgrade",
             (WIDTH // 2, 104), 20, WHITE, center=True)
        text(surf, "A / D to choose     ENTER to go on     R to stop here and bank it",
             (WIDTH // 2, 132), 17, DIM, center=True)

        cw, gap = 330, 30
        x0 = WIDTH // 2 - (2 * cw + gap) // 2
        for i, key in enumerate(CONTINUE_ORDER):
            name, tag, blurb = MODES[key]
            chosen = i == self.continue_index
            accent = (255, 150, 90) if key == "endless" else DANGER
            card = pygame.Rect(x0 + i * (cw + gap), 168, cw, 250)
            panel(surf, card, 210 if chosen else 130,
                  accent if chosen else (66, 70, 94))
            text(surf, name, (card.centerx, card.y + 30), 34,
                 accent if chosen else DIM, True, center=True)
            text(surf, tag, (card.centerx, card.y + 62), 15,
                 GOLD if chosen else (110, 100, 80), True, center=True)
            pygame.draw.line(surf, (70, 74, 100), (card.x + 18, card.y + 84),
                             (card.right - 18, card.y + 84), 1)
            if key == "endless":
                lines = [
                    "one round at a time, forever",
                    f"every round the enemy is {int((ENDLESS_GROWTH - 1) * 100)}% stronger",
                    "and it compounds, so it will end you",
                    f"a boss every {ENDLESS_BOSS_EVERY} rounds, climbing slower",
                    "shop between every round",
                ]
                if self.best_endless:
                    lines.append(f"your best: round {self.best_endless}")
            else:
                boss = BOSSES[self.boss_index]
                lines = [
                    "straight to the boss, best of three",
                    f"now: {boss.name.upper()} - {boss.title}",
                    boss.blurb,
                    "W / S to switch boss",
                    "no scaling, just the fight",
                ]
            for j, line in enumerate(lines):
                text(surf, line, (card.centerx, card.y + 108 + j * 26), 16,
                     WHITE if chosen else DIM, center=True)
            if chosen:
                dip = math.sin(self.t * 5) * 4
                pygame.draw.polygon(surf, GOLD, [
                    (card.centerx - 12, card.y - 23 + dip),
                    (card.centerx + 12, card.y - 23 + dip),
                    (card.centerx, card.y - 8 + dip)])

        text(surf, "you keep your stats, your upgrade cards and your gold",
             (WIDTH // 2, HEIGHT - 56), 18, (190, 180, 220), center=True)

    def draw_matchend(self, surf):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((6, 6, 12, 195))
        surf.blit(overlay, (0, 0))
        won = self.winner is self.player
        text(surf, "VICTORY" if won else "DEFEAT", (WIDTH // 2, 168), 84,
             GOLD if won else DANGER, True, center=True)
        score = (f"{self.player.rounds_won}-{self.cpu.rounds_won}" if won
                 else f"{self.cpu.rounds_won}-{self.player.rounds_won}")
        text(surf, f"{self.winner.name} takes the match {score}",
             (WIDTH // 2, 238), 28, WHITE, center=True)
        text(surf, f"{self.player.name} vs {self.cpu.name}",
             (WIDTH // 2, 276), 20, DIM, center=True)
        if self.mode == "endless":
            text(surf, f"survived to round {self.best_round}"
                       f"    -    best ever: round {self.best_endless}",
                 (WIDTH // 2, 276), 22, GOLD, True, center=True)
        if self.just_unlocked:
            pulse = 0.6 + 0.4 * math.sin(self.t * 5)
            box = pygame.Rect(0, 0, 470, 52)
            box.center = (WIDTH // 2, 308)
            panel(surf, box, 200, GOLD)
            text(surf, "BOSS FIGHTS UNLOCKED", box.center, 27,
                 tuple(min(255, int(c * pulse + 60)) for c in GOLD), True,
                 center=True)
        text(surf, "R  -  back to fighter select", (WIDTH // 2, 356), 24, DIM,
             center=True)
        text(surf, "ESC  -  quit", (WIDTH // 2, 388), 24, DIM, center=True)

    def draw_pause(self, surf):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((6, 6, 12, 175))
        surf.blit(overlay, (0, 0))
        text(surf, "PAUSED", (WIDTH // 2, 200), 72, WHITE, True, center=True)
        text(surf, "P or ESC to resume     Q to quit to menu",
             (WIDTH // 2, 268), 24, DIM, center=True)
        text(surf, "move A/D   -   jump W/SPACE   -   crouch S   -   strike J   "
                   "-   weapons 1 2 3   -   super Q   -   hold K to shield",
             (WIDTH // 2, 316), 17, (150, 156, 185), center=True)
        if self.player is not None:
            kit = "   -   ".join(
                f"{i + 1} {WEAPONS[k].name}" for i, k in enumerate(self.player.kit))
            text(surf, f"{self.player.style.name}:   {kit}",
                 (WIDTH // 2, 348), 17, self.player.style.accent, center=True)

    # -- loop --------------------------------------------------------------

    def run(self):
        running = True
        while running:
            dt = min(0.05, self.clock.tick(FPS) / 1000.0)
            for event in pygame.event.get():
                if not self.handle_event(event):
                    running = False
            self.update(dt)
            self.draw()


# ------------------------------------------------------------ balance ----
#
# Every number above was settled by running the AI against itself: all nine
# character x style builds, every pairing, both sides of the arena. The last
# pass was 864 matches and landed here.
#
#     build            win%          |  aggregate
#     Max   melee      57.3          |  Andy  50.0    sorcerer  50.9
#     Andy  sorcerer   56.8          |  Bob   49.5    gun       48.8
#     Bob   gun        55.2          |  Max   50.5    melee     50.3
#     Max   sorcerer   48.4          |
#     Andy  melee      47.9          |  Nothing is above 58% or below 45%,
#     Bob   sorcerer   47.4          |  and no character or style is more
#     Bob   melee      45.8          |  than ~2 points off even.
#     Max   gun        45.8          |
#     Andy  gun        45.3          |
#
# The styles are not flat - they form a loop. Melee wants to be on top of
# you, guns want the middle distance, and a sorcerer's control beats anyone
# who has to walk in. Any two are close; who wins depends on who gets their
# range first, which is the point.
#
# FOUR THINGS THAT LOOKED FINE AND WERE NOT
#
# 1. The melee AI read its stand-off distance from a fixed table and parked
#    itself up to 190px away while its longest swing reached 96. It was
#    swinging at air, and the only character it worked for was the one with
#    the longest arms. Deriving the band from the fighter's own reach moved
#    Andy's melee build from 20% to 50% on its own. Any melee number tuned
#    before that fix was measuring the bug.
#
# 2. Giving the melee god the universal J jab on top of their three slots -
#    which is what every other style gets - is not symmetric, it is a free
#    fourth weapon. A melee fighter is always at jab range; a sorcerer
#    almost never is. It put the style at 63-90% against the field.
#
# 3. Bob's health was tuned for a game where every weapon hit for 1.5-2.0x.
#    Rapid low-multiplier weapons turn a fight into a flat damage race, and
#    a flat damage race is decided by raw HP, so he ran at 65%.
#
# 4. Andy is deliberately median on every stat, which is survivable in a
#    spell fight and fatal in a melee one - melee rewards extremes, and he
#    has none. He could not be fixed by buffing his stats, because that
#    lifted his other two styles just as much. It took a melee-only lever:
#    his SURGE drops the reflect shield there and buys weight instead.
#
# To re-check any of this, drive two Brains against each other with the
# window and the particles switched off; a full match runs in about 30ms.

def main():
    try:
        pygame.mixer.pre_init(RATE, -16, 1, 512)
    except pygame.error:
        pass
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass
    build_audio()

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Arena Clash - Andy / Bob / Max")
    Game(screen).run()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
