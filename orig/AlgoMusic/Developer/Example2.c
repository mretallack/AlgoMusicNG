/* 

   Example2.c   (C) 1997 by Thomas Schürger

   Last change: 30-Nov-97

   This is a small example how to use the AlgoMusicMsgPort structure
   in order to obtain song information from AlgoMusic.

   Note that this thing was hacked up in a few minutes, it is rather
   a bad example, but shows the way to access the data anyway.

   This example requires OS 3.0 or higher (V39), because of using
   SetRGB32(). Don't blame me for that, blame yourself for having
   an obsolete OS, if you don't have OS 3.0+.

   May be called with argument WINDOW to open a window instead of a
   screen.


   If you want a program that runs even though AlgoMusic is not, you
   must wait for AlgoMusic's port to (re)appear after having got
   a quit signal instead of exiting then.

   IF YOU'VE WRITTEN A BETTER EXAMPLE THAN THIS ONE, DON'T HESITATE
   TO SEND ME THE SOURCECODE FOR INCLUSION IN THE NEXT RELEASE!

   Also read the developer section in the guide!

*/


#include <intuition/intuition.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/intuition.h>
#include <proto/graphics.h>
#include <pragmas/exec_pragmas.h>
#include <pragmas/dos_pragmas.h>
#include <pragmas/intuition_pragmas.h>
#include <pragmas/graphics_pragmas.h>

#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#include "algomusic.h"

struct Window *win;
struct Screen *screen;
struct RastPort *rp;
struct ViewPort *vp;
struct MsgPort *mymsgport;

SHORT Last[SAMPLES],Current[SAMPLES];

BOOL algoquit;

ULONG width;
ULONG height;

int r=0,g=0,b=0;                        /* Values for red, green, blue */

ULONG barheight;
ULONG spaceheight;
ULONG barspaceheight;
BOOL window;

ULONG xoffset,yoffset;

USHORT sig[4];
USHORT sigquit;
ULONG  allsigs;

BOOL registered;

struct IntuiMessage *msg;
struct AlgoMusicMsgPort *amport;
struct AlgoMusicVoice *v;

struct IntuitionBase *IntuitionBase;
struct GfxBase *GfxBase;

int  MyMin(int,int);
void Add(int,int,int);
void Init(void);
void DeInit(void);
void Communicate(struct MsgPort *port,struct MsgPort *myport,ULONG command,ULONG value1,ULONG value2,char *string1,char *string2,void *address);

int MyMin(int a1,int b1)
  {
  if(a1>b1) return(b1);
  return(a1);
  }

void Add(int a1,int b1,int c1)   /* Adds values to the background color */
  {
  int vol=v->Volume;

  r=MyMin(255,r+((vol*a1)>>6));
  g=MyMin(255,g+((vol*b1)>>6));
  b=MyMin(255,b+((vol*c1)>>6));
  }

