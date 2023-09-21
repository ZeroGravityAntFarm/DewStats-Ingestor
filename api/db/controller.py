from sqlalchemy.orm import Session
from db.models import models

#Create Match Stats
def create_stats(db: Session, stats: str):
    #Check if server record exist already (Not much unique data to go by here so we filter on name and player host)
    server = db.query(models.Server).filter(models.Server.serverName == stats["serverName"]).filter(models.Server.hostPlayer == stats["hostPlayer"]).first()

    winners = getWinner(stats)

    if not server:
        #Create server record
        server = models.Server(serverName=stats["serverName"], 
                            serverVersion=stats["gameVersion"], 
                            serverPort=stats["serverPort"], 
                            port=stats["port"], 
                            hostPlayer=stats["hostPlayer"])
        db.add(server)
        db.commit()

    #Create match record
    game = models.Game(serverId=server.id, 
                       sprintEnabled=stats["game"]["sprintEnabled"], 
                       sprintUnlimitedEnabled=stats["game"]["sprintUnlimitedEnabled"], 
                       maxPlayers=stats["game"]["maxPlayers"], 
                       mapName=stats["game"]["mapName"], 
                       mapFile=stats["game"]["mapFile"], 
                       variant=stats["game"]["variant"], 
                       variantType=stats["game"]["variantType"], 
                       teamGame=stats["game"]["teamGame"])
    db.add(game)
    db.commit()

    #Iterate over players in match and create records for them. Create a new record for each game event as player records are unique. For some reason player match data is stored here in the form of team id?
    for playerData in stats["players"]:
        if playerData["uid"] in winners:
            player = models.Player(playerName=playerData["name"],
                               clientName=playerData["clientName"],
                               serviceTag=playerData["serviceTag"],
                               playerIp=playerData["ip"],
                               team=playerData["team"],
                               playerIndex=playerData["playerIndex"],
                               playerUID=playerData["uid"],
                               primaryColor=playerData["primaryColor"],
                               playerExp=1)
            
        else:
            player = models.Player(playerName=playerData["name"],
                                clientName=playerData["clientName"],
                                serviceTag=playerData["serviceTag"],
                                playerIp=playerData["ip"],
                                team=playerData["team"],
                                playerIndex=playerData["playerIndex"],
                                playerUID=playerData["uid"],
                                primaryColor=playerData["primaryColor"])
            
        db.add(player)
        db.commit()


        #Add player match stats
        player_stats = models.PlayerGameStats(playerId=player.id, 
                                              gameId=game.id, 
                                              score=playerData["playerGameStats"]["score"], 
                                              kills=playerData["playerGameStats"]["kills"], 
                                              assists=playerData["playerGameStats"]["assists"], 
                                              deaths=playerData["playerGameStats"]["deaths"], 
                                              betrayals=playerData["playerGameStats"]["betrayals"], 
                                              timeAlive=playerData["playerGameStats"]["timeSpentAlive"], 
                                              suicides=playerData["playerGameStats"]["suicides"], 
                                              bestStreak=playerData["playerGameStats"]["bestStreak"],
                                              nemesisIndex=playerData["otherStats"]["nemesisIndex"],
                                              kingsKilled=playerData["otherStats"]["kingsKilled"],
                                              humansInfected=playerData["otherStats"]["humansInfected"],
                                              zombiesKilled=playerData["otherStats"]["zombiesKilled"],
                                              timeInHill=playerData["otherStats"]["timeInHill"],
                                              timeControllingHill=playerData["otherStats"]["timeControllingHill"],
                                              playerVersusPlayerKills=playerData["playerVersusPlayerKills"])
        
        db.add(player_stats)
        db.commit()

        #Add player id and match id to link table
        link_table = models.PlayersLink(gameId=game.id, playerId=player.id)

        db.add(link_table)
        db.commit()

        #Iterate over medals earned for our player in recent match
        for medal in playerData["playerMedals"]:
            medal = models.PlayerMedals(playerId=player.id, 
                                        gameId=game.id, 
                                        medalName=medal["medalName"], 
                                        count=medal["count"])

            db.add(medal)
            db.commit()

        #Iterate over player weapons for recent match
        for weapon in playerData["playerWeapons"]:
            weapon = models.PlayerWeapons(playerId=player.id, 
                                          gameId=game.id, 
                                          weaponName=weapon["weaponName"], 
                                          weaponIndex=weapon["weaponIndex"], 
                                          kills=weapon["kills"], 
                                          killedBy=weapon["killedBy"], 
                                          betrayalsWith=weapon["betrayalsWith"], 
                                          suicidesWith=weapon["suicidesWith"], 
                                          headShotsWith=weapon["headshotsWith"])
            
            db.add(weapon)
            db.commit()

    return True


