import math
import textwrap
import shelve
import datetime

import libtcodpy as libtcod

#=====#
#Setup#
#=====#

#Screen
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 10
LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30

#Map
MAP_WIDTH = 80
MAP_HEIGHT = 43
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
MAX_ROOM_MONSTERS = 3 
MAX_ROOM_ITEMS = 2

#Field of View
FOV_ALGO = 0 
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

#map colors 
color_dark_wall = libtcod.Color(0, 0, 100)
color_light_wall = libtcod.Color(130, 110, 50)
color_dark_ground = libtcod.Color(50, 50, 150)
color_light_ground = libtcod.Color(200, 180, 50)

#game font
libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)

#sizes and coordinates relevant for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1
INVENTORY_WIDTH = 50

#==========#
#Item Stats#
#==========#

#bandage heal amount
HEAL_AMOUNT = 3

#wild shot range
WILD_SHOT_DAMAGE = 20
WILD_SHOT_RANGE = 5

GERNADE_RADIUS = 3
GERNADE_DAMAGE = 12

#============#
#Player stats#
#============#

#experience and level-ups
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150

#============#
#Object Class#
#============#

class Object:

    #this is a generic object: the player, a monster, an item, the stairs...
    #it's always represented by a character on screen.
    def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, item=None, flame=None):
   
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks
        self.always_visible = always_visible  
		
        self.flame =flame
        if self.flame:
            self.flame.owner = self
            
        self.fighter = fighter
        if self.fighter:  #let the fighter component know who owns it
            self.fighter.owner = self
 
        self.ai = ai
        if self.ai:  #let the AI component know who owns it
            self.ai.owner = self		

        self.item = item
        if self.item:  #let the Item component know who owns it
            self.item.owner = self
    
	#move by the given amount, if the destination is not blocked
    def move(self, dx, dy):
        if not map[self.x + dx][self.y + dy].blocked or dx==0 and dy==0:
            self.x += dx
            self.y += dy
 
    #vector from this object to the target, and distance
    def move_towards(self, target_x, target_y):
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)
        
 
        #normalize it to length 1 (preserving direction), then round it and
        #convert to integer so the movement is restricted to the map grid
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        moved = False
        if not is_blocked(dx + self.x, dy + self.y):
            if moved is not True:    
                self.move(dx, dy)
                moved = True
        if not is_blocked(self.x, dy+self.y):
            if moved is not True:
                self.move(0,dy)
                moved = True
        if not is_blocked(dx + self.x, self.y):
            if moved is not True:
                self.move(dx,0)
                moved = True

        dx = target_x - self.x
        dy = target_y - self.y
        
        dx = int(math.ceil(dx / distance))
        dy = int(math.ceil(dy / distance))
        if not is_blocked(dx + self.x, dy + self.y):
            if moved is not True:
                self.move(dx, dy)
                moved = True
        if not is_blocked(self.x, dy+self.y):
            if moved is not True:
                self.move(0,dy)
                moved = True
        if not is_blocked(dx + self.x, self.y):
            if moved is not True:
                self.move(dx,0)
                moved = True

        dx = target_x - self.x
        dy = target_y - self.y
        
        dx = int(math.floor(dx / distance))
        dy = int(math.floor(dy / distance))
        
        if not is_blocked(dx + self.x, dy + self.y):
            if moved is not True:
                self.move(dx, dy)
                moved = True
        if not is_blocked(self.x, dy+self.y):
            if moved is not True:
                self.move(0,dy)
                moved = True
        if not is_blocked(dx + self.x, self.y):
            if moved is not True:
                self.move(dx,0)
                moved = True
                    
	#return the distance to another object 
    def distance_to(self, other):
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)
        
	#return the distance to some coordinates
    def distance(self, x, y):
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)
		
    def draw(self):
        #only show if it's visible to the player
        if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or
            (self.always_visible and map[self.x][self.y].explored)):
            #set the color and then draw the character that represents this object at its position
            libtcod.console_set_foreground_color(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
    
	#make this object be drawn first, so all others appear above it if they're in the same tile.
    def send_to_back(self):
        global objects
        objects.remove(self)
        objects.insert(0, self)
		
    #erase the character that represents this object
    def clear(self):
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)
 
