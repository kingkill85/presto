// SPDX-License-Identifier: GPL-2.0-or-later
// Use Doom's native save archive with a bounded, in-memory FILE bridge.
#include "doomstat.h"
#include "g_game.h"
#include "p_saveg.h"
#include "r_main.h"
#include "r_draw.h"
#include "p_local.h"
#include "i_sound.h"
#include "i_system.h"
extern void R_ExecuteSetViewSize(void);
int doom_can_save(void){return gamestate==GS_LEVEL&&!demoplayback&&!netgame;}
void doom_archive(void){
    if(!doom_can_save())I_Error("Cannot save outside a level");
    save_stream=(FILE *)(intptr_t)-1;savegame_error=false;
    P_WriteSaveGameHeader("PRESTO DOOM");P_ArchivePlayers();P_ArchiveWorld();P_ArchiveThinkers();P_ArchiveSpecials();P_WriteSaveGameEOF();
    save_stream=NULL;
}
void doom_restore(void){
    save_stream=(FILE *)(intptr_t)-1;savegame_error=false;
    if(!P_ReadSaveGameHeader())I_Error("Invalid Doom save version");
    if(gameskill<0||gameskill>4||gameepisode!=1||gamemap<1||gamemap>9)I_Error("Invalid shareware save level");
    int saved_time=leveltime;
    G_InitNew(gameskill,gameepisode,gamemap);leveltime=saved_time;
    P_UnArchivePlayers();P_UnArchiveWorld();P_UnArchiveThinkers();P_UnArchiveSpecials();
    if(!P_ReadSaveGameEOF())I_Error("Invalid Doom save EOF");
    save_stream=NULL;R_ExecuteSetViewSize();R_FillBackScreen();
}
void doom_stats(int *out){out[0]=gametic;out[1]=gamemap;out[2]=players[consoleplayer].health;out[3]=players[consoleplayer].mo?players[consoleplayer].mo->x:0;out[4]=players[consoleplayer].mo?players[consoleplayer].mo->y:0;}

int doom_weapon_key(void){
    player_t *p=&players[consoleplayer];
    const int keys[]={49,50,51,52,53,54,55,49,51};
    for(int n=1;n<=NUMWEAPONS;n++){int w=(p->readyweapon+n)%NUMWEAPONS;if(p->weaponowned[w])return keys[w];}
    return 50;
}
