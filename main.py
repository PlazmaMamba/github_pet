import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json


load_dotenv()


token = os.getenv("GITHUB_TOKEN")
pet_first_use = os.getenv("PET_FIRST_USE", "2025-08-25")
save_file_path = os.getenv("SAVE_FILE_PATH", "pet_save.json")


def parse_date_string(date_string):
    return datetime.strptime(date_string, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)


today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
year_past = today - timedelta(days=365)
pet_start_date = parse_date_string(pet_first_use)


today_str = today.strftime("%Y-%m-%dT%H:%M:%SZ")
year_past_str = year_past.strftime("%Y-%m-%dT%H:%M:%SZ")

def load_pet_save():
    default_data = {
        "days_alive": 0,
        "total_experience": 0,
        "current_stage": "EGG",
        "health_state": "HEALTHY",
        "days_since_last_commit": 0,
        "days_in_current_stage": 0,
        "stage_stability": 0,  
        "evolution_history": [],
        "last_update": None,
        "is_first_run": True,
        "best_streak": 0,
        "total_commits": 0,
        "stage_days": {
            "EGG": 0,
            "HATCHLING": 0,
            "YOUNG": 0,
            "ADULT": 0,
            "LEGENDARY": 0
        },
        "achievements": [],
        "devolution_warnings": 0,
        "last_commit_date": None,
        "consecutive_inactive_days": 0  # New field to track consecutive inactive days
    }

    try:
        if os.path.exists(save_file_path):
            with open(save_file_path, 'r') as f:
                data = json.load(f)
                for key, value in default_data.items():
                    if key not in data:
                        data[key] = value
                return data
        else:
            return default_data
    except Exception as e:
        print(f"Error loading pet data: {e}")
        return default_data
    