#===============================#
#Object Functions and SubClasses#
#===============================#

def closest_monster(max_range):
    #find closest enemy, up to a maximum range, and in the player's FOV
    closest_enemy = None
    closest_dist = max_range + 1  #start with (slightly more than) maximum range
 
    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            #calculate distance between this object and the player
            dist = player.distance_to(object)
            if dist < closest_dist:  #it's closer, so remember it
                closest_enemy = object
                closest_dist = dist
    return closest_enemy

def target_monster(max_range=None):
    #returns a clicked monster inside FOV up to a range, or None if right-clicked
    while True:
        (x, y) = target_tile(max_range)
        if x is None:  #player cancelled
            return None
 
        #return the first clicked monster, otherwise continue looping
        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj	

class Flame:
    def __init__(self, duration, heat, spread):
        self.max_duration = duration
        self.duration = duration
        self.heat = heat
        self.spread = spread
        
    def take_turn(self):
        flame = self.owner
        if self.duration > 0:
            self.duration -= 1
            #damage anything thats on the flame
            for object in objects:
                if object.fighter and object.x == flame.x and object.y == flame.y:
                    object.fighter.take_damage(self.heat, "FIRE! FIRE EVERYWHERE!")
                    message('Flames burn ' + object.name + ' for ' + str(self.heat) + ' hit points.', libtcod.red)
            #randomly spread fire
            new_flames = libtcod.random_get_int(0, 0, self.spread)
            new_flames = new_flames/2 
            while new_flames > 0:
                x = libtcod.random_get_int(0, -1, 1)
                y = libtcod.random_get_int(0, -1, 1)
                x = flame.x + x
                y = flame.y + y
                new_flames = new_flames - 1
                if not is_blocked(x,y):
                    fire_spread_prevention = libtcod.random_get_int(0, 1, 3)
                    flame_component = Flame( duration=3, heat=5, spread=(self.spread/fire_spread_prevention))
                    fire = Object(x, y, ',', 'flame', libtcod.red, blocks=False, flame = flame_component)      
                    objects.append(fire)  

                    
        else:
            objects.remove(flame)
                      
class Fighter:
    #combat-related properties and methods (monster, player, NPC).
    def __init__(self, hp, defense, power,xp, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.death_function = death_function
        self.xp = xp

 
    def attack(self, target):
        #a simple formula for attack damage
        damage = self.power - target.fighter.defense
 
        if damage > 0:
            #make the target take some damage
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
            target.fighter.take_damage(damage, self.owner.name)
        else:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!')
 
    def take_damage(self, damage, damager=None):
        #apply damage if possible
        if damage > 0:
            self.hp -= damage
 
            #check for death. if there's a death function, call it
            if self.hp <= 0:
                function = self.death_function
                if function is not None:
                    function(self.owner, damager)
                if self.owner != player:
					player.fighter.xp += self.xp
 
    def heal(self, amount):
        #heal by the given amount, without going over the maximum
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

class BasicMonster:
    #AI for a basic monster.
    global alert_level
    def take_turn(self):
        #a basic monster takes its turn. If you can see it, it can see you
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y) or monster.distance_to(player) <= alert_level:
 
            #move towards player if far away
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)
                Object.clear(self.owner)
 
            #close enough, attack! (if the player is still alive.)
            #close enough, attack! (if the player is still alive.)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)

