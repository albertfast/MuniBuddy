#/MuniBuddy/backend/app/routers/routers.py
routes = {
    "YELLOW": {
        "iconDown": "yellow-sfo",
        "iconUp": "yellow-antc",
        "stations": [
            "MLBR", "SFIA", "SBRN", "SSAN", "COLM", "DALY", "BALB", "GLEN", "24TH",
            "16TH", "CIVC", "POWL", "MONT", "EMBR", "WOAK", "12TH", "19TH", "MCAR",
            "ROCK", "ORIN", "LAFY", "WCRK", "PHIL", "CONC", "NCON", "PITT", "PCTR", "ANTC"
        ]
    },
    "ORANGE": {
        "iconDown": "orange-warm",
        "iconUp": "orange-rich",
        "stations": [
            "BERY", "MLPT", "WARM", "FRMT", "UCTY", "SHAY", "HAYW", "BAYF", "SANL", "COLS",
            "FTVL", "LAKE", "12TH", "19TH", "MCAR", "ASHB", "DBRK", "NBRK", "PLZA", "DELN", "RICH"
        ]
    },
    "GREEN": {
        "iconDown": "green-warm",
        "iconUp": "green-daly",
        "stations": [
            "WARM", "FRMT", "UCTY", "SHAY", "HAYW", "BAYF", "SANL", "COLS", "FTVL", "LAKE",
            "WOAK", "EMBR", "MONT", "POWL", "CIVC", "16TH", "24TH", "GLEN", "BALB", "DALY"
        ]
    },
    "RED": {
        "iconDown": "red-sfo",
        "iconUp": "red-rich",
        "stations": [
            "MLBR", "SBRN", "SSAN", "COLM", "DALY", "BALB", "GLEN", "24TH", "16TH", "CIVC",
            "POWL", "MONT", "EMBR", "WOAK", "12TH", "19TH", "MCAR", "ASHB", "DBRK", "NBRK",
            "PLZA", "DELN", "RICH"
        ]
    },
    "BLUE": {
        "iconDown": "blue-daly",
        "iconUp": "blue-dubl",
        "stations": [
            "DALY", "BALB", "GLEN", "24TH", "16TH", "CIVC", "POWL", "MONT", "EMBR", "WOAK",
            "LAKE", "FTVL", "COLS", "SANL", "BAYF", "CAST", "WDUB", "DUBL"
        ]
    },
    "BEIGE": {
        "iconDown": "beige-oakl",
        "iconUp": "beige-cols",
        "stations": ["OAKL", "COLS"]
    }
}
