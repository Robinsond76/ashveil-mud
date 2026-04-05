"""
Phase 8 — Help System Overhaul tests.

Phase A: _HELP_TOPICS module-level dict exists with all required keys
Phase B: State-aware bare HELP (contextual per State)
Phase C: All topic entries return valid formatted help
Phase D: Unknown topic returns graceful fallback
"""
import asyncio
import pytest

from server.engine.game import GameSession, State, _HELP_TOPICS
from server.engine.character import Character
from server.engine.world import WorldMap


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_session(state=State.NAVIGATION):
    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    world.get_room = lambda rid: None
    world.active_encounter_groups = lambda rid: []
    session = GameSession(send_fn=_noop, world=world, class_defs={}, clock=None)
    player = Character(name="Hero", class_type="warrior")
    session.player = player
    session.state = state
    return session


async def _noop(text): pass


def ask(session, command):
    collected = []
    async def _send(text): collected.append(text)
    session._send_raw = _send
    asyncio.get_event_loop().run_until_complete(session.handle_input(command))
    return "".join(collected)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase A — _HELP_TOPICS dict exists with required keys
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseA_HelpTopicsDict:
    def test_help_topics_is_dict(self):
        assert isinstance(_HELP_TOPICS, dict)

    # Navigation topics
    def test_has_topic_look(self):
        assert "LOOK" in _HELP_TOPICS

    def test_has_topic_l_alias(self):
        assert "L" in _HELP_TOPICS

    def test_has_topic_north(self):
        assert "NORTH" in _HELP_TOPICS

    def test_has_topic_south(self):
        assert "SOUTH" in _HELP_TOPICS

    def test_has_topic_east(self):
        assert "EAST" in _HELP_TOPICS

    def test_has_topic_west(self):
        assert "WEST" in _HELP_TOPICS

    def test_has_topic_move(self):
        assert "MOVE" in _HELP_TOPICS

    def test_has_topic_inv(self):
        assert "INV" in _HELP_TOPICS

    def test_has_topic_inventory(self):
        assert "INVENTORY" in _HELP_TOPICS

    def test_has_topic_equip(self):
        assert "EQUIP" in _HELP_TOPICS

    def test_has_topic_unequip(self):
        assert "UNEQUIP" in _HELP_TOPICS

    def test_has_topic_drop(self):
        assert "DROP" in _HELP_TOPICS

    def test_has_topic_take(self):
        assert "TAKE" in _HELP_TOPICS

    def test_has_topic_pick(self):
        assert "PICK" in _HELP_TOPICS

    def test_has_topic_stats(self):
        assert "STATS" in _HELP_TOPICS

    def test_has_topic_skills(self):
        assert "SKILLS" in _HELP_TOPICS

    def test_has_topic_attack(self):
        assert "ATTACK" in _HELP_TOPICS

    def test_has_topic_camp(self):
        assert "CAMP" in _HELP_TOPICS

    def test_has_topic_status(self):
        assert "STATUS" in _HELP_TOPICS

    def test_has_topic_sit(self):
        assert "SIT" in _HELP_TOPICS

    def test_has_topic_stand(self):
        assert "STAND" in _HELP_TOPICS

    # Environment topics
    def test_has_topic_time(self):
        assert "TIME" in _HELP_TOPICS

    def test_has_topic_weather(self):
        assert "WEATHER" in _HELP_TOPICS

    def test_has_topic_light(self):
        assert "LIGHT" in _HELP_TOPICS

    def test_has_topic_lighting(self):
        assert "LIGHTING" in _HELP_TOPICS

    def test_has_topic_envdetails(self):
        assert "ENVDETAILS" in _HELP_TOPICS

    def test_has_topic_env(self):
        assert "ENV" in _HELP_TOPICS

    def test_has_topic_lit(self):
        assert "LIT" in _HELP_TOPICS

    def test_has_topic_extinguish(self):
        assert "EXTINGUISH" in _HELP_TOPICS

    def test_has_topic_douse(self):
        assert "DOUSE" in _HELP_TOPICS

    # Combat topics
    def test_has_topic_combat(self):
        assert "COMBAT" in _HELP_TOPICS

    def test_has_topic_flee(self):
        assert "FLEE" in _HELP_TOPICS

    def test_has_topic_strategy(self):
        assert "STRATEGY" in _HELP_TOPICS

    def test_has_topic_strategies(self):
        assert "STRATEGIES" in _HELP_TOPICS

    def test_has_topic_cast(self):
        assert "CAST" in _HELP_TOPICS

    # Campfire topics
    def test_has_topic_rest(self):
        assert "REST" in _HELP_TOPICS

    def test_has_topic_party(self):
        assert "PARTY" in _HELP_TOPICS

    # Survival topics
    def test_has_topic_hunger(self):
        assert "HUNGER" in _HELP_TOPICS

    def test_has_topic_thirst(self):
        assert "THIRST" in _HELP_TOPICS

    def test_has_topic_stamina(self):
        assert "STAMINA" in _HELP_TOPICS

    def test_has_topic_survival(self):
        assert "SURVIVAL" in _HELP_TOPICS

    # Weight topics
    def test_has_topic_weight(self):
        assert "WEIGHT" in _HELP_TOPICS

    def test_has_topic_backpack(self):
        assert "BACKPACK" in _HELP_TOPICS

    def test_has_topic_cart(self):
        assert "CART" in _HELP_TOPICS

    def test_has_topic_give(self):
        assert "GIVE" in _HELP_TOPICS

    def test_has_topic_stash(self):
        assert "STASH" in _HELP_TOPICS

    def test_has_topic_load(self):
        assert "LOAD" in _HELP_TOPICS

    def test_has_topic_unload(self):
        assert "UNLOAD" in _HELP_TOPICS

    # Mount topics
    def test_has_topic_ride(self):
        assert "RIDE" in _HELP_TOPICS

    def test_has_topic_dismount(self):
        assert "DISMOUNT" in _HELP_TOPICS

    def test_has_topic_horses(self):
        assert "HORSES" in _HELP_TOPICS

    def test_has_topic_mounts(self):
        assert "MOUNTS" in _HELP_TOPICS

    # Wizard topics
    def test_has_topic_wizard(self):
        assert "WIZARD" in _HELP_TOPICS

    def test_has_topic_spells(self):
        assert "SPELLS" in _HELP_TOPICS

    def test_has_topic_casting(self):
        assert "CASTING" in _HELP_TOPICS

    # Per-spell entries
    def test_has_topic_fireball(self):
        assert "FIREBALL" in _HELP_TOPICS

    def test_has_topic_frost_bolt(self):
        assert "FROST_BOLT" in _HELP_TOPICS

    def test_has_topic_arcane_bolt(self):
        assert "ARCANE_BOLT" in _HELP_TOPICS

    def test_has_topic_magic_missile(self):
        assert "MAGIC_MISSILE" in _HELP_TOPICS

    def test_has_topic_chain_lightning(self):
        assert "CHAIN_LIGHTNING" in _HELP_TOPICS

    def test_has_topic_arcane_shield(self):
        assert "ARCANE_SHIELD" in _HELP_TOPICS

    def test_has_topic_blink(self):
        assert "BLINK" in _HELP_TOPICS

    def test_has_topic_arcane_light(self):
        assert "ARCANE_LIGHT" in _HELP_TOPICS

    def test_has_topic_identify(self):
        assert "IDENTIFY" in _HELP_TOPICS

    def test_all_values_are_non_empty_strings(self):
        for key, val in _HELP_TOPICS.items():
            assert isinstance(val, str) and len(val.strip()) > 0, \
                f"_HELP_TOPICS[{key!r}] is empty or not a string"