def check_level_up():
    #see if the player's experience is enough to level-up
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.xp >= level_up_xp:
        #it is! level up
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('Your battle skills grow stronger! You reached level ' + str(player.level) + '!', libtcod.yellow)

        choice = None
        while choice == None:  #keep asking until a choice is made
            choice = menu('Level up! Choose a stat to raise:\n',
                ['Constitution (+20 HP, from ' + str(player.fighter.max_hp) + ')',
                'Strength (+1 attack, from ' + str(player.fighter.power) + ')',
                'Agility (+1 defense, from ' + str(player.fighter.defense) + ')'], LEVEL_SCREEN_WIDTH)
 
        if choice == 0:
            player.fighter.max_hp += 20
            player.fighter.hp += 20
        elif choice == 1:
            player.fighter.power += 1
        elif choice == 2:
            player.fighter.defense += 1
		
def player_death(player, cause):
    #the game ended!
    global game_state
    message ("And then John was a zombie...", color = libtcod.red)
    message ("Press 'r' to try again", color = libtcod.light_red)    
    game_state = 'dead'
    score_board(cause)
    
 
    #for added effect, transform the player into a corpse!
    player.char = '%'
    player.color = libtcod.dark_red
	
def monster_death(monster, cause):
    #transform it into a nasty corpse! it doesn't block, can't be
    #attacked and doesn't move
    message('The ' + monster.name + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points.', libtcod.orange)
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()
      
class Item:
    #an item that can be picked up and used.
    def __init__(self, use_function=None):
        self.use_function = use_function
 
    def pick_up(self):
        #add to the player's inventory and remove from the map
        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', libtcod.green)
 
    def use(self):
        #just call the "use_function" if it is defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner)  #destroy after use, unless it was cancelled for some reason
 
    def drop(self):
        #add to the map and remove from the player's inventory. also, place it at the player's coordinates
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.', libtcod.yellow) 
		
#==========#
#Tile Class#
#==========#

class Tile:
    #a tile of the map and its properties
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked
 
        #all tiles start unexplored
        self.explored = False
 
        #by default, if a tile is blocked, it also blocks sight
        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight
		
#=============#
#Map Generator#
#=============#

def make_map():
    global map, objects, stairs
 
    #the list of objects with just the player
    objects = [player]
 
    #fill map with "blocked" tiles
    map = [[ Tile(True)
        for y in range(MAP_HEIGHT) ]
            for x in range(MAP_WIDTH) ]
 
    rooms = []
    num_rooms = 0
 
    for r in range(MAX_ROOMS):
        #random width and height
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        #random position without going out of the boundaries of the map
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
 
        #"Rect" class makes rectangles easier to work with
        new_room = Rect(x, y, w, h)
 
        #run through the other rooms and see if they intersect with this one
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break
 
        if not failed:
            #this means there are no intersections, so this room is valid
 
            #"paint" it to the map's tiles
            create_room(new_room)
 
            #add some contents to this room, such as monsters
            place_objects(new_room)
 
            #center coordinates of new room, will be useful later
            (new_x, new_y) = new_room.center()
 
            if num_rooms == 0:
                #this is the first room, where the player starts at
                if not is_blocked(new_x,new_y):
                    player.x = new_x
                    player.y = new_y
                elif not is_blocked(new_x + 1,new_y):
                    player.x = new_x + 1
                    player.y = new_y  
                elif not is_blocked(new_x - 1,new_y):
                    player.x = new_x - 1
                    player.y = new_y 
                elif not is_blocked(new_x,new_y + 1):
                    player.x = new_x 
                    player.y = new_y + 1
                elif not is_blocked(new_x,new_y - 1):
                    player.x = new_x + 1
                    player.y = new_y - 1                    
                    
            else:
                #all rooms after the first:
                #connect it to the previous room with a tunnel
 
                #center coordinates of previous room
                (prev_x, prev_y) = rooms[num_rooms-1].center()
 
                #draw a coin (random number that is either 0 or 1)
                if libtcod.random_get_int(0, 0, 1) == 1:
                    #first move horizontally, then vertically
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    #first move vertically, then horizontally
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)
 
            #finally, append the new room to the list
            rooms.append(new_room)
            num_rooms += 1

	#create stairs at the center of the last room
    stairs = Object(new_x, new_y, '<', 'stairs', libtcod.white, always_visible=True)
    objects.append(stairs)
			