def save_pet_data(data):
    try:
        with open(save_file_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved pet data to {save_file_path}")
    except Exception as ex:
        print(f"Error saving pet data: {ex}")

  
def make_graphql_request():
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is not set")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    query = f'''
    query {{
        user(login: "PlazmaMamba") {{
            calendar: contributionsCollection(from: "{year_past_str}", to: "{today_str}") {{
                contributionCalendar {{
                    weeks {{
                        contributionDays {{
                            contributionCount
                            color
                            date
                        }}
                    }}
                }}
            }}
        }}
    }}
    '''
    
    response = requests.post(
        "https://api.github.com/graphql",
        json={"query": query},
        headers=headers
    )
    
    if response.status_code != 200:
        raise Exception(f"GraphQL request failed: {response.status_code} - {response.text}")
    
    return response.json()

def get_adjusted_contributions(response, pet_start_date):
    weeks = response["data"]["user"]["calendar"]["contributionCalendar"]["weeks"]
    
    adjusted_contributions = []
    
    for week in weeks:
        for day in week["contributionDays"]:
            day_date = datetime.strptime(day["date"], "%Y-%m-%d")
            contribution_count = day["contributionCount"]
            
            # If this day is on or after pet start date, subtract 1 for the bot commit
            if day_date >= pet_start_date:
                adjusted_count = max(0, contribution_count - 1)  
            else:
                adjusted_count = contribution_count
            
            adjusted_contributions.append({
                "date": day["date"],
                "original_count": contribution_count,
                "adjusted_count": adjusted_count,
                "color": day["color"]
            }) 
    
    return adjusted_contributions

def calculate_current_streak(adjusted_contributions):
    if not adjusted_contributions:
        return 0
    
    streak = 0
    for day in reversed(adjusted_contributions):
        if day["adjusted_count"] > 0:
            streak += 1
        else:
            break  
    
    return streak

def calculate_days_since_last_contribution(adjusted_contributions):
    if not adjusted_contributions:
        return 0
    days = 0
    for day in reversed(adjusted_contributions):
        if day["adjusted_count"] == 0:
            days += 1
        else:
            break
    return days
            
def get_streak_multiplier(streak):
    if streak > 28:
        return 3
    elif streak > 21:
        return 2
    elif streak > 14:
        return 1.5
    elif streak > 7:
        return 1.25
    else:
        return 1

def calculate_days_alive(pet_start_date, today):
    return (today - pet_start_date).days + 1

def determine_health_state(days_since_last):
    if days_since_last == 0:
        return "HEALTHY"
    elif days_since_last <= 1:
        return "GOOD"
    elif days_since_last <= 3:
        return "TIRED"
    elif days_since_last <= 7:
        return "WEAK"
    elif days_since_last <= 14:
        return "CRITICAL"
    else:
        return "DEAD"
    
def get_stage_resilience(stage):
    """How many days a pet can survive without commits before starting to deteriorate"""
    resilience = {
        "EGG": 3,
        "HATCHLING": 5,
        "YOUNG": 7,
        "ADULT": 10,
        "LEGENDARY": 14
    }
    return resilience.get(stage, 3)

def get_stage_index(stage):
    """Helper function to get numeric index of a stage"""
    stage_order = ["EGG", "HATCHLING", "YOUNG", "ADULT", "LEGENDARY"]
    return stage_order.index(stage) if stage in stage_order else 0

def calculate_exp_gain(streak, days_since_last, health_state, adjusted_contributions):
    base_exp = 10
    streak_multiplier = get_streak_multiplier(streak)

    health_modifiers = {
        "HEALTHY": 1.2,
        "GOOD": 1.0,
        "TIRED": 0.8,
        "WEAK": 0.5,
        "CRITICAL": 0.2,
        "DEAD": 0.0
    }
    
    health_multiplier = health_modifiers.get(health_state, 1.0)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    today_commits = next(
        (day["adjusted_count"] for day in adjusted_contributions if day["date"] == today_str),
        0
    )
    
    activity_bonus = 1.0 + (today_commits * 0.1)
    
    total_exp = base_exp * streak_multiplier * health_multiplier * activity_bonus
    return int(total_exp)


def get_evolution_requirements():
    """Requirements to reach each stage (not to evolve FROM them)"""
    return {
        "EGG": {"days": 0, "exp": 0},
        "HATCHLING": {"days": 1, "exp": 50},
        "YOUNG": {"days": 3, "exp": 200},
        "ADULT": {"days": 7, "exp": 500},
        "LEGENDARY": {"days": 14, "exp": 1000}
    }


def get_pet_display(stage, health_state, days_since_last):
    stage_emojis = {
        "EGG": "🥚",
        "HATCHLING": "🐣",
        "YOUNG": "🐤", 
        "ADULT": "🐦",
        "LEGENDARY": "🦅"
    }
    
    health_indicators = {
        "HEALTHY": "✨",
        "GOOD": "😊",
        "TIRED": "😴",
        "WEAK": "😵",
        "CRITICAL": "🆘",
        "DEAD": "💀"
    }
    
    base_emoji = stage_emojis.get(stage, "🥚")
    health_emoji = health_indicators.get(health_state, "😊")
    
    if health_state == "DEAD":
        return f"{health_emoji} {base_emoji} (DEAD - {days_since_last} days)"
    elif health_state == "CRITICAL":
        return f"{health_emoji} {base_emoji} (CRITICAL - {days_since_last} days)"
    elif health_state == "WEAK":
        return f"{health_emoji} {base_emoji} (Weak - {days_since_last} days)"
    elif health_state == "TIRED":
        return f"{health_emoji} {base_emoji} (Tired - {days_since_last} days)"
    else:
        return f"{health_emoji} {base_emoji} (Healthy)"
    
def can_evolve(stage, days_alive, total_experience, current_streak, days_in_current_stage):
    """Check if pet meets requirements to evolve TO the given stage"""
    requirements = get_evolution_requirements()
    req = requirements.get(stage, {"days": 999, "exp": 999999})
    
    # Must be in current stage for at least 1 day before evolving
    if days_in_current_stage < 1:
        return False
    
    # Apply streak bonus to effective days
    streak_bonus = get_streak_multiplier(current_streak)
    effective_days = days_alive * streak_bonus
    
    return effective_days >= req["days"] and total_experience >= req["exp"]

def check_devolution(pet_data, days_since_last):
    """Check if pet should devolve due to neglect"""
    current_stage = pet_data["current_stage"]
    resilience = get_stage_resilience(current_stage)
    stage_order = ["EGG", "HATCHLING", "YOUNG", "ADULT", "LEGENDARY"]
    current_index = get_stage_index(current_stage)
    
    # Reset consecutive inactive days if there was a commit
    if days_since_last == 0:
        pet_data["consecutive_inactive_days"] = 0
        pet_data["devolution_warnings"] = 0
        return current_stage, None
    
    # Track consecutive inactive days
    consecutive_days = pet_data.get("consecutive_inactive_days", 0)
    
    # If it's been more days than resilience allows
    if days_since_last > resilience:
        days_over = days_since_last - resilience
        
        # Devolve if significantly over limit and not already at lowest stage
        if days_over >= 3 and current_index > 0:
            new_stage = stage_order[current_index - 1]
            devolution_message = f"😢 DEVOLUTION! {current_stage} → {new_stage} (inactive for {days_since_last} days)"
            
            # Reset stage days and warnings
            pet_data["days_in_current_stage"] = 0
            pet_data["devolution_warnings"] = 0
            pet_data["consecutive_inactive_days"] = days_since_last
            
            # Record devolution in history
            devolution_event = {
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "from_stage": current_stage,
                "to_stage": new_stage,
                "reason": "neglect",
                "days_neglected": days_since_last
            }
            pet_data["evolution_history"].append(devolution_event)
            
            return new_stage, devolution_message
        
        # Issue warning if close to devolution
        elif days_over >= 1:
            pet_data["devolution_warnings"] = pet_data.get("devolution_warnings", 0) + 1
            days_until_devolution = 3 - days_over  # Will devolve when days_over reaches 3
            if days_until_devolution > 0:
                devolution_message = f"⚠️  WARNING: Pet will devolve in {days_until_devolution} days without commits!"
            else:
                devolution_message = f"⚠️  CRITICAL: Pet will devolve tomorrow without commits!"
            return current_stage, devolution_message
    
    # Update consecutive inactive days
    pet_data["consecutive_inactive_days"] = days_since_last
    
    return current_stage, None

def check_evolution(pet_data, days_alive, total_experience, current_streak, days_since_last):
    """Check if pet should evolve to next stage"""
    current_stage = pet_data["current_stage"]
    stage_order = ["EGG", "HATCHLING", "YOUNG", "ADULT", "LEGENDARY"]
    current_index = get_stage_index(current_stage)
    
    # Can't evolve if at max stage
    if current_index >= len(stage_order) - 1:
        return current_stage, None
    
    # Can't evolve if inactive for too long (must have committed recently)
    if days_since_last > 3:
        return current_stage, None
    
    next_stage = stage_order[current_index + 1]
    days_in_stage = pet_data.get("days_in_current_stage", 0)
    
    # Check if pet meets evolution requirements
    if can_evolve(next_stage, days_alive, total_experience, current_streak, days_in_stage):
        evolution_msg = f"🎉 EVOLUTION! {current_stage} → {next_stage}"
        
        # Record evolution in history
        evolution_event = {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "from_stage": current_stage,
            "to_stage": next_stage,
            "days_alive": days_alive,
            "experience": total_experience,
            "reason": "evolution"
        }
        pet_data["evolution_history"].append(evolution_event)
        
        # Reset stage days
        pet_data["days_in_current_stage"] = 0
        
        return next_stage, evolution_msg
    
    return current_stage, None

def determine_final_stage(pet_data, days_alive, total_experience, current_streak, days_since_last):
    """Determine the final stage after checking both devolution and evolution"""
    
    # First check for devolution (higher priority)
    stage_after_devolution, devolution_msg = check_devolution(pet_data, days_since_last)
    
    # If devolved, return immediately
    if stage_after_devolution != pet_data["current_stage"]:
        return stage_after_devolution, devolution_msg
    
    # Then check for evolution (only if not devolving)
    stage_after_evolution, evolution_msg = check_evolution(
        pet_data, days_alive, total_experience, current_streak, days_since_last
    )
    
    # Return evolution result or warning message
    if evolution_msg:
        return stage_after_evolution, evolution_msg
    else:
        return stage_after_devolution, devolution_msg

def check_achievements(pet_data, current_streak, days_alive):
    achievements = pet_data.get("achievements", [])
    new_achievements = []
    
    achievement_conditions = {
        "first_hatch": lambda: pet_data["current_stage"] != "EGG" and "first_hatch" not in achievements,
        "week_streak": lambda: current_streak >= 7 and "week_streak" not in achievements,
        "month_streak": lambda: current_streak >= 30 and "month_streak" not in achievements,
        "ancient": lambda: days_alive >= 100 and "ancient" not in achievements,
        "legendary": lambda: pet_data["current_stage"] == "LEGENDARY" and "legendary" not in achievements,
        "dedication": lambda: pet_data["total_experience"] >= 5000 and "dedication" not in achievements,
        "survivor": lambda: pet_data["current_stage"] == "LEGENDARY" and days_alive >= 50 and "survivor" not in achievements,
        "comeback": lambda: len([e for e in pet_data["evolution_history"] if e.get("reason") == "evolution"]) > len([e for e in pet_data["evolution_history"] if e.get("reason") == "neglect"]) and "comeback" not in achievements
    }
    
    for achievement, condition in achievement_conditions.items():
        if condition():
            new_achievements.append(achievement)
            achievements.append(achievement)
    
    return achievements, new_achievements
    
def update_pet():
    try:
        # Load existing pet data
        pet_data = load_pet_save()
        
        # Get GitHub contribution data
        response = make_graphql_request()
        adjusted_contributions = get_adjusted_contributions(response, pet_start_date)
        current_streak = calculate_current_streak(adjusted_contributions)
        days_since_last = calculate_days_since_last_contribution(adjusted_contributions)
        
        # Calculate pet stats
        days_alive = calculate_days_alive(pet_start_date, today)
        health_state = determine_health_state(days_since_last)
        
        # Calculate experience gain (only if not dead)
        if not pet_data["is_first_run"] and health_state != "DEAD":
            exp_gain = calculate_exp_gain(current_streak, days_since_last, health_state, adjusted_contributions)
            pet_data["total_experience"] += exp_gain
        else:
            exp_gain = 0
            if pet_data["is_first_run"]:
                pet_data["is_first_run"] = False
        
        # Update basic stats
        pet_data["days_alive"] = days_alive
        pet_data["health_state"] = health_state
        pet_data["days_since_last_commit"] = days_since_last
        pet_data["best_streak"] = max(pet_data["best_streak"], current_streak)
        pet_data["last_update"] = today.strftime("%Y-%m-%d")
        
        # Update last commit date if there was activity today
        if days_since_last == 0:
            pet_data["last_commit_date"] = today.strftime("%Y-%m-%d")
        
        # Calculate total commits (excluding bot commits)
        total_commits = sum(day["adjusted_count"] for day in adjusted_contributions)
        pet_data["total_commits"] = total_commits
        
        # Determine stage (handles both evolution and devolution)
        old_stage = pet_data["current_stage"]
        new_stage, stage_message = determine_final_stage(
            pet_data, days_alive, pet_data["total_experience"], current_streak, days_since_last
        )
        
        # Update stage if changed
        if old_stage != new_stage:
            pet_data["current_stage"] = new_stage
            # days_in_current_stage is already reset in the evolution/devolution functions
        else:
            # Increment days in current stage only if stage didn't change
            pet_data["days_in_current_stage"] = pet_data.get("days_in_current_stage", 0) + 1
        
        # Update stage days counter
        pet_data["stage_days"][pet_data["current_stage"]] = pet_data["stage_days"].get(pet_data["current_stage"], 0) + 1
        
        # Check achievements
        achievements, new_achievements = check_achievements(pet_data, current_streak, days_alive)
        pet_data["achievements"] = achievements
        
        # Display pet status
        pet_display = get_pet_display(pet_data["current_stage"], health_state, days_since_last)
        resilience = get_stage_resilience(pet_data["current_stage"])
        
        # Get next stage requirements for display
        stage_order = ["EGG", "HATCHLING", "YOUNG", "ADULT", "LEGENDARY"]
        current_index = get_stage_index(pet_data["current_stage"])
        next_stage_info = ""
        if current_index < len(stage_order) - 1:
            next_stage = stage_order[current_index + 1]
            reqs = get_evolution_requirements()[next_stage]
            next_stage_info = f"\n📊 Next Stage Requirements: {next_stage} (Days: {reqs['days']}, Exp: {reqs['exp']})"
        
        print("=" * 60)
        print(f"🐾 GITHUB TAMAGOTCHI STATUS")
        print("=" * 60)
        print(f"Pet: {pet_display}")
        print(f"Stage: {pet_data['current_stage']} (Day {pet_data['days_in_current_stage']} in this stage)")
        print(f"Health: {health_state}")
        print(f"Days Alive: {days_alive}")
        print(f"Experience: {pet_data['total_experience']} (+{exp_gain})")
        print(f"Current Streak: {current_streak} days")
        print(f"Best Streak: {pet_data['best_streak']} days")
        print(f"Days Since Last Real Commit: {days_since_last}")
        print(f"Stage Resilience: Can survive {resilience} days without commits")
        print(f"Total Real Commits: {total_commits}")
        
        if next_stage_info:
            print(next_stage_info)
        
        if stage_message:
            print(f"\n{stage_message}")
        
        if new_achievements:
            print(f"\n🏆 NEW ACHIEVEMENTS: {', '.join(new_achievements)}")
        
        if pet_data["evolution_history"]:
            print(f"\n📈 Recent Evolution History:")
            for evo in pet_data["evolution_history"][-3:]:
                arrow = "⬆️" if evo.get("reason") == "evolution" else "⬇️"
                print(f"  {evo['date']}: {arrow} {evo['from_stage']} -> {evo['to_stage']}")
        
        # Survival tips based on health
        if health_state in ["WEAK", "CRITICAL", "DEAD"]:
            print(f"\n💡 TIP: Your pet needs attention! Commit some code to restore its health.")
        elif days_since_last > resilience // 2:
            print(f"\n💡 TIP: Your pet will start getting weak after {resilience} days without commits.")
        
        print("=" * 60)
        
        # Save updated data
        save_pet_data(pet_data)
        
        return pet_data
        
    except Exception as e:
        print(f"Error updating pet: {e}")
        return None

if __name__ == "__main__":
    update_pet()