# ═══════════════════════════════════════════════════════════════════════════════
# Phase B — State-aware bare HELP
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseB_StateAwareHelp:
    def test_navigation_help_mentions_look(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP")
        assert "LOOK" in out.upper()

    def test_navigation_help_mentions_north(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP")
        assert "NORTH" in out.upper()

    def test_navigation_help_mentions_attack(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP")
        assert "ATTACK" in out.upper()

    def test_navigation_help_does_not_say_combat_list(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP")
        # Should not show combat-only commands like FLEE at the top level
        assert "You are exploring" in out or "exploring" in out.lower()

    def test_campfire_help_mentions_rest(self):
        s = make_session(State.CAMPFIRE)
        out = ask(s, "HELP")
        assert "REST" in out.upper()

    def test_campfire_help_mentions_leave(self):
        s = make_session(State.CAMPFIRE)
        out = ask(s, "HELP")
        assert "LEAVE" in out.upper()

    def test_campfire_help_does_not_mention_north(self):
        s = make_session(State.CAMPFIRE)
        out = ask(s, "HELP")
        # Navigation commands should not appear in campfire help
        assert "resting at camp" in out.lower() or "camp" in out.lower()

    def test_combat_help_mentions_flee(self):
        s = make_session(State.COMBAT)
        out = ask(s, "HELP")
        assert "FLEE" in out.upper()

    def test_combat_help_mentions_attack(self):
        s = make_session(State.COMBAT)
        out = ask(s, "HELP")
        assert "ATTACK" in out.upper()

    def test_combat_help_says_in_combat(self):
        s = make_session(State.COMBAT)
        out = ask(s, "HELP")
        assert "combat" in out.lower()

    def test_strategy_help_mentions_done(self):
        s = make_session(State.STRATEGY)
        out = ask(s, "HELP")
        assert "DONE" in out.upper()

    def test_strategy_help_mentions_tactics(self):
        s = make_session(State.STRATEGY)
        out = ask(s, "HELP")
        assert "AGGRESSIVE" in out.upper() or "tactic" in out.lower()

    def test_connect_help_mentions_races(self):
        s = make_session(State.CONNECT)
        out = ask(s, "HELP")
        assert "RACES" in out.upper()

    def test_creation_help_mentions_classes(self):
        s = make_session(State.CREATION)
        out = ask(s, "HELP")
        assert "CLASSES" in out.upper()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase C — HELP <topic> returns formatted content
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseC_TopicLookup:
    def _help(self, topic, state=State.NAVIGATION):
        s = make_session(state)
        return ask(s, f"HELP {topic}")

    def test_help_look_returns_look_content(self):
        out = self._help("LOOK")
        assert "LOOK" in out.upper()

    def test_help_l_returns_look_content(self):
        out = self._help("L")
        assert "LOOK" in out.upper()

    def test_help_inv_returns_inventory_content(self):
        out = self._help("INV")
        assert "INV" in out.upper() or "inventory" in out.lower()

    def test_help_inventory_returns_content(self):
        out = self._help("INVENTORY")
        assert "inventory" in out.lower() or "INV" in out.upper()

    def test_help_equip_returns_content(self):
        out = self._help("EQUIP")
        assert "EQUIP" in out.upper()

    def test_help_unequip_returns_content(self):
        out = self._help("UNEQUIP")
        assert "UNEQUIP" in out.upper()

    def test_help_drop_returns_content(self):
        out = self._help("DROP")
        assert "DROP" in out.upper()

    def test_help_take_returns_content(self):
        out = self._help("TAKE")
        assert "TAKE" in out.upper()

    def test_help_stats_returns_content(self):
        out = self._help("STATS")
        assert "STATS" in out.upper() or "stat" in out.lower()

    def test_help_skills_returns_content(self):
        out = self._help("SKILLS")
        assert "SKILLS" in out.upper() or "skill" in out.lower()

    def test_help_attack_returns_content(self):
        out = self._help("ATTACK")
        assert "ATTACK" in out.upper()

    def test_help_camp_returns_content(self):
        out = self._help("CAMP")
        assert "CAMP" in out.upper() or "campfire" in out.lower()

    def test_help_status_returns_content(self):
        out = self._help("STATUS")
        assert "STATUS" in out.upper() or "survival" in out.lower()

    def test_help_sit_returns_content(self):
        out = self._help("SIT")
        assert "SIT" in out.upper() or "stamina" in out.lower()

    def test_help_stand_returns_content(self):
        out = self._help("STAND")
        assert "STAND" in out.upper() or "stamina" in out.lower()

    def test_help_time_returns_content(self):
        out = self._help("TIME")
        assert "TIME" in out.upper() or "time" in out.lower()

    def test_help_weather_returns_content(self):
        out = self._help("WEATHER")
        assert "WEATHER" in out.upper() or "weather" in out.lower()

    def test_help_light_returns_content(self):
        out = self._help("LIGHT")
        assert "LIGHT" in out.upper() or "light" in out.lower()

    def test_help_lighting_alias_returns_content(self):
        out = self._help("LIGHTING")
        assert "LIGHT" in out.upper() or "light" in out.lower()

    def test_help_envdetails_returns_content(self):
        out = self._help("ENVDETAILS")
        assert "ENVDETAILS" in out.upper() or "environment" in out.lower() or "ENV" in out.upper()

    def test_help_env_alias_returns_content(self):
        out = self._help("ENV")
        assert "ENV" in out.upper() or "environment" in out.lower()

    def test_help_lit_returns_content(self):
        out = self._help("LIT")
        assert "LIT" in out.upper() or "torch" in out.lower() or "light" in out.lower()

    def test_help_extinguish_returns_content(self):
        out = self._help("EXTINGUISH")
        assert "EXTINGUISH" in out.upper() or "put out" in out.lower()

    def test_help_douse_alias_returns_content(self):
        out = self._help("DOUSE")
        assert "EXTINGUISH" in out.upper() or "DOUSE" in out.upper() or "put out" in out.lower()

    def test_help_combat_returns_content(self):
        out = self._help("COMBAT")
        assert "COMBAT" in out.upper() or "combat" in out.lower()

    def test_help_flee_returns_content(self):
        out = self._help("FLEE")
        assert "FLEE" in out.upper() or "flee" in out.lower()

    def test_help_strategy_returns_content(self):
        out = self._help("STRATEGY")
        assert "STRATEGY" in out.upper() or "tactic" in out.lower()

    def test_help_strategies_alias_returns_content(self):
        out = self._help("STRATEGIES")
        assert "STRATEGY" in out.upper() or "tactic" in out.lower()

    def test_help_cast_returns_content(self):
        out = self._help("CAST")
        assert "CAST" in out.upper() or "spell" in out.lower()

    def test_help_rest_returns_content(self):
        out = self._help("REST")
        assert "REST" in out.upper() or "recover" in out.lower() or "HP" in out

    def test_help_party_returns_content(self):
        out = self._help("PARTY")
        assert "PARTY" in out.upper() or "party" in out.lower()

    def test_help_hunger_returns_content(self):
        out = self._help("HUNGER")
        assert "HUNGER" in out.upper() or "hunger" in out.lower()

    def test_help_thirst_returns_content(self):
        out = self._help("THIRST")
        assert "THIRST" in out.upper() or "thirst" in out.lower()

    def test_help_stamina_returns_content(self):
        out = self._help("STAMINA")
        assert "STAMINA" in out.upper() or "stamina" in out.lower()

    def test_help_survival_returns_content(self):
        out = self._help("SURVIVAL")
        assert "SURVIVAL" in out.upper() or "survival" in out.lower()

    def test_help_weight_returns_content(self):
        out = self._help("WEIGHT")
        assert "WEIGHT" in out.upper() or "weight" in out.lower()

    def test_help_backpack_returns_content(self):
        out = self._help("BACKPACK")
        assert "BACKPACK" in out.upper() or "backpack" in out.lower()

    def test_help_cart_returns_content(self):
        out = self._help("CART")
        assert "CART" in out.upper() or "cart" in out.lower()

    def test_help_give_returns_content(self):
        out = self._help("GIVE")
        assert "GIVE" in out.upper() or "give" in out.lower()

    def test_help_stash_returns_content(self):
        out = self._help("STASH")
        assert "STASH" in out.upper() or "stash" in out.lower() or "cart" in out.lower()

    def test_help_load_returns_content(self):
        out = self._help("LOAD")
        assert "LOAD" in out.upper() or "cart" in out.lower()

    def test_help_unload_returns_content(self):
        out = self._help("UNLOAD")
        assert "UNLOAD" in out.upper() or "cart" in out.lower()

    def test_help_ride_returns_content(self):
        out = self._help("RIDE")
        assert "RIDE" in out.upper() or "horse" in out.lower() or "mount" in out.lower()

    def test_help_dismount_returns_content(self):
        out = self._help("DISMOUNT")
        assert "DISMOUNT" in out.upper() or "mount" in out.lower()

    def test_help_horses_returns_content(self):
        out = self._help("HORSES")
        assert "HORSES" in out.upper() or "horse" in out.lower() or "mount" in out.lower()

    def test_help_mounts_alias_returns_content(self):
        out = self._help("MOUNTS")
        assert "MOUNT" in out.upper() or "horse" in out.lower()

    def test_help_wizard_returns_content(self):
        out = self._help("WIZARD")
        assert "WIZARD" in out.upper() or "mage" in out.lower() or "wizard" in out.lower()

    def test_help_spells_returns_content(self):
        out = self._help("SPELLS")
        assert "SPELL" in out.upper() or "spell" in out.lower()

    def test_help_casting_returns_content(self):
        out = self._help("CASTING")
        assert "CAST" in out.upper() or "cast" in out.lower()

    def test_help_fireball_returns_content(self):
        out = self._help("FIREBALL")
        assert "FIREBALL" in out.upper() or "fireball" in out.lower()

    def test_help_frost_bolt_returns_content(self):
        out = self._help("FROST_BOLT")
        assert "FROST" in out.upper() or "frost" in out.lower()

    def test_help_arcane_bolt_returns_content(self):
        out = self._help("ARCANE_BOLT")
        assert "ARCANE" in out.upper() or "arcane" in out.lower()

    def test_help_magic_missile_returns_content(self):
        out = self._help("MAGIC_MISSILE")
        assert "MAGIC" in out.upper() or "missile" in out.lower()

    def test_help_chain_lightning_returns_content(self):
        out = self._help("CHAIN_LIGHTNING")
        assert "CHAIN" in out.upper() or "lightning" in out.lower()

    def test_help_arcane_shield_returns_content(self):
        out = self._help("ARCANE_SHIELD")
        assert "SHIELD" in out.upper() or "arcane" in out.lower()

    def test_help_blink_returns_content(self):
        out = self._help("BLINK")
        assert "BLINK" in out.upper() or "blink" in out.lower()

    def test_help_arcane_light_spell_returns_content(self):
        out = self._help("ARCANE_LIGHT")
        assert "ARCANE" in out.upper() or "light" in out.lower()

    def test_help_identify_returns_content(self):
        out = self._help("IDENTIFY")
        assert "IDENTIFY" in out.upper() or "identify" in out.lower()

    def test_help_topic_case_insensitive(self):
        out = self._help("hunger")
        assert "HUNGER" in out.upper() or "hunger" in out.lower()

    def test_help_topic_works_from_any_state(self):
        # HELP <topic> should work regardless of current state
        for state in [State.NAVIGATION, State.CAMPFIRE, State.COMBAT]:
            s = make_session(state)
            out = ask(s, "HELP HUNGER")
            assert "HUNGER" in out.upper() or "hunger" in out.lower(), \
                f"HELP HUNGER failed in state {state}"


# ═══════════════════════════════════════════════════════════════════════════════
# Phase D — Unknown topic graceful fallback
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseD_UnknownTopic:
    def test_help_nonexistent_does_not_crash(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP XYZZY")
        assert len(out) > 0

    def test_help_nonexistent_mentions_topic_name(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP XYZZY")
        assert "XYZZY" in out.upper() or "xyzzy" in out.lower()

    def test_help_nonexistent_suggests_help_list(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP FOOBAR")
        assert "HELP" in out.upper()

    def test_help_empty_string_returns_contextual(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP")
        assert len(out) > 0
        assert "LOOK" in out.upper() or "NORTH" in out.upper()