class Rect:
    #a rectangle on the map. used to characterize a room.
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h
		

    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)
 
    def intersect(self, other):
        #returns true if this rectangle intersects with another one
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)		
		
def create_h_tunnel(x1, x2, y):
    global map
    for x in range(min(x1, x2), max(x1, x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False
		
def create_v_tunnel(y1, y2, x):
    global map
    #vertical tunnel
    for y in range(min(y1, y2), max(y1, y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False		
		
def create_room(room):
    global map
    #go through the tiles in the rectangle and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False
					
def place_objects(room):

    #choose random number of monsters
    num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)
 
    for i in range(num_monsters):
        #choose random spot for this monster
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		
        #only place it if the tile is not blocked
        if not is_blocked(x, y):
            if libtcod.random_get_int(0, 0, 100) < 80:  #80% chance of getting a weak zombie
                #create a weak zombie
                fighter_component = Fighter(hp=10, defense=dungeon_level, power=3  + (dungeon_level/2) , death_function = monster_death, xp = 35 + (10*dungeon_level))
                ai_component = BasicMonster()
                monster = Object(x, y, 'z', 'Weak Zombie', libtcod.desaturated_green, blocks=True, 
				    fighter = fighter_component, ai = ai_component)
                
            else:
                #create a Strong Zombie
                fighter_component = Fighter(hp=15, defense=1 + ((dungeon_level*2)/3), power=3 + ((dungeon_level*2)/3), death_function = monster_death, xp = 75+(15*dungeon_level))
                ai_component = BasicMonster()
                monster = Object(x, y, 'Z', 'Strong Zombie', libtcod.darker_green, blocks=True, 
				     fighter = fighter_component, ai = ai_component)
                
            objects.append(monster)
            
			#choose random number of items
    num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)


	
    for i in range(num_items):
        #choose random spot for this item
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
 
        #only place it if the tile is not blocked
        if not is_blocked(x, y):		

            dice = libtcod.random_get_int(0, 0, 100)
            if dice < 65:
                #create a bandage (65% chance)
                item_component = Item(use_function=use_bandage)
                item = Object(x, y, '!', 'Bandage', libtcod.violet, item=item_component)
				
            elif dice >80 and dice<85:
                #create a wild shot (20% chance)
                item_component = Item(use_function=wild_shot)
                item = Object(x, y, '#', 'Wild Shot', libtcod.light_yellow, item=item_component)
            
            elif dice >65 and dice<80:
                item_component = Item(use_function=throw_molotov)
                item = Object(x, y, 'm', 'Molotov Cocktail', libtcod.light_red, item = item_component)
            
            else:
                #create a hand gernade (15% chance)
                item_component = Item(use_function=throw_gernade)
                item = Object(x, y, '#', 'Hand Gernade', libtcod.light_red, item=item_component)
				
            objects.append(item)
            item.send_to_back()  #items appear below other objects
            item.always_visible = True      
			
def next_level():
    global dungeon_level, alert_level
	
    #advance to the next level
    message('You take a moment to rest, and recover your strength.', libtcod.light_violet)
    player.fighter.heal(player.fighter.max_hp / 2)  #heal the player by 50%
 
    message('After a rare moment of peace, you descend deeper into the heart of the dungeon...', libtcod.red)
    dungeon_level += 1
    alert_level = alert_level//2
    make_map()  #create a fresh new level!
    initialize_fov()			
#=============#
#Render screen#
#=============#
def render_all(target=False):
    global fov_map, color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute
 
    if fov_recompute:
        #recompute FOV if needed (the player moved or something)
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
 
        #go through all tiles, and set their background color according to the FOV
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = libtcod.map_is_in_fov(fov_map, x, y)
                wall = map[x][y].block_sight
                if not visible:
                    #if it's not visible right now, the player can only see it if it's explored
                    if map[x][y].explored:
                        if wall:
                            libtcod.console_set_back(con, x, y, color_dark_wall, libtcod.BKGND_SET)
                        else:
                            libtcod.console_set_back(con, x, y, color_dark_ground, libtcod.BKGND_SET)
                else:
                    #it's visible
                    if wall:
                        libtcod.console_set_back(con, x, y, color_light_wall, libtcod.BKGND_SET )
                    else:
                        libtcod.console_set_back(con, x, y, color_light_ground, libtcod.BKGND_SET )
                    #since it's visible, explore it
                    map[x][y].explored = True
 
    #draw all objects in the list, except the player. we want it to
    #always appear over all other objects! so it's drawn later.
    if target is False:
        for object in objects:
            if object != player:
                object.draw()
        player.draw()
    
        
    #blit the contents of "con" to the root console
    libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)
 
 
    #prepare to render the GUI panel
    libtcod.console_set_background_color(panel, libtcod.black)
    libtcod.console_clear(panel)
 
    #print the game messages, one line at a time
    y = 1
    for (line, color) in game_msgs:
        libtcod.console_set_foreground_color(panel, color)
        libtcod.console_print_left(panel, MSG_X, y, libtcod.BKGND_NONE, line)
        y += 1
 
    #show the player's stats
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
        libtcod.light_red, libtcod.darker_red)
        
    render_bar(1, 2, BAR_WIDTH, 'XP', player.fighter.xp, LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR,
        libtcod.light_green, libtcod.darker_green)    

    libtcod.console_print_left(panel, 1, 3, libtcod.BKGND_NONE, 'Player level ' + str(player.level))
    libtcod.console_print_left(panel, 1, 4, libtcod.BKGND_NONE, 'Dungeon level ' + str(dungeon_level))	
	
	#display names of objects under the mouse
    libtcod.console_set_foreground_color(panel, libtcod.light_gray)
    libtcod.console_print_left(panel, 1, 0, libtcod.BKGND_NONE, get_names_under_mouse())
 
    #blit the contents of "panel" to the root console
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)	

