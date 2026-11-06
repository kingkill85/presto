"""Virtual folders; discovery never imports a native engine or moves ROMs."""
from retro_roms import discover, system_for

SYSTEM_NAMES = (('GB','Game Boy'),('GBC','Game Boy Color'),('GG','Game Gear'),
                ('NES','NES'),('SMS','Master System'),('SCUMM','Adventures'),('DOOM','Doom'))
SCUMM_GAMES = (
    (2, 'Monkey Island 2', '/sd/scumm/monkey2-de', ('monkey2.000','monkey2.001')),
    (1, 'Monkey Island', '/sd/scumm/monkey-vga-de',
     ('000.lfl','disk01.lec','disk02.lec','disk03.lec','disk04.lec')),
)


def installed_adventures():
    import os
    found=[]
    for game in SCUMM_GAMES:
        try:
            for name in game[3]: os.stat(game[2]+'/'+name)
            found.append(game)
        except OSError:
            pass
    return found


def catalog():
    folders={}
    for path in discover():
        try:
            system=system_for(path)[0]
        except (OSError, ValueError):
            continue
        title=path.rsplit('/',1)[-1].rsplit('.',1)[0].split(' (')[0]
        folders.setdefault(system,[]).append(dict(title=title,path=path,system=system,app='gb.py'))
    for profile,title,path,_ in installed_adventures():
        folders.setdefault('SCUMM',[]).append(dict(title=title,path=path,profile=profile,system='SCUMM',app='scumm.py'))
    import os
    for path in ('/sd/doom/doom1.wad', '/sd/doom/DOOM1.WAD'):
        try:
            if os.stat(path)[6] == 4196020:
                folders['DOOM'] = [dict(title='Doom Shareware', path=path, system='DOOM', app='doom.py')]
                break
        except OSError:
            pass
    return [(key,title,folders[key]) for key,title in SYSTEM_NAMES if key in folders]


def main():
    import machine
    from presto import Presto
    from gamepad import Gamepad
    from game_ui import GameUI
    from game_launch import mount_sd, take_request, launch
    presto=Presto(full_res=True,direct_to_fb=True,layers=1,ambient_light=False)
    ui=GameUI(presto,Gamepad())
    mount_sd()
    request=take_request()
    folders=catalog()
    selected=next((i for i,f in enumerate(folders) if f[0]==request.get('system')),0)
    while True:
        if not folders:
            ui.notice('SPIELE','Keine Spiele auf der SD-Karte gefunden')
            machine.reset()
        folder=ui.choose('SPIELE',[(title,'%d %s' % (len(games), 'Spiel' if len(games)==1 else 'Spiele'),True) for _,title,games in folders], selected=selected,back='Startseite')
        if folder is None: machine.reset()
        selected=folder
        system,title,games=folders[folder]
        while True:
            item=ui.choose(title.upper(),[(g['title'],'',True) for g in games],
                           'Touch oder Gamepad' if system=='SCUMM' else 'Zum Spielen: Gamepad anschliessen')
            if item is None: break
            launch(games[item]['app'],games[item])
