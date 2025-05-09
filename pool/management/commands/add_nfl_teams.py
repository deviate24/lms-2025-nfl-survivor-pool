from django.core.management.base import BaseCommand
from pool.models import Team

class Command(BaseCommand):
    help = 'Adds all 32 NFL teams for the 2025 season'

    def handle(self, *args, **options):
        # Clear existing teams
        Team.objects.all().delete()
        
        # AFC East
        Team.objects.create(name="Buffalo Bills", conference="AFC", division="East", abbreviation="BUF")
        Team.objects.create(name="Miami Dolphins", conference="AFC", division="East", abbreviation="MIA")
        Team.objects.create(name="New England Patriots", conference="AFC", division="East", abbreviation="NE")
        Team.objects.create(name="New York Jets", conference="AFC", division="East", abbreviation="NYJ")
        
        # AFC North
        Team.objects.create(name="Baltimore Ravens", conference="AFC", division="North", abbreviation="BAL")
        Team.objects.create(name="Cincinnati Bengals", conference="AFC", division="North", abbreviation="CIN")
        Team.objects.create(name="Cleveland Browns", conference="AFC", division="North", abbreviation="CLE")
        Team.objects.create(name="Pittsburgh Steelers", conference="AFC", division="North", abbreviation="PIT")
        
        # AFC South
        Team.objects.create(name="Houston Texans", conference="AFC", division="South", abbreviation="HOU")
        Team.objects.create(name="Indianapolis Colts", conference="AFC", division="South", abbreviation="IND")
        Team.objects.create(name="Jacksonville Jaguars", conference="AFC", division="South", abbreviation="JAX")
        Team.objects.create(name="Tennessee Titans", conference="AFC", division="South", abbreviation="TEN")
        
        # AFC West
        Team.objects.create(name="Denver Broncos", conference="AFC", division="West", abbreviation="DEN")
        Team.objects.create(name="Kansas City Chiefs", conference="AFC", division="West", abbreviation="KC")
        Team.objects.create(name="Las Vegas Raiders", conference="AFC", division="West", abbreviation="LV")
        Team.objects.create(name="Los Angeles Chargers", conference="AFC", division="West", abbreviation="LAC")
        
        # NFC East
        Team.objects.create(name="Dallas Cowboys", conference="NFC", division="East", abbreviation="DAL")
        Team.objects.create(name="New York Giants", conference="NFC", division="East", abbreviation="NYG")
        Team.objects.create(name="Philadelphia Eagles", conference="NFC", division="East", abbreviation="PHI")
        Team.objects.create(name="Washington Commanders", conference="NFC", division="East", abbreviation="WAS")
        
        # NFC North
        Team.objects.create(name="Chicago Bears", conference="NFC", division="North", abbreviation="CHI")
        Team.objects.create(name="Detroit Lions", conference="NFC", division="North", abbreviation="DET")
        Team.objects.create(name="Green Bay Packers", conference="NFC", division="North", abbreviation="GB")
        Team.objects.create(name="Minnesota Vikings", conference="NFC", division="North", abbreviation="MIN")
        
        # NFC South
        Team.objects.create(name="Atlanta Falcons", conference="NFC", division="South", abbreviation="ATL")
        Team.objects.create(name="Carolina Panthers", conference="NFC", division="South", abbreviation="CAR")
        Team.objects.create(name="New Orleans Saints", conference="NFC", division="South", abbreviation="NO")
        Team.objects.create(name="Tampa Bay Buccaneers", conference="NFC", division="South", abbreviation="TB")
        
        # NFC West
        Team.objects.create(name="Arizona Cardinals", conference="NFC", division="West", abbreviation="ARI")
        Team.objects.create(name="Los Angeles Rams", conference="NFC", division="West", abbreviation="LAR")
        Team.objects.create(name="San Francisco 49ers", conference="NFC", division="West", abbreviation="SF")
        Team.objects.create(name="Seattle Seahawks", conference="NFC", division="West", abbreviation="SEA")
        
        self.stdout.write(self.style.SUCCESS('Successfully added all 32 NFL teams'))