#===#
#GUI#
#===#

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    #render a bar (HP, experience, etc). first calculate the width of the bar
    bar_width = int(float(value) / maximum * total_width)
 
    #render the background first
    libtcod.console_set_background_color(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False)
 
    #now render the bar on top
    libtcod.console_set_background_color(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False)	

    #finally, some centered text with the values
    libtcod.console_set_foreground_color(panel, libtcod.white)
    libtcod.console_print_center(panel, x + total_width / 2, y, libtcod.BKGND_NONE,
        name + ': ' + str(value) + '/' + str(maximum))
		
def message(new_msg, color = libtcod.white):
    #split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
 
    for line in new_msg_lines:
        #if the buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]
 
        #add the new line as a tuple, with the text and the color
        game_msgs.append( (line, color) )

def get_names_under_mouse():
    #return a string with the names of all objects under the mouse
    mouse = libtcod.mouse_get_status()
    (x, y) = (mouse.cx, mouse.cy)
 
    #create a list with the names of all objects at the mouse's coordinates and in FOV
    names = [obj.name for obj in objects
        if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
 
    names = ', '.join(names)  #join the names, separated by commas
    return names.capitalize()

def menu(header, options, width):
    if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')
 
    #calculate total height for the header (after auto-wrap) and one line per option
    header_height = libtcod.console_height_left_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    if header == '':
        header_height = 0
    height = len(options) + header_height
 
    #create an off-screen console that represents the menu's window
    window = libtcod.console_new(width, height)
 
    #print the header, with auto-wrap
    libtcod.console_set_foreground_color(window, libtcod.white)
    libtcod.console_print_left_rect(window, 0, 0, width, height, libtcod.BKGND_NONE, header)
 
    #print all the options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        libtcod.console_print_left(window, 0, y, libtcod.BKGND_NONE, text)
        y += 1
        letter_index += 1
 
    #blit the contents of "window" to the root console
    x = SCREEN_WIDTH/2 - width/2
    y = SCREEN_HEIGHT/2 - height/2
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)
 
    #present the root console to the player and wait for a key-press
    libtcod.console_flush()	
    key = libtcod.console_wait_for_keypress(True)
 
    if key.vk == libtcod.KEY_ENTER and key.lalt:  #(special case) Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
 
    #convert the ASCII code to an index; if it corresponds to an option, return it
    index = key.c - ord('a')
    if index >= 0 and index < len(options): return index
    return None

