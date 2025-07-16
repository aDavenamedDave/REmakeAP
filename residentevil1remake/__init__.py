import re
import typing

from typing import Dict, Any, TextIO
from Utils import visualize_regions

from BaseClasses import ItemClassification, Item, Location, Region, CollectionState
from worlds.AutoWorld import World
from ..generic.Rules import set_rule
from Fill import fill_restrictive

from .Data import Data
from .Exceptions import RE1ROptionError
from .Options import RE1ROptions


Data.load_data('chris')
Data.load_data('jill')


class RE1RLocation(Location):
    def stack_names(*area_names):
        return " - ".join(area_names)
    
    def stack_names_not_victory(*area_names):
        if area_names[-1] == "Victory": return area_names[-1]

        return RE1RLocation.stack_names(*area_names)

    def is_item_forbidden(item, location_data, current_item_rule):
        return current_item_rule(item) and ('forbid_item' not in location_data or item.name not in location_data['forbid_item'])


class ResidentEvil1Remake(World):
    """
    'That was too close. You were almost a Jill sandwich!' - Leon S. Kennedy, probably
    """
    game: str = "Resident Evil 1 Remake"

    data_version = 2
    required_client_version = (0, 5, 0)
    apworld_release_version = "0.1.0" # defined to show in spoiler log

    item_id_to_name = { item['id']: item['name'] for item in Data.item_table }
    item_name_to_id = { item['name']: item['id'] for item in Data.item_table }
    item_name_to_item = { item['name']: item for item in Data.item_table }
    location_id_to_name = { loc['id']: RE1RLocation.stack_names(loc['region'], loc['name']) for loc in Data.location_table }
    location_name_to_id = { RE1RLocation.stack_names(loc['region'], loc['name']): loc['id'] for loc in Data.location_table }
    location_name_to_location = { RE1RLocation.stack_names(loc['region'], loc['name']): loc for loc in Data.location_table }
    source_locations = {} # this is used to seed the initial item pool from original items, and is indexed by player as lname:loc locations

    # de-dupe the item names for the item group name
    item_name_groups = { key: set(values) for key, values in Data.item_name_groups.items() }

    options_dataclass = RE1ROptions
    options: RE1ROptions

    def generate_early(self):
        self.source_locations[self.player] = self._get_locations_for_scenario(self._get_character(), self._get_scenario()) # id:loc combo
        self.source_locations[self.player] = { 
            RE1RLocation.stack_names(l['region'], l['name']): { **l, 'id': i } 
                for i, l in self.source_locations[self.player].items() 
        } # turn it into name:loc instead

    def create_regions(self): # and create locations
        scenario_locations = { l['id']: l for _, l in self.source_locations[self.player].items() }
        scenario_regions = self._get_region_table_for_scenario(self._get_character(), self._get_scenario())

        regions = [
            Region(region['name'], self.player, self.multiworld) 
                for region in scenario_regions
        ]
        
        for region in regions:
            region.locations = [
                RE1RLocation(self.player, RE1RLocation.stack_names_not_victory(region.name, location['name']), location['id'], region) 
                    for _, location in scenario_locations.items() if location['region'] == region.name
            ]
            region_data = [scenario_region for scenario_region in scenario_regions if scenario_region['name'] == region.name][0]
            
            for location in region.locations:
                location_data = scenario_locations[location.address]
                
                # if location has an item that should be forced there, place that. for cases where the item to place differs from the original.
                if 'force_item' in location_data and location_data['force_item']:
                    location.place_locked_item(self.create_item(location_data['force_item']))
                # if location is marked not rando'd, place its original item. 
                # if/elif here allows force_item + randomized=0, since a forced item is technically not randomized, but don't need to trigger both.
                elif 'randomized' in location_data and location_data['randomized'] == 0:
                    location.place_locked_item(self.create_item(location_data["original_item"]))
                # if location is not force_item'd or not not randomized, check for Labs progression option and apply
                # since Labs progression option doesn't matter for force_item'd or not randomized locations
                # we check for zone id > 3 because 3 is typically Sewers, and anything beyond that is Labs / endgame stuff
                elif self._format_option_text(self.options.allow_progression_in_lab) == 'False' and region_data['zone_id'] > 3:
                    location.item_rule = lambda item: not item.advancement
                # END if

                if 'forbid_item' in location_data and location_data['forbid_item']:
                    current_item_rule = location.item_rule or None

                    if not current_item_rule:
                        current_item_rule = lambda x: True

                    location.item_rule = lambda item, loc_data=location_data, cur_rule=current_item_rule: RE1RLocation.is_item_forbidden(item, loc_data, cur_rule)

                # now, set rules for the location access
                if "condition" in location_data and "items" in location_data["condition"]:
                    set_rule(location, lambda state, loc=location, loc_data=location_data: self._has_items(state, loc_data["condition"].get("items", [])))

            self.multiworld.regions.append(region)
                
        for connect in self._get_region_connection_table_for_scenario(self._get_character(), self._get_scenario()):
            # skip connecting on a one-sided connection because this should not be reachable backwards (and should be reachable otherwise)
            if 'limitation' in connect and connect['limitation'] in ['ONE_SIDED_DOOR']:
                continue

            from_name = connect['from'] if 'Menu' not in connect['from'] else 'Menu'
            to_name = connect['to'] if 'Menu' not in connect['to'] else 'Menu'

            region_from = self.multiworld.get_region(from_name, self.player)
            region_to = self.multiworld.get_region(to_name, self.player)
            ent = region_from.connect(region_to)

            if "condition" in connect and "items" in connect["condition"]:
                set_rule(ent, lambda state, en=ent, conn=connect: self._has_items(state, conn["condition"].get("items", [])))

        # Uncomment the below to see a connection of the regions (and their locations) for any scenarios you're testing.
        # visualize_regions(self.multiworld.get_region("Menu", self.player), "region_uml")

        # Place victory and set the completion condition for having victory
        self.multiworld.get_location("Victory", self.player) \
            .place_locked_item(self.create_item("Victory"))

        self.multiworld.completion_condition[self.player] = lambda state: self._has_items(state, ['Victory'])

    def create_items(self):
        scenario_locations = self.source_locations[self.player]

        pool = [
            self.create_item(item['name'] if item else None) for item in [
                self.item_name_to_item[location['original_item']] if location.get('original_item') else None
                    for _, location in scenario_locations.items()
            ]
        ]

        pool = [item for item in pool if item is not None] # some of the locations might not have an original item, so might not create an item for the pool

        # remove any already-placed items from the pool (forced items, etc.)
        for filled_location in self.multiworld.get_filled_locations(self.player):
            if filled_location.item.code and filled_location.item in pool: # not id... not address... "code"
                pool.remove(filled_location.item)

        # check the bonus start option and add some heal items and ammo packs as precollected / starting items
        if self._format_option_text(self.options.bonus_start) == 'True':
            count_spray = 3
            count_ammo = 4
            count_grenades = 3
            count_bangs = 3

            for x in range(count_spray): self.multiworld.push_precollected(self.create_item('First Aid Spray'))
            for x in range(count_ammo): self.multiworld.push_precollected(self.create_item('Handgun Magazine'))
            for x in range(count_grenades): self.multiworld.push_precollected(self.create_item('Hand Grenade'))
            for x in range(count_bangs): self.multiworld.push_precollected(self.create_item('Flash Grenade'))


        # if the number of unfilled locations exceeds the count of the pool, fill the remainder of the pool with extra maybe helpful items
        missing_item_count = len(self.multiworld.get_unfilled_locations(self.player)) - len(pool)

        if missing_item_count > 0:
            for x in range(missing_item_count):
                pool.append(self.create_item('Blue Herb'))

        # Make any items that result in a really quick BK either early or local items, so the BK time is reduced
        early_items = {}       
        #early_items["Fuse - Main Hall"] = 1

        for item_name, item_qty in early_items.items():
            if item_qty > 0:
                self.multiworld.early_items[self.player][item_name] = item_qty

        local_items = {}       
        #local_items["Fuse - Main Hall"] = len([i for i in pool if i.name == "Fuse - Main Hall"])

        for item_name, item_qty in local_items.items():
            if item_qty > 0:
                self.options.local_items.value.add(item_name)

        # Check the item count against the location count, and remove items until they match
        extra_items = len(pool) - len(self.multiworld.get_unfilled_locations(self.player))

        for _ in range(extra_items):
            eligible_items = [i for i in pool if i.classification == ItemClassification.filler]

            if len(eligible_items) == 0:
                eligible_items = [i for i in pool if i.name in [self.get_filler_item_name(), "Blue Herb"]]

            if len(eligible_items) == 0:
                eligible_items = [i for i in pool if i.name in ["Handgun Magazine"]]

            if len(eligible_items) == 0: break # no items to remove to match, give up

            pool.remove(eligible_items[0])

        self.multiworld.itempool += pool
    

    ##############
    #
    # Most of the time, you won't need to change anything below here.
    # (Main exception would be when you add different difficulties.)
    #
    ##############


    def create_item(self, item_name: str) -> Item:
        if not item_name: return
        if not isinstance(item_name, str):
            print(item_name) 

        item = self.item_name_to_item[item_name]

        if item.get('progression', False):
            classification = ItemClassification.progression
        elif item.get('type', None) not in ['Lore', 'Trap']:
            classification = ItemClassification.useful
        elif item.get('type', None) == 'Trap':
            classification = ItemClassification.trap
        else: # it's Lore
            classification = ItemClassification.filler

        new_item = Item(item['name'], classification, item['id'], player=self.player)
        return new_item

    def get_filler_item_name(self) -> str:
        return "Empty Bottle"

    def fill_slot_data(self) -> Dict[str, Any]:
        slot_data = {
            "apworld_version": self.apworld_release_version,
            "character": self._get_character(),
            "difficulty": self._get_difficulty(),
            "death_link": self._format_option_text(self.options.death_link) == 'Yes' # why is this yes? lol
        }

        return slot_data
    
    def write_spoiler_header(self, spoiler_handle: TextIO):
        spoiler_handle.write(f"RE1R_AP_World version: {self.apworld_release_version}\n")

    def _has_items(self, state: CollectionState, item_names: list) -> bool:
        # if there are no item requirements, this location is open, they "have the items needed"
        if len(item_names) == 0:
            return True

        # if the requirements are a single set of items, make it a list of a single set of items to support looping for multiple sets (below)
        if len(item_names) > 0 and type(item_names[0]) is not list:
            item_names = [item_names]

        for set_of_requirements in item_names:
            # if it requires all unique items, just do a state has all
            if len(set(set_of_requirements)) == len(set_of_requirements):
                if state.has_all(set_of_requirements, self.player):
                    return True
            # else, it requires some duplicates, so let's group them up and do some has w/ counts
            else:
                item_counts = {
                    item_name: len([i for i in set_of_requirements if i == item_name]) for item_name in set_of_requirements # e.g., { Spare Key: 2 }
                }
                missing_an_item = False

                for item_name, count in item_counts.items():
                    if not state.has(item_name, self.player, count):
                        missing_an_item = True

                if missing_an_item:
                    continue # didn't meet these requirements, so skip to the next set, if any
                
                # if we made it here, state has all the items and the quantities needed, return True
                return True

        # if we made it here, state didn't have enough to return True, so return False
        return False

    def _format_option_text(self, option) -> str:
        return re.sub(r'\w+\(', '', str(option)).rstrip(')')
    
    def _get_locations_for_scenario(self, character, scenario) -> dict:
        locations_pool = {
            loc['id']: loc for _, loc in self.location_name_to_location.items()
                if loc['character'] == character and loc['scenario'] == scenario
        }

        # if the player chose hardcore, take out any matching standard difficulty locations
        if self._format_option_text(self.options.difficulty) == 'Hardcore':
            for hardcore_loc in [loc for loc in locations_pool.values() if loc['difficulty'] == 'hardcore']:
                check_loc_region = re.sub(r'H\)$', ')', hardcore_loc['region']) # take the Hardcore off the region name
                check_loc_name = hardcore_loc['name']

                # if there's a standard location with matching name and region, it's obsoleted in hardcore, remove it
                standard_locs = [id for id, loc in locations_pool.items() if loc['region'] == check_loc_region and loc['name'] == check_loc_name and loc['difficulty'] != 'hardcore']

                if len(standard_locs) > 0:
                    del locations_pool[standard_locs[0]]

        # else, the player is still playing standard, take out all of the matching hardcore difficulty locations
        else:
            locations_pool = {
                id: loc for id, loc in locations_pool.items() if loc['difficulty'] != 'hardcore'
            }

        # now that we've factored in hardcore swaps, remove any hardcore locations that were just there for removing unused standard ones
        locations_pool = { id: loc for id, loc in locations_pool.items() if 'remove' not in loc }
        
        return locations_pool

    def _get_region_table_for_scenario(self, character, scenario) -> list:
        return [
            region for region in Data.region_table 
                if region['character'] == character and region['scenario'] == scenario
        ]
    
    def _get_region_connection_table_for_scenario(self, character, scenario) -> list:
        return [
            conn for conn in Data.region_connections_table
                if conn['character'] == character and conn['scenario'] == scenario
        ]
    
    def _get_character(self) -> str:
        return self._format_option_text(self.options.character).lower()
    
    def _get_scenario(self) -> str:
        # preserving scenario in case it's ever used later, in which case this function can be updated
        # don't forget to restructure the data folders and update the data folder structure to support any changes here

        return "a"; 
    
    def _get_difficulty(self) -> str:
        return self._format_option_text(self.options.difficulty).lower()
    
    def _replace_pool_item_with(self, pool, from_item_name, to_item_name) -> list:
        items_to_remove = [item for item in pool if item.name == from_item_name]
        count_of_new_items = len(items_to_remove)

        for item in items_to_remove:
            pool.remove(item)

        for x in range(count_of_new_items):
            pool.append(self.create_item(to_item_name))

        return pool
       
    # def _output_items_and_locations_as_text(self):
    #     my_locations = [
    #         {
    #             'id': loc.address,
    #             'name': loc.name,
    #             'original_item': self.location_name_to_location[loc.name]['original_item'] if loc.name != "Victory" else "(Game Complete)"
    #         } for loc in self.multiworld.get_locations() if loc.player == self.player
    #     ]

    #     my_locations = set([
    #         "{} | {} | {}".format(loc['id'], loc['name'], loc['original_item'])
    #         for loc in my_locations
    #     ])
        
    #     my_items = [
    #         {
    #             'id': item.code,
    #             'name': item.name
    #         } for item in self.multiworld.get_items() if item.player == self.player
    #     ]

    #     my_items = set([
    #         "{} | {}".format(item['id'], item['name'])
    #         for item in my_items
    #     ])

    #     print("\n".join(sorted(my_locations)))
    #     print("\n".join(sorted(my_items)))

    #     raise BaseException("Done with debug output.")