main(int argc,char **argv)
  {
  USHORT num;
  int i; 
  struct AlgoMusicMsgPort myport;
  BYTE oldpri;
  ULONG class;
  ULONG sigs;

  if(argc==2 && argv[1][0]=='?')
    {
    printf("Usage: %s [WINDOW]\n",argv[0]);
    exit(0);
    }
  else if(argc==2 && !stricmp(argv[1],"WINDOW"))
    window=TRUE;

  Init();

  oldpri=SetTaskPri(FindTask(NULL),10);

  SetSignal(0,(1<<sig[0])|(1<<sig[1])|(1<<sig[2])|(1<<sig[3]));
       /* Clear the voice signals that might have arrived already */

  while(!CheckSignal(SIGBREAKF_CTRL_C))
    {
    WaitTOF();        

    Forbid();
    myport=*amport;   /* Make a copy of the AlgoMusicMsgPort */
    Permit();         /* And ONLY use the copy */

    sigs=SetSignal(0,allsigs);  /* Get (all) signals, clear our 5 ones */

    if(sigs&(1<<sigquit))   /* AlgoMusic sent us a QUIT? */
      {
      algoquit=TRUE;
      SetTaskPri(FindTask(NULL),oldpri);
      DeInit();
      }
      
    for(i=0;i<4;i++)
      {
      if(sigs&(1<<sig[i]))   /* Has the specific signal been sent? */
        {
        v=&myport.Voice[i];  /* Get AlgoMusicVoice structure */
        num=v->SampleNumber; /* Get sample number */

        if(num==BASE || num==BASECLAP)
          Add(255,0,0);   

        if(num==CLAP || num==BASECLAP || num==CLAPHIHAT)
          Add(0,255,0);

        if(num<=5)          /* That's all kinds of chords */
          Add(0,0,255);
        else if(num==BASS)
          Add(200,0,230);            
        else if(num==ACID)
          Add(40,100,40);            
        else if(num==MELODY)
          Add(100,0,50);            
        else if(num==SNARE)
          Add(120,120,120);            

        Current[num]=(v->Volume*4*width)/256-1;
        if(Current[num]<0) Current[num]=0;
        }
      }

    if(!window) SetRGB32(vp,0,r<<24,g<<24,b<<24);

    r-=20;if(r<0) r=0;
    g-=20;if(g<0) g=0;    /* Decrease RGB values */
    b-=20;if(b<0) b=0; 

    for(i=0;i<SAMPLES;i++)        /* Loop for updating the bars */
      {
      if(Last[i]>Current[i])      /* Must we shorten the bar? */
        {
        SetAPen(rp,0);
        RectFill(rp,xoffset+Current[i]+1,yoffset+i*barspaceheight,xoffset+Last[i],yoffset+i*barspaceheight+barheight);
        }
      else if(Last[i]<Current[i]) /* Must we append to the bar? */
        {
        SetAPen(rp,1);
        RectFill(rp,xoffset+Last[i]+1,yoffset+i*barspaceheight,xoffset+Current[i],yoffset+i*barspaceheight+barheight);
        }
      Last[i]=Current[i];

      Current[i]-=3;               /* Decrease bar amplitude */
      if(Current[i]<0) Current[i]=0;
      }

    if(window)                /* Window message handling */
      {
      while(msg=(struct IntuiMessage *)GetMsg(win->UserPort))
        {
        class=msg->Class;
        ReplyMsg(msg);

        if(class==IDCMP_CLOSEWINDOW)
          {
          SetTaskPri(FindTask(NULL),oldpri);
          DeInit();
          }
        else if(class=IDCMP_NEWSIZE)
          {
          width=win->Width-win->BorderLeft-win->BorderRight;
          height=win->Height-win->BorderTop-win->BorderBottom-1;
          barspaceheight=height/SAMPLES;
          barheight=(barspaceheight*2)/3;
          spaceheight=barspaceheight-barheight;

          SetAPen(rp,0);
          RectFill(rp,xoffset,yoffset,xoffset+width-1,yoffset+height-1);
          SetAPen(rp,1);
          for(i=0;i<SAMPLES;i++)
            {
            Last[i]=0;
            Current[i]=0;
            RectFill(rp,xoffset+0,yoffset+i*barspaceheight,xoffset+0,yoffset+i*barspaceheight+barheight);
            }
          }
        }
      }
    }

  SetTaskPri(FindTask(NULL),oldpri);

  DeInit();
  }