#Return should be list of players as winners
def getWinner(gameData):

    #Get Slayer Winner
    if gameData["game"]["variantType"] == "slayer":
        if gameData["game"]["teamGame"]:
            
            #Find all teams in our game and sum their player scores
            teams = {}
            for player in gameData["players"]:
                if player["team"] not in teams:
                    teams[player["team"]] = player["playerGameStats"]["kills"]

                else:
                    teams[player["team"]] = player["playerGameStats"]["kills"] + teams[player["team"]]

            win_team = max(teams, key=teams.get)

            win_players = []
            for player in gameData["players"]:
                if player["team"] == win_team:
                    win_players.append(player["uid"])

            return win_players

        else:
            kills = 0
            winner = []
            for player in gameData["players"]:
                if player["playerGameStats"]["kills"] >= kills:
                    kills = player["playerGameStats"]["kills"]
                    winner.append(player["uid"])

            return winner
    
    #Get CTF Winner
    elif gameData["game"]["variantType"] == "ctf":
        teams = {}
        for player in gameData["players"]:
            if player["team"] not in teams:
                for medal in player["playerMedals"]:
                    if medal["medalName"] == "flag_captured":
                        teams[player["team"]] = medal["count"]

            else:
                for medal in player["playerMedals"]:
                    if medal["medalName"] == "flag_captured":
                        teams[player["team"]] = medal["count"] + teams[player["team"]]

        win_team = max(teams, key=teams.get)

        win_players = []
        for player in gameData["players"]:
            if player["team"] == win_team:
                win_players.append(player["uid"])

        return win_players

    elif gameData["game"]["variantType"] == "infection":
        #Iterate over players and get sum of zombies killed and humans infected
        #We will average these values to get a infection "score". This incentivizes players while human and infected (Thanks Mtn)
        perf_score = 0
        winner = ""
        for player in gameData["players"]:
            zombs = player["otherStats"]["zombiesKilled"]
            infects = player["otherStats"]["humansInfected"]
            player_score = zombs + infects / 2

            if player_score >= perf_score:
                winner = (player["uid"])
                perf_score = player_score

        return [winner]
    
    elif gameData["game"]["variantType"] == "vip":
        if gameData["game"]["teamGame"]:
            #This one gonna be fun
            return []
        
        else:
            #This one gonna be fun
            return []
    
    elif gameData["game"]["variantType"] == "koth":
        if gameData["game"]["teamGame"]:
             #Find all teams in our game and sum their player hill time
            teams = {}
            for player in gameData["players"]:
                if player["team"] not in teams:
                    teams[player["team"]] = player["otherStats"]["timeControllingHill"]

                else:
                    teams[player["team"]] = player["otherStats"]["timeControllingHill"] + teams[player["team"]]

            #This will return last team in loop if in case of tie
            win_team = max(teams, key=teams.get)

            win_players = []
            for player in gameData["players"]:
                if player["team"] == win_team:
                    win_players.append(player["uid"])

            return win_players
        
        else:
            time = 0
            winner = []
            for player in gameData["players"]:
                if player["otherStats"]["timeControllingHill"] >= time:
                    time = ["otherStats"]["timeControllingHill"]
                    winner.append(player["uid"])
    
    elif gameData["game"]["variantType"] == "oddball":
        if gameData["game"]["teamGame"]:
            #Iterate over teams and find team sum max score
            return []
        
        else:
            #Iterate over players and find max score
            return []
 
    elif gameData["game"]["variantType"] == "territories":
        if gameData["game"]["teamGame"]:
            #Iterate over teams and find team sum max score
            return []
        
        else:
            #Iterate over players and find max score
            return []
        
    else:
        return ['Guardians']