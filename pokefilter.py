#!/usr/bin/env python

import urllib.request
import json
from pprint import pprint

from typing import Set
from pydantic import BaseModel

import pytest

from joblib import Memory
memory = Memory("./.pokemon_cache", verbose=False)

#
# Get a list of Pokemon which match some filter critera.
#

class Filter(BaseModel):
    """
    Filter for pokemon attributes.  A passing pokemon must have at least
    one type in the types list, a height in the height range, and experience
    points in the XP range.
    """
    types: Set[str]
    height_range: tuple[int, int]
    xp_range: tuple[int, int]

    def height_in_range(self, height: int) -> bool:
        """
        Return True if the height is in the right range.

        Some pokemon data blobs don't have a height so assume that does not match.
        """
        return height is not None and \
            height >= self.height_range[0] and height <= self.height_range[1]
    
    def xp_in_range(self, xp: int) -> bool:
        """
        Return True if the XP is in the right range

        Some pokemon data blobs don't have a XP so assume that does not match.
        """
        return xp is not None \
            and xp >= self.xp_range[0] and xp <= self.xp_range[1]
    
    def type_matches(self, types:Set[str]) -> bool:
        """
        Return true if at least one element of types is in the set of types this 
        filter is looking for.

        We could use set.intersection() but we don't actually need know the
        matching type, just that there is a match.
        """
        for t in types:
            if t in self.types:
                return True
        
        return False
    
    def matching_types(self, types: Set[str]) -> Set[str]:
        """
        A Pokemaon has many types.  Return a set of only the types which this 
        filter matches.
        """
        return self.types.intersection(types)

def test_Filter_init():
    f = Filter(types={"type"}, height_range=(1, 2), xp_range=(3, 4))
    assert(isinstance(f, Filter))

    # Try creations which should raise exceptions
    try:
        f = Filter(types={"type"}, height_range=("a", 3), xp_range=(1, 3))
        pytest.fail("Failed to detect non-string type in __init__")
    except:
        pass
    
    try:
        f = Filter(types={1}, height_range=(1, 2), xp_range=(3, 4))
        pytest.fail("Failed to detect non-string type in __init__")
    except:
        pass

    try:
        f = Filter(types={"type"}, height_range=("a", 3), xp_range=(1, 3))
        pytest.fail("Failed to detect non-string height in __init__")
    except:
        pass

    try:
        f = Filter(types={"type"}, height_range=(1, 3), xp_range=("a", 3))
        pytest.fail("Failed to detect non-string XP in __init__")
    except:
        pass

    try:
        f = Filter(types={"type"}, height_range=(1), xp_range=(1, 3))
        pytest.fail("Failed to detect only one height in __init__")
    except:
        pass

    try:
        f = Filter({"type"}, (1, 3), (1))
        pytest.fail("Failed to detect only one XP in __init__")
    except:
        pass

def test_height_in_range():
    f = Filter(types={"test"}, height_range=(1, 4), xp_range=(5, 8))
    assert f.height_in_range(1)
    assert f.height_in_range(2)
    assert f.height_in_range(4)
    
    assert f.height_in_range(0) == False
    assert f.height_in_range(5) == False

def test_xp_in_range():
    f = Filter(types={"test"}, height_range=(1, 4), xp_range=(5, 8))
    assert f.xp_in_range(5)
    assert f.xp_in_range(6)
    assert f.xp_in_range(8)

    assert f.xp_in_range(4) == False
    assert f.xp_in_range(9) == False

def test_types_match():
    f = Filter(types={"type1", "type2"}, height_range=(0, 10), xp_range=(0, 10))
    assert f.type_matches({"type1"})
    assert f.type_matches({"type2"})
    assert f.type_matches({"type1", "not-type"})
    assert f.type_matches({"not-type"}) == False

def test_matching_types():
    f = Filter(types={"type1", "type2"}, height_range=(0, 10), xp_range=(0, 10))
    assert f.matching_types({"type1"}) == {"type1"}
    assert f.matching_types({"type2"}) == {"type2"}
    assert f.matching_types({"not-type"}) == set()

    assert f.matching_types({"type1", "type2"}) == {"type1", "type2"}
    assert f.matching_types({"type1", "non-type"}) == {"type1"}

@memory.cache
def query(url: str) -> dict:
    request = urllib.request.Request(url)
    request.add_header('User-Agent',"pokemon test")
    return json.loads(urllib.request.urlopen(request).read())
    
@memory.cache
def query_paged(url: str) -> list:
    """
    Query URL.  Save results element as a list.
    
    If response includes a "next" field, fetch that too.  Keep fetching unil "next" is empty.
    """
    results = []
    while url is not None:
        resp = query(url)
        results.extend(resp["results"])
        url = resp["next"]

    return results

def get_types(pokemon:dict) -> set:
    """
    Return all the types of a given pokemon.
    
    The data is annoyingly formatted.  For each element in pokemon["types"], we 
    want the pokemon["types"][index]["type"]["name"] element.
    """
    return set(t["type"]["name"] for t in pokemon["types"])

def get_pokemon(filter: Filter) -> dict:
    """
    Get Pokemon which match the fiter object.

    Return object is a dict keyed by the Pokemon type.  The value is a list 
    of Pokemon names.
    """

    # Get list of all pokemons
    pokemons = query_paged("https://pokeapi.co/api/v2/pokemon/")

    # Iterate through all pokemons, saving the ones which match the filter
    passing_pokemons = []
    for p in pokemons:
        print(f"Fetching pokemon {p['name']}, {p['url']} ({len(pokemons)})")
        p_data = query(p["url"])

        if filter.xp_in_range(p_data["base_experience"]) \
            and filter.height_in_range(p_data["height"]) \
            and filter.type_matches(get_types(p_data)):
            passing_pokemons.append(p_data)

    # Now we need to aggregate the results.  For every type of each passing pokemon
    # which matches the filter, append the name to type type element of results.
    results = dict()
    for p in passing_pokemons:
        matching_types = filter.matching_types(get_types(p))
        for t in matching_types:
            if t not in results:
                results[t] = []
            results[t].append(p["name"])

    pprint(results)

if __name__ == "__main__":
    filter = Filter(types={"grass", "poison", "electric"}, 
                    height_range=(1, 100), 
                    xp_range=(20, 200))
    pprint(filter)
    get_pokemon(filter=filter)