"""Known chain brands in Maine: regex on normalized name -> brand label.

Adapted from ct-eats/pipeline/brands.py (from wi-eats and chi-eats); Maine and New England chains added.
"""
import re

BRANDS = [
    ("Dunkin'", r"^DUNKIN"), ("Subway", r"^SUBWAY"), ("McDonald's", r"^MC ?DONALDS"), ("Starbucks", r"^STARBUCK"),
    ("Jimmy John's", r"^JIMMY JOHN"), ("Burger King", r"^BURGER KING"), ("Taco Bell", r"^TACO BELL"),
    ("Potbelly", r"^POTBELLY"), ("Wingstop", r"^WING ?STOP"), ("Chipotle", r"^CHIPOTLE"), ("Popeyes", r"^POPEYE"),
    ("Wendy's", r"^WENDYS"), ("Panda Express", r"^PANDA EXPRESS"), ("Chick-fil-A", r"^CHICK FIL"), ("Domino's", r"^DOMINO"), ("Jersey Mike's", r"^JERSEY MIKE"),
    ("Panera Bread", r"^PANERA"), ("Little Caesars", r"^LITTLE CAESAR"),
    ("Papa John's", r"^PAPA JOHN"), ("KFC", r"^KFC|^KENTUCKY FRIED"), ("Tropical Smoothie Cafe", r"^TROPICAL SMOOTHIE"),
    ("Buffalo Wild Wings", r"^BUFFALO WILD"), ("Five Guys", r"^FIVE GUYS"), ("Raising Cane's", r"^RAISING CANE"),
    ("Auntie Anne's", r"^AUNTIE ANNE"), ("Qdoba", r"^QDOBA"),
    ("Noodles & Company", r"^NOODLES (?:AND )?CO(?:MPANY)?\b"), ("Smoothie King", r"^SMOOTHIE KING"), ("Firehouse Subs", r"^FIREHOUSE SUB"),
    ("IHOP", r"^IHOP"), ("Denny's", r"^DENNYS"), ("Sonic", r"^SONIC DRIVE|^SONIC$"), ("Insomnia Cookies", r"^INSOMNIA COOKIE"),
    ("Crumbl", r"^CRUMBL"), ("Dairy Queen", r"^DAIRY QUEEN|^DQ GRILL|^DQ$"), ("Baskin-Robbins", r"^BASKIN"), ("Krispy Kreme", r"^KRISPY KREME"),
    ("Chuck E. Cheese", r"^CHUCK E CHEESE"), ("Nothing Bundt Cakes", r"^NOTHING BUNDT"),
    ("Hooters", r"^HOOTERS"), ("Cheesecake Factory", r"^CHEESECAKE FACTORY"), ("P.F. Chang's", r"^P ?F CHANG"), ("Maggiano's", r"^MAGGIANO"),
    ("Ruth's Chris", r"^RUTHS CHRIS"), ("Morton's", r"^MORTONS THE STEAK|^MORTONS STEAK"), ("Applebee's", r"^APPLEBEE"), ("Chili's", r"^CHILIS"), ("Olive Garden", r"^OLIVE GARDEN"), ("Red Lobster", r"^RED LOBSTER"),
    ("Jamba", r"^JAMBA"), ("Cinnabon", r"^CINNABON"), ("Pizza Hut", r"^PIZZA HUT"), ("Arby's", r"^ARBYS"),
    ("Checkers", r"^CHECKERS DRIVE|^CHECKERS AND RALLY|^CHECKERS$"), ("MOD Pizza", r"^MOD PIZZA"), ("Tim Hortons", r"^TIM HORTON"),
    ("Peet's Coffee", r"^PEETS"), ("Cava", r"^CAVA$|^CAVA (?:MEDITERRANEAN|GRILL)"), ("Blaze Pizza", r"^BLAZE PIZZA"),
    # national chains with New England stores (the Wisconsin-only list was removed: a "Casey's Irish Pub" isn't the gas station)
    ("Taco John's", r"^TACO JOHN"), ("A&W", r"^A (?:AND )?W(?: RESTAURANTS?| ALL AMERICAN| DRIVE| ROOT| FAMILY| RESTAURANT| KITCHEN)?$|^A (?:AND )?W (?:RESTAURANT|ALL AMERICAN|DRIVE IN|ROOT BEER|FAMILY)"), ("Texas Roadhouse", r"^TEXAS ROADHOUSE"), ("Red Robin", r"^RED ROBIN"),
    ("Marco's Pizza", r"^MARCOS PIZZA"),
    ("Cracker Barrel", r"^CRACKER BARREL"), ("Outback Steakhouse", r"^OUTBACK STEAK"), ("LongHorn Steakhouse", r"^LONGHORN STEAK"),
    ("Pita Pit", r"^PITA PIT"), ("Cold Stone Creamery", r"^COLD STONE"),
    ("Golden Corral", r"^GOLDEN CORRAL"), ("Einstein Bros. Bagels", r"^EINSTEIN BRO"), ("Quiznos", r"^QUIZNO"), ("Dickey's Barbecue Pit", r"^DICKEYS"), ("Blimpie", r"^BLIMPIE"), ("Dave's Hot Chicken", r"^DAVES HOT CHICKEN"),
    ("Sbarro", r"^SBARRO"), ("Orange Julius", r"^ORANGE JULIUS"),
    ("Great Harvest", r"^GREAT HARVEST"), ("Teriyaki Madness", r"^TERIYAKI MADNESS"), ("First Watch", r"^FIRST WATCH"), ("Uno Pizzeria", r"^UNO PIZZERIA|^UNO CHICAGO"),
    ("TGI Fridays", r"^TGI FRIDAY"), ("Mooyah", r"^MOOYAH"), ("Charleys Cheesesteaks", r"^CHARLEYS (?:PHILLY|CHEESESTEAK)"), ("Smashburger", r"^SMASHBURGER"), ("Mission BBQ", r"^MISSION BBQ"), ("Chesters Chicken", r"^CHESTERS (?:FRIED )?CHICKEN"),
    ("Krispy Krunchy Chicken", r"^KRISPY KRUNCHY"),
    ("Wendy's", r"^WENDYS"),
    ("Pardon My Cheesesteak", r"^PARDON MY CHEESESTEAK"), ("MrBeast Burger", r"^MR ?BEAST"), ("Farmer's Fridge", r"^FARMERS FRIDGE"),
    ("Mad Chicken", r"^MAD CHICKEN"), ("It's Just Wings", r"^ITS JUST WINGS"), ("Banda Burrito", r"^BANDA BURRITO"),
    ("Tenderfix", r"^TENDERFIX"), ("The Meltdown", r"^(?:THE )?MELTDOWN$"),
    ("7-Eleven", r"^7 ELEVEN"),  # Maine chains
    ("Amato's", r"^AMATOS"), ("Pat's Pizza", r"^PATS PIZZA"), ("Otto Pizza", r"^OTTO PIZZA|^OTTO$"), ("Portland Pie Co.", r"^PORTLAND PIE"),
    ("Gritty McDuff's", r"^GRITTY"), ("Sea Dog Brewing", r"^SEA DOG BREW"), ("The Holy Donut", r"^(?:THE )?HOLY DONUT"),
    ("Moe's Italian Sandwiches", r"^MOES ITALIAN"), ("Flatbread Company", r"^FLATBREAD(?: COMPANY| CO)?$|^FLATBREAD COMPANY"),
    ("Mr. Bagel", r"^MR BAGEL"), ("Anania's", r"^ANANIAS"), ("Bissell Brothers", r"^BISSELL BROTHERS"),
    ("Hannaford", r"^HANNAFORD"), ("Irving", r"^IRVING(?: OIL| MAINWAY| CIRCLE K)?$|^IRVING OIL"), ("Circle K", r"^CIRCLE K"),
    ("Big Apple", r"^BIG APPLE(?: FOOD STORE)?$"), ("Rite Aid", r"^RITE AID"), ("Walmart", r"^WALMART|^WAL MART"),
    ("Cousins Maine Lobster", r"^COUSINS MAINE LOBSTER"), ("Luke's Lobster", r"^LUKES LOBSTER"), ("Bob's Clam Hut", r"^BOBS CLAM HUT"),
    # New England chains
    ("Frank Pepe Pizzeria Napoletana", r"^(?:FRANK )?PEPES PIZZERIA|^FRANK PEPE"), ("Sally's Apizza", r"^SALLYS APIZZA"),
    ("Colony Grill", r"^COLONY GRILL"), ("Wood-n-Tap", r"^WOOD N TAP"), ("Plan B Burger Bar", r"^PLAN B BURGER|^PLAN B$"),
    ("Archie Moore's", r"^ARCHIE MOORE"), ("Duchess", r"^DUCHESS(?: RESTAURANT)?$"), ("Friendly's", r"^FRIENDLYS"),
    ("Bertucci's", r"^BERTUCCI"), ("Papa Gino's", r"^PAPA GINO"), ("D'Angelo", r"^D ?ANGELOS?(?: GRILLED| SANDWICH)|^D ?ANGELOS?$"),
    ("Moe's Southwest Grill", r"^MOES SOUTHWEST"), ("99 Restaurant", r"^99 RESTAURANT|^NINETY NINE"), ("Ruby Tuesday", r"^RUBY TUESDAY"),
    ("Bonefish Grill", r"^BONEFISH"), ("Carrabba's", r"^CARRABBA"), ("Max Burger", r"^MAX BURGER"), ("Rizzuto's", r"^RIZZUTOS"),
    ("J. Timothy's", r"^J TIMOTHYS"), ("Bruegger's", r"^BRUEGGER"), ("Au Bon Pain", r"^AU BON PAIN"), ("Cosi", r"^COSI$"),
    ("Shake Shack", r"^SHAKE SHACK"), ("Sweetgreen", r"^SWEETGREEN"), ("Ben & Jerry's", r"^BEN (?:AND )?JERRYS"),
    ("Carvel", r"^CARVEL"), ("Rita's", r"^RITAS(?: ITALIAN ICE)?$|^RITAS ITALIAN"), ("Cumberland Farms", r"^CUMBERLAND FARMS"),
    ("Honey Dew Donuts", r"^HONEY DEW"), ("Bess Eaton", r"^BESS EATON"), ("Nathan's Famous", r"^NATHANS"), ("Wingstop", r"^WINGSTOP"),
    ("Bareburger", r"^BAREBURGER"), ("Tony's Di Napoli", r"^TONYS DI NAPOLI"), ("Ninety Nine", r"^NINETY NINE"),
    ("City Steam Brewery", r"^CITY STEAM"), ("Little Pub", r"^LITTLE PUB"), ("Burger Joint", r"^BURGER JOINT"),
    ("Pizzeria Uno", r"^PIZZERIA UNO"), ("Joe's Crab Shack", r"^JOES CRAB"), ("Kona Grill", r"^KONA GRILL"), ("Panda Express", r"^PANDA EXPRESS"),
    ("Stop & Shop", r"^STOP (?:AND )?SHOP"), ("Big Y", r"^BIG Y\b"), ("ShopRite", r"^SHOP ?RITE"), ("Price Chopper", r"^PRICE CHOPPER"),
    ("Xtra Mart", r"^XTRA ?MART"), ("Alltown", r"^ALLTOWN"), ("Tim Hortons", r"^TIM HORTON"), ("Dave's Hot Chicken", r"^DAVES HOT CHICKEN"),
    ("Starbucks", r"^STARBUCK"), ("Grade A ShopRite", r"^GRADE A"), ("Whole Foods Market", r"^WHOLE FOODS"), ("Trader Joe's", r"^TRADER JOE"),
    ("Planet Pizza", r"^PLANET PIZZA"), ("Taste of China", r"^TASTE OF CHINA$"), ("Chuck E. Cheese", r"^CHUCK E"),
]
_C = [(b, re.compile(p)) for b, p in BRANDS]

# distinctive brands also recognized mid-name ("HALE FAMILY MCDONALDS", "SAII BABA DUNKIN")
_ANYWHERE = [(b, re.compile(p)) for b, p in [("McDonald's", r"\bMC ?DONALDS\b"), ("Dunkin'", r"\bDUNKIN\b"), ("Starbucks", r"\bSTARBUCKS\b"),
             ("Wingstop", r"\bWING ?STOP\b"), ("Popeyes", r"\bPOPEYES\b"), ("Chipotle", r"\bCHIPOTLE\b"),
             ("Jimmy John's", r"\bJIMMY JOHNS\b"), ("Taco Bell", r"\bTACO BELL\b")]]


def brand_of(nkey, *more):
    """Brand from the display name, else from Overture's brand label."""
    keys = [k for k in [nkey] + [m for m in more if isinstance(m, str)] if isinstance(k, str)]
    for k in keys:
        for part in [k or ""] + [p.strip() for p in (k or "").split("/")]:
            for b, p in _C:
                if p.search(part):
                    return b
    for k in keys:
        for b, p in _ANYWHERE:
            if p.search(k or ""):
                return b
    return None
