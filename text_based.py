
import random
import time 
import copy
#regular enemies that appear for non boss rounds, easy enough to beat if played correctly. 
enemies = [
    {"name": "Goblin", "hp": 105, "base_damage": 13, "damage_reduction": 0},
    {"name": "Orc", "hp": 140, "base_damage": 17, "damage_reduction": 0},
    {"name": "Dragon", "hp": 180, "base_damage": 20, "damage_reduction": 5}
]
#appears every 4 rounds, tough enemies that need good strategy to kill. Rewards well though.
bosses = [
    {"name": "Skelly King", "hp":110,"base_damage":50 ,"damage_reduction": 15},
    {"name": "BigWolf", "hp": 250, "base_damage": 21, "damage_reduction": 10}
]
#starting gear, player can pick 1 of the 3, sword boosting raw dmg, shield boosting miss chance of enemy and armor boosting 
gear_options = {
    "sword":20,
    "shield":20,
    "armor":40,
}
# Lets the player type either a number ("1") or a name ("sword") and
# have both resolve to the same canonical key.
gear_lookup = {
    "1": "sword", "sword": "sword",   # just a TRANSLATOR
    "2": "shield", "shield": "shield",
    "3": "armor", "armor": "armor",
}
def shop(player, enemy):
    print("\n--- SHOP ---")
    print(f"Hello stranger, you have just defeated {enemy['name']}, take a breather and check out the shop!")
    while True:
        print(f"\nGold: {player['gold']}")
        print("[1] Sharpen weapon: +10 damage on attacks-15 gold")
        print("[2] Reinforce armor: +10% damage reduction - 20 gold")
        print("[3] Buy a potion: +1 potion - 9 gold")
        print("[4] Leave shop")
        choice = input("> ").strip()
        if choice == "1":
            if player["gold"] >= 15:
                player["gold"] -= 15
                player["base_damage"] += 10
                print("Your weapon feels sharper! +10 damage")
            else:
                print("Not enough gold!")
        elif choice == "2":
            # Damage reduction is capped at 90% inside attack(), so once
            # the player is already at the cap, block further purchases.
            if player["damage_reduction"] >= 90:
                print("You're already at the max damage reduction limit (90%). You are not charged")
            elif player["gold"] >= 20:
                player["gold"] -= 20
                player["damage_reduction"] = min(player["damage_reduction"] + 10, 90)
                print("Your armor is reinforced! +10% damage reduction")
            else:
                print("Not enough gold!")
        elif choice == "3":
            if player["gold"] >= 9:
                player["gold"] -= 9
                player["potions"] += 1
                print("You bought a potion!")
            else:
                print("Not enough gold!")
        elif choice == "4":
            print("Leaving the shop...")
            break
        else:
            print("Not a valid option.")
def attack(attacker, defender):
    
    #Rolls a random number 1-100 to decide the outcome:
       #1-15   -> miss (no damage)
        #31-50  -> critical hit (2x base damage)
        #51-100 -> normal hit (base damage +/- small random variance)
 
    #If the defender has a shield equipped, all three thresholds shift
    #up (miss/block/crit become more likely,  hits less likely).
 
    #Whatever damage is dealt is then reduced by the defender's
    #damage_reduction percentage, capped at 90% so nobody can become
    #fully immune.
    print(f"It is {attacker['name']}'s turn!")
    time.sleep(1)
    chance = random.randint(1,100)
    miss_limit = 15
    block_limit = 30
    crit_limit = 50
    damage_reduction = min(defender["damage_reduction"],90)
    if defender.get("shield"):
        miss_limit += 10
        block_limit += 20
        crit_limit += 20 
    
    if chance <= miss_limit:
        print(f"{attacker['name']} has missed! End of turn.")
        time.sleep(1)
              
    elif chance <= block_limit:
        print(f"{attacker['name']} has attacked but {defender['name']} has blocked it, zero damage!")
        time.sleep(1)
    elif chance <= crit_limit:
        crit = attacker['base_damage'] * 2
        crit = crit *(100-damage_reduction)//100
        defender['hp'] -= crit
        print(f"{attacker['name']} has attacked {defender['name']}, landing a criticial hit doing {crit} damage")      
        time.sleep(1) 
    
    else:
        # Normal hit: base damage with a small +/-2 random swing, reduced by armor %.
        variety = random.randint(-2,2)
        damage = attacker['base_damage'] + variety
        damage = max(0,damage)
        damage = damage *(100-damage_reduction)//100
        defender['hp'] -= damage
        print(f"{attacker['name']} has attacked {defender['name']}, doing {damage} damage")
        time.sleep(1)
    print(f"{attacker['name']} is at {max(0, attacker['hp'])}, {defender['name']} is at {max(0, defender['hp'])}")
    time.sleep(1)