def inventory_menu(header):
    #show a menu with each item of the inventory as an option
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = [item.name for item in inventory]
 
    index = menu(header, options, INVENTORY_WIDTH)
 
    #if an item was chosen, return it
    if index is None or len(inventory) == 0: return None
    return inventory[index].item

def quit_confirmation():
    options = ["yes" , "no"]
    index = menu("Are you sure you want to quit?", options, INVENTORY_WIDTH)
    return index

def msgbox(text, width=50):
    menu(text, [], width)  #use menu() as a sort of "message box"
        
#==================#
#User input handler#
#==================#
	
#Checks if movement is blocked
def is_blocked(x, y):
    #first test the map tile
    if map[x][y].blocked:
        return True
 
    #now check for any blocking objects
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True
 
    return False	
		
def player_move_or_attack(dx, dy):
    global fov_recompute
    
    #the coordinates the player is moving to/attacking
       
    x = player.x + dx
    y = player.y + dy
 
    #try to find an attackable object there
    target = None
    for object in objects:
        if object.fighter and object.x == x and object.y == y:
            target = object

 
    #attack if target found, move otherwise
    if target is not None:
        if target is not player:
            player.fighter.attack(target)
        else:
            player.move(dx, dy)
    else:
        player.move(dx, dy)
        fov_recompute = True	

def target_tile(max_range=None):
    #return the position of a tile left-clicked in player's FOV (optionally in a range), or (None,None) if right-clicked.
    while True:
        render_all(True)
        #render the screen. this erases the inventory and shows the names of objects under the mouse.
        libtcod.console_flush()
        
        for object in objects:
            object.draw()
 
        key = libtcod.console_check_for_keypress()
        mouse = libtcod.mouse_get_status()  #get mouse position and click status
        (x, y) = (mouse.cx, mouse.cy)
 
        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            for object in objects:
                object.clear()
            return (None, None)  #cancel if the player right-clicked or pressed Escape
 
        #accept the target if the player clicked in FOV, and in case a range is specified, if it's in that range
        if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and
            (max_range is None or player.distance(x, y) <= max_range)):
            for object in objects:
                object.clear()

            return (x, y)

