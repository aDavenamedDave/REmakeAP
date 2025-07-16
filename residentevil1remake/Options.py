from dataclasses import dataclass
from Options import (Choice, OptionList, NamedRange, 
    StartInventoryPool,
    PerGameCommonOptions, DeathLinkMixin)

class Character(Choice):
    """Chris: Punches boulders, pretty solid choice.
    Jill: Might actually be a sandwich, but also a solid choice."""
    display_name = "Character to Play"
    option_chris = 0
    option_jill = 1
    default = 0

class Difficulty(Choice):
    """Normal: idk, normal?
    Easy: Easier than Normal?
    Very Easy: Easier than Easy?"""
    display_name = "Difficulty to Play On"
    option_normal = 0
    option_easy = 1
    option_very_easy = 2
    default = 0

class BonusStart(Choice):
    """Some players might want to start with a little help in the way of a few extra heal items and packs of ammo.

    False: Normal, don't start with extra heal items and packs of ammo.
    True: Start with those helper items."""
    display_name = "Bonus Start"
    option_false = 0
    option_true = 1
    default = 0

class AllowProgressionInLab(Choice):
    """If any progression gets placed in the Underground Laboratory, it can cause some lengthy BK. 
    This option seeks to avoid that.

    False: (Default) The only progression in Laboratory -- and the final fight area(s) -- will be any static progression items that are placed there by RE1R.
    True: Progression can be placed in Laboratory and the final fight area(s). This can, but won't always, lead to some BK.

    NOTE - This option only affects *YOUR* Laboratory. Your progression can still be in someone else's Laboratory if they have this option enabled."""
    display_name = "Allow Progression in Laboratory"
    option_false = 0
    option_true = 1
    default = 0


# making this mixin so we can keep actual game options separate from AP core options that we want enabled
# not sure why this isn't a mixin in core atm, anyways
@dataclass
class StartInventoryFromPoolMixin:
    start_inventory_from_pool: StartInventoryPool

@dataclass
class RE1ROptions(StartInventoryFromPoolMixin, DeathLinkMixin, PerGameCommonOptions):
    character: Character
    difficulty: Difficulty
    bonus_start: BonusStart
    allow_progression_in_lab: AllowProgressionInLab

