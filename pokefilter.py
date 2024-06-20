#!/usr/bin/env python

import urllib.request
import json
from pprint import pprint

import pytest

from joblib import Memory
memory = Memory("./.pokemon_cache", verbose=False)

#
# Get a list of Pokemon which match some filter critera.
#

class Filter:
    def __init__(self, types: set, height_range: tuple, xp_range: tuple) -> None:
        """
        Create the Pokemon filter. 
         - types is a list of type names
         - height_range is a pair of heights, inclusive, of desired Pokemon
         - xp_range is also a pair of XP, inclusive, of desired experience points
        """
        assert(isinstance(types, set))
        assert(isinstance(height_range, tuple))
        assert(isinstance(xp_range, tuple))

        assert(len(types) > 0)
        assert(len(height_range) == 2)
        assert(len(xp_range) == 2)

        assert(isinstance(str, x) for x in types)
        assert(isinstance(int, x) for x in height_range)
        assert(isinstance(int, x) for x in xp_range)

        self.types = types
        self.height_range = height_range
        self.xp_range = xp_range

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
    
    def type_matches(self, types:set) -> bool:
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
    
    def matching_types(self, types: set) -> set:
        """
        A Pokemaon has many types.  Return a set of only the types which this 
        filter matches.
        """
        return self.types.intersection(types)

def test_Filter_init():
    f = Filter({"type"}, (1, 2), (3, 4))
    assert(isinstance(f, Filter))

    # Try creations which should raise exceptions
    try:
        f = Filter({"type"}, ("a", 3), (1, 3))
        pytest.fail("Failed to detect non-string type in __init__")
    except:
        pass
    
    try:
        f = Filter({1}, (1, 2), (3, 4))
        pytest.fail("Failed to detect non-string type in __init__")
    except:
        pass

    try:
        f = Filter({"type"}, ("a", 3), (1, 3))
        pytest.fail("Failed to detect non-string height in __init__")
    except:
        pass

    try:
        f = Filter({"type"}, (1, 3), ("a", 3))
        pytest.fail("Failed to detect non-string XP in __init__")
    except:
        pass

    try:
        f = Filter({"type"}, (1), (1, 3))
        pytest.fail("Failed to detect only one height in __init__")
    except:
        pass

    try:
        f = Filter({"type"}, (1, 3), (1))
        pytest.fail("Failed to detect only one XP in __init__")
    except:
        pass

def test_height_in_range():
    f = Filter({"test"}, (1, 4), (5, 8))
    assert f.height_in_range(1)
    assert f.height_in_range(2)
    assert f.height_in_range(4)
    
    assert f.height_in_range(0) == False
    assert f.height_in_range(5) == False

def test_xp_in_range():
    f = Filter({"test"}, (1, 4), (5, 8))
    assert f.xp_in_range(5)
    assert f.xp_in_range(6)
    assert f.xp_in_range(8)

    assert f.xp_in_range(4) == False
    assert f.xp_in_range(9) == False

def test_types_match():
    f = Filter({"type1", "type2"}, (0, 10), (0, 10))
    assert f.type_matches({"type1"})
    assert f.type_matches({"type2"})
    assert f.type_matches({"type1", "not-type"})
    assert f.type_matches({"not-type"}) == False

def test_matching_types():
    f = Filter({"type1", "type2"}, (0, 10), (0, 10))
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

get_pokemon(Filter({"grass", "poison", "electric"}, (1, 100), (20, 200)))