def handle_keys():
    key = libtcod.console_check_for_keypress(libtcod.KEY_PRESSED)
    mouse = libtcod.mouse_get_status()
    (x, y) = (mouse.cx, mouse.cy)
    (mousex, mousey) = (x - player.x, y - player.y)   
    
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        #Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
 
    elif key.vk == libtcod.KEY_ESCAPE:
        if quit_confirmation() ==0:
            return 'exit'  #exit game
        else: 
            return 'didnt-take-turn'
            

    if game_state == 'dead':
        key_char = chr(key.c)
        if key_char == 'r':
            new_game()

    if game_state == 'playing':
        #movement keys
        
        if key.vk == libtcod.KEY_KP1:
            player_move_or_attack(-1, 1)          
        elif key.vk == libtcod.KEY_KP2:
            player_move_or_attack( 0, 1)   
        elif key.vk == libtcod.KEY_KP3:
            player_move_or_attack( 1, 1)   
        elif key.vk == libtcod.KEY_KP4:
            player_move_or_attack(-1, 0)
        
        elif key.vk == libtcod.KEY_KP5:
            action_taken =False
            for object in objects:  #look for an item in the player's tile
                if object.x == player.x and object.y == player.y and object.item :
                    object.item.pick_up()
                    action_taken = True
            if stairs.x == player.x and stairs.y == player.y:
                    action_taken = True
                    next_level()
            if action_taken == False:
                player_move_or_attack( 0, 0)  
            
            
        elif key.vk == libtcod.KEY_KP6:
            player_move_or_attack( 1, 0)   
        elif key.vk == libtcod.KEY_KP7:
            player_move_or_attack(-1,-1)   
        elif key.vk == libtcod.KEY_KP8:
            player_move_or_attack( 0,-1)   
        elif key.vk == libtcod.KEY_KP9:
            player_move_or_attack( 1,-1) 
            
             
        elif (mouse.lbutton_pressed and mousex < 2 and mousex > -2 and mousey < 2 and mousey > -2):
            player_move_or_attack(mousex, mousey)
        
        elif key.vk == libtcod.KEY_UP:
            player_move_or_attack(0, -1)          

        elif key.vk == libtcod.KEY_DOWN:
            player_move_or_attack(0, 1)
 
        elif key.vk == libtcod.KEY_LEFT:
            player_move_or_attack(-1, 0)
 
        elif key.vk == libtcod.KEY_RIGHT:
            player_move_or_attack(1, 0)
                        
        elif chr(key.c) == 'i':
            #show the inventory; if an item is selected, use it
            chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
            if chosen_item is not None:
                chosen_item.use()  
                player_move_or_attack(0,0)
            else:
                return 'didnt-take-turn'

                    
        else:
            #test for other keys
            key_char = chr(key.c)

            if key_char == 'g':
                #pick up an item
                for object in objects:  #look for an item in the player's tile
                    if object.x == player.x and object.y == player.y and object.item :
                        object.item.pick_up()
                        break

            if key_char == 'd':
                #show the inventory; if an item is selected, drop it
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()

            if key_char == '<':
                #go down stairs, if the player is on them
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()
			
            if key_char == 'c':
                #show character information
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox('Character Information\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) +
                    '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
                    '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)
                    
            if key_char == '?':
                #show controls
                msgbox("Controls:"+"\narrows/numpad    = move/attack" +"\ni    = inventory"+"\ng    = pick up item at player's feet"+
                "\nd    = drop an item in inventory"+"\n<    = use the stairs at player's feet"+"\nc    = character sheet"+
                "\nr    = new game (when dead)"+"\n\nalt+enter    =fullscreen mode"+"\nesc          = quit game")       
			
            return 'didnt-take-turn'
			
#==============#
#Item Abilities#
#==============#
		
def use_bandage():
    #heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', libtcod.red)
        return 'cancelled'
 
    message('Your wounds start to feel better!', libtcod.light_violet)
    player.fighter.heal((player.fighter.max_hp - player.fighter.hp)/HEAL_AMOUNT)		
		
def wild_shot():
    global alert_level
    #find closest enemy (inside a maximum range) and damage it
    monster = closest_monster(WILD_SHOT_RANGE)
    if monster is None:  #no enemy found within maximum range
        message('No enemy is close enough to strike.', libtcod.red)
        return 'cancelled'
 
    message('A wild gunshot hits ' + monster.name + ' with a loud blast! The damage is '
        + str(WILD_SHOT_DAMAGE) + ' hit points.', libtcod.light_blue)
    monster.fighter.take_damage(WILD_SHOT_DAMAGE, "wild_shot")	
    alert_level += 3

def throw_gernade():
    global alert_level

    #ask the player for a target tile to throw a gernade at
    message('Left-click a target tile for the gernade, or right-click to cancel.', libtcod.light_cyan)
    (x, y) = target_tile()

    if x is None: return 'cancelled'
    message('The gernade explodes, harming everything within ' + str(GERNADE_RADIUS) + ' tiles!', libtcod.orange)
    
    for obj in objects:  #damage every fighter in range, including the player
        if obj.distance(x, y) <= GERNADE_RADIUS and obj.fighter:
            message('The ' + obj.name + ' gets damaged for ' + str(GERNADE_DAMAGE) + ' hit points.', libtcod.orange)
            obj.fighter.take_damage(GERNADE_DAMAGE, "......your own hand gernade....nice..")
            alert_level +=3

def throw_molotov():
    global alert_level
    #ask the player for a target tile to throw a gernade at
    message('Left-click a target tile for the molotov, or right-click to cancel.', libtcod.light_cyan)
    (x, y) = target_tile()
    if x is None: 
        return 'cancelled'
    
    flame_component = Flame( duration=5, heat=5, spread=6)
    fire = Object(x, y, ',', 'flame', libtcod.red, blocks=False, flame = flame_component)      
    objects.append(fire)  
    alert_level += 1
        
#=============#
#Save and Load#
#=============#
def score_board(death):
    date = datetime.date.today()
    msgbox((str)(date.day)+"-"+(str)(date.month)+"-"+(str)(date.year) +     "\nYou were killed on floor " + (str)(dungeon_level) +" by a " + death)

def save_game():
    #open a new empty shelve (possibly overwriting an old one) to write the game data
    file = shelve.open('savegame', 'n')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player)  #index of player in objects list
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['stairs_index'] = objects.index(stairs)
    file['dungeon_level'] = dungeon_level
    file.close()

