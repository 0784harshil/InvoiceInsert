"""
Smart Intelligent Department Classifier Engine for CRE POS
Maps item descriptions and keywords to valid CRE POS Departments:
BEER, Candy, CBD, Cigs, Cigarilo, CIGAR, LIQUOR, SODA, VAPE, WINE, Rolling, MISC.
"""

import re
from typing import List, Set, Dict

VALID_CRE_DEPARTMENTS = [
    'BEER', 'Candy', 'CBD', 'Cigs', 'Cigarilo', 'CIGAR', 'Carton',
    'LIQUOR', 'SODA', 'VAPE', 'WINE', 'Rolling', 'SNUS', 'Pouch',
    'TOBACCO', 'Butane', 'Lighter', 'MISC'
]


class DepartmentClassifier:
    """Classifies products into valid CRE POS Departments based on description and package keywords."""

    @classmethod
    def classify_department(cls, description: str, raw_upc: str = "") -> str:
        text = str(description).upper()

        # 1. Candy / Snack / Gum Keywords
        if re.search(r'\b(GUM|GUMMI|GUSHERS|BEARS|CANDY|HARIBO|BUTTERFINGER|AIRHEADS|ALBANESE|SKITTLES|SNICKERS|M&M|REESE|TWIX|DENTYNE|EXTRA|TIC TAC|BROOKSIDE|FRUIT|SOUR|CHOCOLATE|SWEET)\b', text):
            return 'Candy'

        # 2. Beer / Malt Beverage Keywords
        if re.search(r'\b(BEER|ALE|LAGER|IPA|STOUT|SELTZER|TRULY|COORS|HEINEKEN|MODELO|PACIFICO|CORONA|BUD|BUDWEISER|LITE|MILLER|MICHELOB|STELLA|DOS EQUIS|GUINNESS|VICTORIA|ESTRELLA|BLUE MOON|SIERRA|LAGUNITAS|WARPIGS|CLUBTAILS|HACKER|ASAHI|HAMMS|PREMIER|FOSTERS|BUSCH|NATURAL|PBR|FOUNDERS|ELYSIAN)\b', text):
            return 'BEER'

        # 3. Soda / Energy / Non-Alcoholic Beverage
        if re.search(r'\b(SODA|COKE|PEPSI|SPRITE|7UP|DR PEPPER|MOUNTAIN DEW|MONSTER|RED BULL|CELSIUS|GATORADE|POWERADE|JUICE|WATER|TEA|CELSIUS|ROCKSTAR|ENERGY)\b', text):
            return 'SODA'

        # 4. Liquor / Spirits
        if re.search(r'\b(VODKA|WHISKEY|WHISKY|TEQUILA|RUM|GIN|COGNAC|BOURBON|SCOTCH|BRANDY|LIQUOR|HENNESSY|PATRON|TITOS|JACK DANIELS|JIM BEAM|FIREBALL|JAGERMEISTER|CROWN)\b', text):
            return 'LIQUOR'

        # 5. Wine
        if re.search(r'\b(WINE|CHARDONNAY|CABERNET|MERLOT|PINOT|SAUVIGNON|PROSECCO|MOSCATO|CHAMPAGNE|ROSÉ|ROSE|SUTTER|BAREFOOT|YELLOW TAIL)\b', text):
            return 'WINE'

        # 6. Tobacco / Cigarettes / Cigars
        if re.search(r'\b(MARLBORO|CAMEL|NEWPORT|WINSTON|PALL MALL|L&M)\b', text):
            return 'Cigs'
        if re.search(r'\b(SWISHER|BACKWOODS|DUTCH|GAME|WHITE OWL|FOIL|CIGAR|CIGARILLO)\b', text):
            return 'Cigarilo'
        if re.search(r'\b(VAPE|JUUL|PUFF|DISPOSABLE|POD|FLUM|ELFBAR)\b', text):
            return 'VAPE'
        if re.search(r'\b(CBD|HEMP|DELTA)\b', text):
            return 'CBD'

        return 'MISC'