def show_intro():
    for x in range(3):
        print("LOADING....")
        time.sleep(0.25)
    print("LOADED!")
    print("Hello and welcome to the text based fighter game!")
    time.sleep(1)
def get_name(player):
    name = input("What name do you want your player to be?: ").strip().title()
    player["name"] = name

def gear_selection(player):
    #Lets the player pick one starting gear item and applies its
    #permanent bonus to the player dict:
    print("Pick your gear: [1] Sword (+20 damage) [2] Shield (+10% chance that enemy misses, +10% chance you block enemy attack)\n [3] Armor , take 40% less damage.")
    while True:
        gear_choice = input("> ").strip().lower()
        if gear_choice in gear_lookup:
            gear = gear_lookup[gear_choice]
            if gear == "sword":  
                player["base_damage"] += gear_options[gear]
                print("Success!")
                print(f"Equipped {gear}!")
                break
                
            elif gear == "shield":
                player["shield"] = True
                print("Success!")
                print(f"Equipped {gear}!")
                break
                
            elif gear == "armor":
                player["damage_reduction"] += gear_options["armor"]
                print("Success!")
                print(f"Equipped {gear}!")
                break
            
            else:
                print("Not a valid gear! Please try again.")

        else:
            print("Not a valid choice! Please enter 1, 2, or 3.")
def continue_round(player, round):
    while True:
        choice = input(f"Continue to round {round}? Y or N\n> ").strip().upper()
        if choice == "Y":
            return True
        elif choice == "N":
            print(f"\n{player['name']} decided to retire after round {round}.")
            return False
        else:
            print("Please enter Y or N.")
def battle(player, enemy):
    while player['hp'] > 0 and enemy['hp'] > 0:
        while True:
            print(f"\nPotions left: {player['potions']}")
            choice=input("Type H to heal or A to attack or E to skip your turn: ").strip().capitalize()
            if choice == "H" and player["potions"] > 0:
                player["hp"]  += 50
                player["potions"] -= 1
                print(f"You healed! HP is now {player['hp']}")
                break
            elif choice == "A":
                attack(player,enemy)
                break
            elif choice == "H" and player["potions"] == 0:
                print("You have 0 potions")
            elif choice == "E":
                print("You decided to skip your turn")
                time.sleep(1.5)
                print("Why\n ?")
                break
            else:
                print("Not valid input")
        if enemy['hp'] > 0:
            # Enemy only gets a turn if the player's action didn't already kill it.  
            print("\nHere comes the enemy...")
            time.sleep(1)
            attack(enemy, player)
    print("\n" + "="*30)
    if player['hp'] > 0:
        print(f"🏆 VICTORY! {player['name']} has slain the {enemy['name']}!")
        return True
    else:
        return False

def main():
    show_intro()
    round = 1
    player ={"name": "", "hp":180,"base_damage":22, "potions":3,"damage_reduction":5,"gold":0}
    get_name(player)
    gear_selection(player)
    while True:
        # used deepcopy so whatever happens in battle does not affect the dict of enemies which should never be changed.
        enemy = copy.deepcopy(random.choice(enemies))
        boss_fight = copy.deepcopy(random.choice(bosses))
        if round % 4 == 0:
            print(f"WARNING!!! BOSS FIGHT IS EMERGING>\n GET READY TO FIGHT{boss_fight['name']}")
        else:
            print(f"\nA wild {enemy['name']} appears!")
        time.sleep(1)
        if round % 4 == 0:
            survived=battle(player, boss_fight)
        else:
            survived=battle(player, enemy)
        if not survived and round % 4 == 0:
            print(f"{boss_fight['name']}) has slain you, better luck next time")
            break
        if not survived:
            print(f"{enemy['name']}) has slain you, better luck next time")
            break
        # Reward gold for winning; boss rounds pay out extra.
        gold_earned = random.randint(20,35)
        if round % 4 == 0:
            gold_earned += 55
        player["gold"] += gold_earned
        print(f"You earned {gold_earned} gold! (Total: {player['gold']})")
        round +=1 
        decision=continue_round(player, round)
        if not decision:
                print(f"Okay!, Thats the end of the text based fighter game {player["name"]}")
                break
        else:
                
            shop_choice = input(f"Do you want to go to the shop before round {round} ?\n Y or N\n> ").strip().capitalize()
            if shop_choice == "Y" and round % 4 == 0:
                shop(player,boss_fight)
            elif shop_choice == "Y":
                shop(player,enemy)
            elif shop_choice == "N":
                print(f"Proceeding to round {round} !")
            else:
                print("Please input a valid answer. Y or N")
                
main()