def load_game():
    #open the previously saved shelve and load the game data
    global map, objects, player, inventory, game_msgs, game_state
 
    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]  #get index of player in objects list and access it
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    stairs = objects[file['stairs_index']]
    dungeon_level = file['dungeon_level'] 
    file.close()
 
    initialize_fov()	
	
def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level, alert_level
 
    #create object representing the player
    fighter_component = Fighter(hp=30, defense=2, power=5, xp=0, death_function=player_death)
    player = Object(0, 0, '@', 'player', libtcod.white, blocks=True, fighter=fighter_component)
 
    player.level = 1
	
    #generate map (at this point it's not drawn to the screen)
    dungeon_level = 1
    alert_level = 0
    make_map()
    initialize_fov()
 
    game_state = 'playing'
    inventory = []
 
    #create the list of game messages and their colors, starts empty
    game_msgs = []
 
    #a warm welcoming message!
    message('Insert apocolypse here', libtcod.red)

def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True
 
    #create the FOV map, according to the generated map
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

    libtcod.console_clear(con)  #unexplored areas start black (which is the default background color)

def play_game():
    player_action = None
 
    while not libtcod.console_is_window_closed():
        #render the screen
        render_all()
 
        libtcod.console_flush()
        check_level_up() 
        #erase all objects at their old locations, before they move
        for object in objects:
            object.clear()
 
        #handle keys and exit game if needed
        player_action = handle_keys()
        if player_action == 'exit':
            save_game()
            break
 
        #let monsters take their turn
        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.flame:
                    object.flame.take_turn()
                if object.ai:
                    object.ai.take_turn()
        
def main_menu():
    # img = libtcod.image_load('menu_background.png')
 
    # while not libtcod.console_is_window_closed():
        #show the background image, at twice the regular console resolution
        # libtcod.image_blit_2x(img, 0, 0, 0)
 
        #show the game's title, and some credits!
        libtcod.console_set_foreground_color(0, libtcod.light_yellow)
        libtcod.console_print_center(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, 'Zombies!')
        libtcod.console_print_center(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, 'By Glenn Jackson')
 
        #show options and wait for the player's choice
        choice = menu('', ['Play a new game'], 24)

	
        if choice == 0:  #new game
            new_game()
            play_game()
		
        else:
            new_game()
            play_game()
			
        #choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)
        # if choice == 0:  #new game
            # new_game()
            # play_game()		
        # if choice == 1:  #load last game
            # try:
                # load_game()
            # except:
                # msgbox('\n No saved game to load.\n', 24)
                # continue
            # play_game()
        # elif choice == 2:  #quit
            # break
			
#===================#
#Game Initilaization#
#===================#

libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Zombies!', False)
libtcod.sys_set_fps(LIMIT_FPS)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

main_menu()		