void Init()
  {
  int i;

  if(!(IntuitionBase=(struct IntuitionBase *)OpenLibrary("intuition.library",39)))
    {
    printf("Couldn't open intuition.library V39!\n");
    DeInit();
    }

  if(!(GfxBase=(struct GfxBase *)OpenLibrary("graphics.library",39)))
    {
    printf("Couldn't open intuition.library V39!\n");
    DeInit();
    }

  if(!(amport=(struct AlgoMusicMsgPort *)FindPort(ALGOMUSICPORTNAME)))
    {
    printf("AlgoMusic is not running!\n");
    DeInit();
    }

  if(!(mymsgport=CreatePort(0,0)))
    {
    printf("Couldn't allocate message port!\n");
    DeInit();
    }

  sig[0] =AllocSignal(-1);
  sig[1] =AllocSignal(-1);
  sig[2] =AllocSignal(-1);
  sig[3] =AllocSignal(-1);
  sigquit=AllocSignal(-1);

  if(!sig[0] || !sig[1] || !sig[2] || !sig[3] || !sigquit)
    {
    printf("Couldn't allocate signals!\n");
    DeInit();
    }

  Communicate(amport,mymsgport,COMMAND_REGISTER,(sig[0]<<24)|(sig[1]<<16)|(sig[2]<<8)|sig[3],sigquit,NULL,NULL,NULL);
  registered=TRUE;

  allsigs=(1<<sig[0])|(1<<sig[1])|(1<<sig[2])|(1<<sig[3])|(1<<sigquit);

  if(!window && (screen=OpenScreenTags(NULL,SA_AutoScroll,TRUE,SA_Quiet,TRUE,SA_Overscan,OSCAN_STANDARD,TAG_DONE)))
    {
    rp=&screen->RastPort;
    vp=&screen->ViewPort;

    SetRGB32(vp,0,0,0,0);
    SetRGB32(vp,1,255<<24,255<<24,255<<24);

    width=screen->Width;
    height=screen->Height;
    }  
  else if(win=OpenWindowTags(NULL,WA_Title,"Example 2",WA_ScreenTitle,"Example 2  (C) 1997 by Thomas Schürger (schuerge@studcs.uni-sb.de)",WA_MinHeight,60,WA_MinWidth,60,WA_SizeGadget,TRUE,WA_DragBar,TRUE,WA_DepthGadget,TRUE,WA_CloseGadget,TRUE,WA_IDCMP,IDCMP_CLOSEWINDOW|IDCMP_NEWSIZE,TAG_DONE))
    {
    rp=win->RPort;
    
    width=win->Width-win->BorderLeft-win->BorderRight;
    height=win->Height-win->BorderTop-win->BorderBottom-1;
    }
  else
    {
    printf("Could not open screen!\n");
    DeInit();
    }

  barspaceheight=height/SAMPLES;
  barheight=(barspaceheight*2)/3;
  spaceheight=barspaceheight-barheight;

  if(win)
    {
    xoffset=win->BorderLeft;
    yoffset=win->BorderTop+1;
    }

  for(i=0;i<SAMPLES;i++)
    {
    Last[i]=0;
    Current[i]=0;

    SetAPen(rp,1);
    RectFill(rp,xoffset+0,yoffset+i*barspaceheight,xoffset+0,yoffset+i*barspaceheight+barheight);
    }
  }

void DeInit()
  {
  if(registered && !algoquit)
    Communicate(amport,mymsgport,COMMAND_UNREGISTER,0,0,NULL,NULL,NULL);

  if(screen)
    CloseScreen(screen);

  if(win)
    CloseWindow(win);

  if(mymsgport)
    DeletePort(mymsgport);

  if(sig[0])  FreeSignal(sig[0]);
  if(sig[1])  FreeSignal(sig[1]);
  if(sig[2])  FreeSignal(sig[2]);
  if(sig[3])  FreeSignal(sig[3]);
  if(sigquit) FreeSignal(sigquit);

  if(IntuitionBase) CloseLibrary((struct Library *)IntuitionBase);
  if(GfxBase) CloseLibrary((struct Library *)GfxBase);

  exit(0);
  }

void Communicate(struct MsgPort *port,struct MsgPort *myport,ULONG command,ULONG value1,ULONG value2,char *string1,char *string2,void *address)
  {
  static struct AlgoMessage msg;

  msg.Message.mn_Node.ln_Succ=NULL;
  msg.Message.mn_Node.ln_Pred=NULL;
  msg.Message.mn_Node.ln_Pri=0;
  msg.Message.mn_Node.ln_Name=NULL;
  msg.Message.mn_ReplyPort=myport;
  msg.Message.mn_Length=sizeof(struct AlgoMessage);

  msg.Command=command;
  msg.Value1=value1;
  msg.Value2=value2;

  if(string1)
    strcpy((char *)&msg.String1[0],string1);
  else
    msg.String1[0]=0;

  if(string2)
    strcpy((char *)&msg.String2[0],string2);
  else
    msg.String2[0]=0;

  msg.Address=address;

  PutMsg(port,(struct Message *)&msg);
  }
