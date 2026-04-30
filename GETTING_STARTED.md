# Ashveil MUD — Getting Started Guide

## Starting the Application

### 1. Install Dependencies (first time only)

```powershell
uv sync
```

### 2. Start the Server

Run this from the project root:

```powershell
uv run uvicorn server.main:app --reload --port 8081
```

The server starts on **http://localhost:8081**.

### 3. Open the Game

Open your browser and navigate to:

```
http://localhost:8081
```

This loads the browser terminal client. You'll see a welcome prompt — you're ready to play.

> **Tip:** Keep the terminal window visible while playing so you can see Python errors and combat log output from uvicorn.

---

## Creating a Character

### Step 1 — Enter Your Name

At the welcome prompt, type your character's name and press Enter.

```
> Aldric
```

### Deleting a Character

If you want to permanently delete a character, use the DELETE command at the login screen:

**Step 1 — Initiate Deletion**

```
> DELETE Aldric
```

**Step 2 — Confirm Deletion**

The system will warn you and ask for confirmation. You must type the character name again to confirm:

```
WARNING: CHARACTER DELETION
You are about to PERMANENTLY delete character: Aldric
This action cannot be undone!

To confirm deletion, type the character name again: 'Aldric'
To cancel, type: CANCEL

> Aldric
```

**Step 3 — Deletion Complete**

After successful deletion, you'll return to the login prompt:

```
Character 'Aldric' has been successfully deleted.

Enter your character name (new or existing):
To delete a character, type: DELETE <name>
>
```

**Important Notes:**
- Deletion is **permanent** and cannot be undone
- Character names are case-insensitive for both deletion and confirmation
- Type `CANCEL` at any time to abort the deletion process
- You can type `HELP DELETE` at the login screen for more information

### Step 2 — Choose a Class

You'll be shown the four available classes. Type the class name to select it.

| Class | Playstyle | Primary Stat | Best For |
|-------|-----------|--------------|----------|
| `WARRIOR` | Melee tank, high HP | STR | Beginners; front-line fighter |
| `MAGE` | Ranged magic, fragile | INT | High burst damage; needs a tank |
| `THIEF` | Fast, sneaky, DoT | DEX | Backstabs; avoids hits |
| `CLERIC` | Healer / support | WIS | Keeping the party alive |

```
> WARRIOR
```

**Recommended for a first playthrough:** `WARRIOR` — high HP, straightforward combat strategies.

### Step 3 — Assign Stats

You have **54 points** to distribute across 6 stats (each stat ranges from 3 to 18).

| Stat | Affects |
|------|---------|
| STR | Melee damage, carry weight |
| DEX | Attack speed, dodge, thief damage |
| INT | Spell damage, mana pool |
| WIS | Healing power, mana regen |
| CON | Max HP |
| AGI | Initiative, dodge |

Use these commands:

```
STATS          — show current allocation
SUGGEST        — auto-fill a class-appropriate spread
SET STR 16     — manually set a stat value
DONE           — finalize and proceed
```

**Quick start:** just type `SUGGEST` then `DONE` to use the recommended spread for your class.

### Step 4 — Set Combat Strategies

Strategies are IF/THEN rules that automate your character's behavior in combat. You don't need to do anything here for basic play — just type:

```
DONE
```

You can always refine strategies later at a campfire (`MANAGE <member_name>`).

**Example strategy (added later):**

```
STRATEGY ADD 1 IF HP < 30% DO USE heal_potion ON SELF
STRATEGY ADD 2 IF ENEMY_HP > 50% DO ATTACK ON WEAKEST
```

---

## Playing the Game

### Your Starting Location

You spawn in **Ashveil Town Square**. Type `LOOK` to see the room, exits, and any NPCs.

```
LOOK
```

### Basic Loop

```
LOOK / L       — see your surroundings
N / S / E / W    — move between rooms
SS               — check hunger, thirst, stamina
STATS            — check HP, MP, level, equipment
INV              — show inventory
```

### Exploring Town

From Town Square:

| Direction | Destination | What's There |
|-----------|-------------|--------------|
| `N` | Blacksmith's Forge | Weapons & armor for sale |
| `E` | The Rusty Flagon Inn | Campfire to rest; potions |
| `W` | Mirabel's Apothecary | Potions, torches, lanterns |
| `S` | South Gate | Exit to Thornwood Forest |

