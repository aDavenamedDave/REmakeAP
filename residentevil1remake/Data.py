import json
import os
import pkgutil

# blatantly copied from the minecraft ap world because why not
def load_data_file(*args) -> dict:
    data_directory = "data"
    fname = os.path.join(data_directory, *args)

    try:
        filedata = json.loads(pkgutil.get_data(__name__, fname).decode())
    except:
        filedata = []

    return filedata

class Data:
    item_table = []
    location_table = []
    region_table = []
    region_connections_table = []

    item_name_groups = {}

    def load_data(character):
        character_offsets = { 'chris': 0, 'jill': 1000 }        
        scenario = "a"
        scenario_offsets = { 'a': 0 }
        hardcore_offset = 400 # put all hardcore-only locations in the last 100 location spots for each scenario
        scenario_suffix = ' ({})'.format(character[0].upper())
        scenario_suffix_hardcore = ' ({}H)'.format(character[0].upper()) # makes hardcore location variations unique

        location_start = item_start = 3000000000 + character_offsets[character] + scenario_offsets[scenario]

        ###
        # Add standard regions
        ###

        new_region_table = load_data_file(character, 'regions.json')
        Data.region_table.extend([
            {
                **reg,
                'name': reg['name'] + scenario_suffix if reg['name'] != 'Menu' else reg['name'], # add the scenario abbreviation so they're unique
                'character': character,
                'scenario': scenario
            }
            for reg in new_region_table
        ])

        ###
        # Add hardcore regions, if applicable
        ###

        hardcore_locations_table = load_data_file(character, 'locations_hardcore.json')
        hardcore_regions = set([loc['region'] for loc in hardcore_locations_table])

        if len(hardcore_regions) > 0:
            Data.region_table.extend([
                {
                    'name': reg + scenario_suffix_hardcore, # add the scenario abbreviation so they're unique
                    'character': character,
                    'scenario': scenario,
                    'zone_id': [regular['zone_id'] for regular in new_region_table if regular['name'] == reg][0]
                }
                for reg in hardcore_regions # instead of using region definitions, we're using the hardcore region additions from the locations themselves
            ])

        ###
        # Add standard region connections
        ###

        added_connections = []
        new_region_connections_table = load_data_file(character, 'region_connections.json')

        for conn in new_region_connections_table:
            connection_path = f"{conn['from'] + scenario_suffix} to {conn['to'] + scenario_suffix}"

            if connection_path in added_connections:
                continue

            added_connections.append(connection_path)

            Data.region_connections_table.append(
                {
                    **conn,
                    'from': conn['from'] + scenario_suffix if conn['from'] != 'Menu' else conn['from'], # add the scenario abbreviation so they're unique
                    'to': conn['to'] + scenario_suffix if conn['to'] != 'Menu' else conn['to'], # add the scenario abbreviation so they're unique
                    'character': character,
                    'scenario': scenario
                }
            )

        ###
        # Add hardcore region connections
        ###

        # not a typo. if we loaded hardcore regions, we need to generate hardcore region connections as well
        if len(hardcore_regions) > 0:
            for conn in new_region_connections_table:
                if conn['from'] in hardcore_regions or conn['to'] in hardcore_regions:
                    suffix_from = scenario_suffix_hardcore if conn['from'] in hardcore_regions else scenario_suffix
                    suffix_to = scenario_suffix_hardcore if conn['to'] in hardcore_regions else scenario_suffix

                    connection_from_name = conn['from'] + suffix_from
                    connection_to_name = conn['to'] + suffix_to
                    connection_path = f"{connection_from_name} to {connection_to_name}"

                    if connection_path in added_connections:
                        continue

                    added_connections.append(connection_path)

                    new_region_connection = {
                        **conn,
                        'from': connection_from_name, 
                        'to': connection_to_name, 
                        'character': character,
                        'scenario': scenario    
                    }

                    Data.region_connections_table.append(new_region_connection)

        ###
        # Add item table for all difficulties
        ###
        
        new_item_table = load_data_file(character, 'items.json')
        Data.item_table.extend([
            { 
                **item, 
                'id': item['id'] if item.get('id') else item_start + key
            } 
            for key, item in enumerate(new_item_table)
        ])

        # For the items that have groups, add them to the item group names
        new_items_with_groups = [item for _, item in enumerate(new_item_table) if "groups" in item.keys()]

        for item_with_group in new_items_with_groups:
            item_name = item_with_group["name"]
            group_names = item_with_group["groups"]

            for group_name in group_names:
                if group_name not in Data.item_name_groups.keys():
                    Data.item_name_groups[group_name] = []

                Data.item_name_groups[group_name].append(item_name)

        ###
        # Add standard location table
        ###

        new_location_table = load_data_file(character, 'locations.json')
        Data.location_table.extend([
            { 
                **loc, 
                'id': loc['id'] if loc.get('id') else location_start + key,
                'region': loc['region'] + scenario_suffix, # add the scenario abbreviation so they're unique
                'character': character,
                'scenario': scenario,
                'difficulty': None
            }
            for key, loc in enumerate(new_location_table)
        ])

        ###
        # Add hardcore locations
        ###

        hardcore_location_table = load_data_file(character, 'locations_hardcore.json')

        if len(hardcore_location_table) > 0:
            Data.location_table.extend([
                { 
                    **loc, 
                    'id': loc['id'] if loc.get('id') else location_start + key + hardcore_offset,
                    'region': loc['region'] + scenario_suffix_hardcore, # add the scenario abbreviation so they're unique
                    'character': character,
                    'scenario': scenario,
                    'difficulty': 'hardcore'
                }
                for key, loc in enumerate(hardcore_location_table)
            ])
