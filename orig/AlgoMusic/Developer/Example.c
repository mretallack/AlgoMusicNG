/* 

   Example.c    (C) 1997 by Thomas Schürger

   This is a small example how to use the AlgoMusicMsgPort structure
   in order to obtain playing information from AlgoMusic.

   Have a look at "AlgoMusic.h". You should get the idea.

   The way the port data is accessed here is not the way one should
   do it, "AlgoMusic.h" will give you information about that.

*/

#include <proto/exec.h>
#include <pragmas/exec_pragmas.h>
#include <stdio.h>

#include "algomusic.h"

main()
  {
    struct AlgoMusicMsgPort *amport;

    if(amport=(struct AlgoMusicMsgPort *)FindPort(ALGOMUSICPORTNAME))
      {
      printf("       Songname: %s\n",amport->SongName);
      printf("     Randominit: $%08lx\n",amport->RandomInit);
      printf("       Song Nr.: %lu\n",amport->SongNr);
      printf("            BPM: %lu\n",amport->BPM);
      printf("       Finetune: %ld\n",amport->FineTune);
      printf(" Total Patterns: %lu\n",amport->TotalSteps/64);
      printf("Current Pattern: %lu\n",amport->CurrentStep/64+1);
      printf("       Progress: %lu %%\n",amport->Progress);

      printf("          State: ");
      switch(amport->State)
        {
        case STATE_UNKNOWN:   printf("STATE_UNKNOWN\n");break;
        case STATE_RENDERING: printf("STATE_RENDERING\n");break;
        case STATE_PLAYING:   printf("STATE_PLAYING\n");break;
        case STATE_STOPPED:   printf("STATE_STOPPED\n");break;
        }
      }
    else
      printf("AlgoMusic is not running!\n");
  }
