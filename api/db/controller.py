from sqlalchemy.orm import Session
from db.models import models

#Create Match Stats
def create_stats(db: Session, stats: str):
    #Check if server record exist already (Not much unique data to go by here so we filter on name and player host)
    server = db.query(models.Server).filter(models.Server.serverName == stats["serverName"]).filter(models.Server.hostPlayer == stats["hostPlayer"]).first()

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