### Resting at the Inn

Go east to the Inn and type:

```
CAMPFIRE
REST
```

`REST` fully restores HP, MP, and survival stats, and saves your character.

### Fighting Monsters

Head south through the gate into **Thornwood Forest** to find enemies. When in a room with monsters:

```
ATTACK
```

Combat is automatic — your strategies execute each 1.5-second tick. Watch the combat log scroll by. When it ends, type `LOOK` to see what loot dropped, then `TAKE <item>` to pick it up.

### Managing Survival

Three stats drain over time:

| Stat | Restored By |
|------|------------|
| **Hunger** | `EAT <food>` or `EA <food>` (e.g., `EA ration_pack`) |
| **Thirst** | `DRINK <item>` or `DR <item>` (e.g., `DR water_flask`) |
| **Stamina** | `SIT` to rest; `REST` at campfire for full recovery |

Check them anytime with:

```
STATUS
```
or use the shorthand:

```
SS
```

Low hunger or thirst reduces your combat damage. Low stamina blocks movement.

### Recruiting a Companion

Some rooms have recruitable NPCs. Speak to them:

```
TALK <npc_name>
```

If they're willing to join, they'll follow you. Manage the party at a campfire:

```
CAMPFIRE
PARTY         — see all members
FORMATION     — arrange the battle grid
MANAGE <name> — edit their combat strategies
```

---

## Look Mode Preferences

You can customize how room information is displayed using two preferences:

### LOOKMODE — Room Display Style

Control whether you see full room descriptions or quick summaries when entering rooms:

```
> LOOKMODE FULL    (default — full descriptions with all details)
> LOOKMODE QUICK   (compact summaries with color highlights)
```

**Quick Look** shows:
- Room name and available exits
- Items on floor (shown in **green**)
- Hostile enemies (shown in **red**)
- Recruitable NPCs (shown in **yellow**)
- Other players (shown in **blue**)

### BATTLELOOK — Post-Combat Display

Control whether a room summary appears after combat ends:

```
> BATTLELOOK ON    (default — show quick look after combat)
> BATTLELOOK OFF   (victory/defeat message only, no room summary)
```

When BATTLELOOK is ON, after defeating enemies you'll immediately see what's in the room — making it easy to spot loot or new threats without being spammed with full room descriptions.

Both preferences are **saved with your character** and persist across sessions.

---

## Useful Commands Reference

### Exploration
```
LOOK / L                   — describe current room
X <item>                   — examine an item or NPC
TIME / TI                  — show game time and day
WEATHER / WEA              — show current weather
LIGHT / LIGHTING           — show light level in room
HELP [topic]               — in-game help system
```

### Inventory & Equipment
```
INV                        — list all party inventory
EQUIP / EQ <member> <item> — equip item on a party member
UNEQUIP / UNEQ <member> <slot> — remove equipped item
DROP <item>                — drop item on the ground
TAKE <item>                — pick up item from ground
GIVE / GIV <item> <member> — transfer item between members
```

### Skills
```
SKILLS / SK                — list unlocked skills
SKILLS UTILITY             — utility skills only
LEARN / LRN <skill>        — unlock a skill (costs skill points)
UPGRADE / UPG <modifier>   — upgrade a stat modifier
USE <skill>                — activate a utility skill
BUFFS / B                  — show active buffs and effects
```

### System
```
SAVE / SV                  — save your progress
QUIT / LOGOUT              — exit the game
PARTY / P                  — show party status
STATUS / SS                — show survival stats (hunger/thirst/stamina)
```

### Party & Combat
```
TALK / T <npc>             — speak with a recruitable NPC
DISMISS / DIS <name>       — remove a companion from party
ATTACK / K                 — engage in combat
HORSES / HOR               — show horse status
```

---

## Running Tests

To verify the server is working correctly after code changes:

```powershell
pytest tests/
```

All tests should pass. Test files are named `test_phase<NN>_<topic>.py`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Server won't start | Run `uv sync` first |
| Browser shows blank page | Make sure the server is running on port 8081 |
| WebSocket disconnects | Check the uvicorn console for Python exceptions |
| Can't move (stamina 0) | `SIT` until stamina recovers, then `STAND` |
| Can't attack (pitch black) | Use `LIT torch` or `LIT lantern` to bring light |
| Lost save data | Saves are in a local SQLite file; make sure `SAVE` was used before quitting |
