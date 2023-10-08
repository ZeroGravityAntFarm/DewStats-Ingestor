from sqlalchemy.orm import Session
from db.models import models
from openskill.models import PlackettLuce
import logging
import requests

#Create Match Stats
def create_stats(db: Session, stats: str, header: str, ip: str):
    logger = logging.getLogger("uvicorn")

    #Validate our requesting server
    if not validate_server(ip, header):
        logger.info("Fake data detected from: " + str(ip))

        return

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

    model = PlackettLuce()
    teamWin = []
    teamLoss = []

    #Iterate over players in match and create records for them. Create a new record for each game event as player records are unique. For some reason player match data is stored here in the form of team id?
    for playerData in stats["players"]:
        #Get most recent player record
        try:
            player = db.query(models.Player).filter(models.Player.playerUID == playerData["uid"]).order_by(models.Player.id.desc()).first()
        
        except:
            #New player !!!!!1
            continue

        if winners:
            if playerData["uid"] in winners:
                player_exp = 1

                if player:
                    #Get players existing rating to use for our model
                    teamWin.append(model.create_rating([player.playerMu, player.playerSigma], name=playerData["uid"]))

                else:
                    #Player does not have a openskill rating yet
                    teamWin.append(model.rating(name=playerData["uid"]))

            
            else:
                player_exp = 0
                
                if player:
                    #Get players existing rating to use for our model
                    teamLoss.append(model.create_rating([player.playerMu, player.playerSigma], name=playerData["uid"]))

                else:
                    #Player does not have a openskill rating yet
                    teamLoss.append(model.rating(name=playerData["uid"]))
        
        else:
            #For whatever reason there are no calculated winners we will "freeze" the players rating and award no exp
            player_exp = 0
        

        #Create new player record
        if player:
            player = models.Player(playerName=playerData["name"],
                                    clientName=playerData["clientName"],
                                    serviceTag=playerData["serviceTag"],
                                    playerIp=playerData["ip"],
                                    team=playerData["team"],
                                    playerIndex=playerData["playerIndex"],
                                    playerUID=playerData["uid"],
                                    primaryColor=playerData["primaryColor"],
                                    playerExp=player_exp,
                                    playerMu = player.playerMu,
                                    playerSigma = player.playerSigma)
            
        else:
            player = models.Player(playerName=playerData["name"],
                                    clientName=playerData["clientName"],
                                    serviceTag=playerData["serviceTag"],
                                    playerIp=playerData["ip"],
                                    team=playerData["team"],
                                    playerIndex=playerData["playerIndex"],
                                    playerUID=playerData["uid"],
                                    primaryColor=playerData["primaryColor"],
                                    playerExp=player_exp,
                                    playerMu = 25.0,
                                    playerSigma = 8.333333333333334)

        
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

    #Update player openskill mu and sigma
    if teamWin and teamLoss:
        match = [teamWin, teamLoss]
        [teamWin, teamLoss] = model.rate(match)

        for playerSkill in teamWin:
            player = db.query(models.Player).filter(models.Player.playerUID == playerSkill.name).order_by(models.Player.id.desc()).first()

            player.playerMu = playerSkill.mu
            player.playerSigma = playerSkill.sigma

            db.add(player)
            db.commit()

        for playerSkill in teamLoss:
            player = db.query(models.Player).filter(models.Player.playerUID == playerSkill.name).order_by(models.Player.id.desc()).first()

            player.playerMu = playerSkill.mu
            player.playerSigma = playerSkill.sigma

            db.add(player)
            db.commit()


    return True


#Validate we have a real server reporting data and not a bot
def validate_server(hostIp, userAgent):
    logger = logging.getLogger("uvicorn")
    master_servers = ['http://ed.thebeerkeg.net/server/list']

    for server in master_servers:
        resp = requests.get(url=server)

    master_data = resp.json()


    if not any(hostIp in s for s in master_data["result"]["servers"]):
        logger.info("Server not in master")
        logger.info(master_data["result"]["servers"])
        return False
    
    elif userAgent != "ElDewrito/0.6.1.0":
        logger.info("Bad user agent: " + userAgent)
        return False
    
    else:
        for server in master_data["result"]["servers"]:
            if hostIp in server:
                try:
                    dew_request = requests.get('http://' + server)

                    if not dew_request:
                        logger.info("Invalid server api response")
                        return False

                except:
                    logger.info("Could not reach server api")
                    return False
        
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

        if teams:
            win_team = max(teams, key=teams.get)

            win_players = []
            for player in gameData["players"]:
                if player["team"] == win_team:
                    win_players.append(player["uid"])

        else:
            win_players = []

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
            teams = {}
            for player in gameData["players"]:
                if player["team"] not in teams:
                    teams[player["team"]] = player["playerGameStats"]["score"]

                else:
                    teams[player["team"]] = player["playerGameStats"]["score"] + teams[player["team"]]

            #This will return last team in loop if in case of tie
            if teams:
                win_team = max(teams, key=teams.get)

            win_players = []
            for player in gameData["players"]:
                if player["team"] == win_team:
                    win_players.append(player["uid"])

            return win_players
        
        else:
            score = 0
            winner = []
            for player in gameData["players"]:
                if player["playerGameStats"]["score"] >= score:
                    score = player["playerGameStats"]["score"]
                    winner.append(player["uid"])

            return winner
    
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
            if teams:
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
                    time = player["otherStats"]["timeControllingHill"]
                    winner.append(player["uid"])
    
    elif gameData["game"]["variantType"] == "oddball":
        if gameData["game"]["teamGame"]:
            teams = {}
            for player in gameData["players"]:
                if player["team"] not in teams:
                    teams[player["team"]] = player["playerGameStats"]["score"]

                else:
                    teams[player["team"]] = player["playerGameStats"]["score"] + teams[player["team"]]

            #This will return last team in loop if in case of tie
            if teams:
                win_team = max(teams, key=teams.get)

            win_players = []
            for player in gameData["players"]:
                if player["team"] == win_team:
                    win_players.append(player["uid"])

            return win_players
        
        else:
            score = 0
            winner = []
            for player in gameData["players"]:
                if player["playerGameStats"]["score"] >= score:
                    score = player["playerGameStats"]["score"]
                    winner.append(player["uid"])

            return winner
 
    elif gameData["game"]["variantType"] == "territories":
        if gameData["game"]["teamGame"]:
            teams = {}
            for player in gameData["players"]:
                if player["team"] not in teams:
                    teams[player["team"]] = player["playerGameStats"]["score"]

                else:
                    teams[player["team"]] = player["playerGameStats"]["score"] + teams[player["team"]]

            #This will return last team in loop if in case of tie
            if teams:
                win_team = max(teams, key=teams.get)

            win_players = []
            for player in gameData["players"]:
                if player["team"] == win_team:
                    win_players.append(player["uid"])

            return win_players
        
        else:
            score = 0
            winner = []
            for player in gameData["players"]:
                if player["playerGameStats"]["score"] >= score:
                    score = player["playerGameStats"]["score"]
                    winner.append(player["uid"])

            return winner
        
    else:
        return ['Guardians']