/*
   These are the developer files for AlgoMusic

   Last change: 03-Dec-97


   General stuff:

   When accessing the AlgoMusicMsgPort structure, make sure that the
structure is valid, meaning that you should do a Forbid() first, then
use FindPort() to get the pointer, copy all necessary stuff and then
Permit() (make sure you let the stuff Forbid()/Permit() be as short as
possible). This whole thing is necessary, because AlgoMusic might change
some of the values while you are snooping in it or even become removed.


  Example:

  const struct AlgoMusicMsgPort *p;   /* No changes allowed! */
  struct AlgoMusicMsgPort myport;
  BOOL portvalid=FALSE;

  Forbid();
  if(p=(struct AlgoMusicMsgPort *)FindPort(ALGOMUSICPORTNAME))
    {
    myport=*p;        /* Copy whole port structure */
    portvalid=TRUE;
    }
  Permit();

  if(portvalid)
    {
    ...      /* Use myport only here, not p! */
    }

*/


/* The name of AlgoMusic's global port */

#define ALGOMUSICPORTNAME (STRPTR)"AlgoMusic.port"


struct AlgoMusicVoice      /* Structure for each hardware voice */
  {
  BYTE   *Data;            /* Pointer to sample data */
  ULONG   Offset;          /* Offset sample is played from (in bytes) */
  USHORT  SampleNumber;    /* Number of sample (have a look below) */
  USHORT  Length;          /* Byte-length of sample (reallength-offset) */
  USHORT  Volume;          /* Volume of sample (0-64) */
  USHORT  Period;          /* Sample playback period */
  };

/*

    struct AlgoMusicMsgPort


    Contains vital information about the song currently being
    played. Information can be obtained by doing a FindPort()
    and reading data out of the AlgoMusicMsgPort structure
    returned.

    All entries in the structure are strictly READ-ONLY!


    Example:

    Have a look at Example.c and Example2.c!

*/

struct AlgoMusicMsgPort
  {
  struct MsgPort ExecMsgPort;   /* Standard Message Port */

  /* AlgoMusic specific stuff */

  char  SongName[256];          /* Name of the current song */
  ULONG RandomInit;             /* Song serie's randominit  */
  ULONG SongNr;                 /* Number of the song (1,...) */
  ULONG BPM;                    /* Current BPM */
  LONG  FineTune;               /* Current FineTune */
  ULONG TotalSteps;             /* 64 steps = 1 pattern */
  ULONG CurrentStep;            /* 0 .. TotalSteps-1 
                                   If song is finished, it will be TotalSteps */
  USHORT Progress;              /* Playing progress in percent:
                                   CurrentStep*100/TotalSteps   */
  USHORT State;                 /* See states below */

  struct AlgoMusicVoice Voice[4];
    
  /* Of course this may be longer in the future! */
  };

/* States */

#define STATE_UNKNOWN   0   /* Unknown state. Should not occur! */
#define STATE_RENDERING 1   /* Song is being created */
#define STATE_PLAYING   2   /* Song is being played */
#define STATE_STOPPED   3   /* Playing has been stopped via STOP */

/* Sample numbers */

#define MAXSPEECHSAMPLES 20

#define SAMPLES (17+MAXSPEECHSAMPLES)

#define MAJOR      0   /* Samplenumbers */
#define MINOR      1
#define MAJOR6     2
#define MINOR6     3
#define MAJOR4     4
#define MINOR4     5
#define BASS       6
#define MELODY     7
#define ACID       8

#define BASE       9  /* These are all finetune independent */
#define HIHAT     10
#define CLAP      11
#define BASECLAP  12
#define CLAPHIHAT 13
#define SNARE     14
#define BASEHIHAT 15

#define BREAKBEAT 16  /* Breakbeat & speech samples are BPM dependent */
  
#define SPEECH    17  /* 17-36 = Speech Samples -> 37 samples altogether */


/* AlgoMusic's used hardware voices

   Note that breakbeat samples can occur on any
   of these voices. Speech samples can occur
   anywhere but on the rhythm voice.            */


#define CHORDSVOICE 0     /* All kinds of chords */
#define BASSVOICE   1     /* Bass sample only */
#define RHYTHMVOICE 2     /* Base, clap, hihat, snare... */
#define MELODYVOICE 3     /* melody and acid samples */

/* struct AlgoMessage

   This message must be filled with the required values
   and sent to AlgoMusic's public message port. Note that
   you do not need to fill out all the structure elements,
   just the ones required for the command are enough.       */

struct AlgoMessage
  {
  struct Message Message;             /* Normal exec message */
  ULONG  Command;                     /* Command to execute */
  ULONG  Value1,Value2;               /* 2 command dependent values */
  char   String1[256],String2[256];   /* 2 command dependent strings */
  void  *Address;                     /* 1 command dependent address */
  };


/* The following commands are possible: */

#define COMMAND_REGISTER 0x1000

/* COMMAND_REGISTER

   Input: Value1, Value2

   Lets any task register to be part of AlgoMusic's signal system.
   You have to provide exactly 5 signals. The first 4 are contained
   in Value1 (Sig0<<24)+(Sig1<<16)+(Sig2<<8)+Sig3, the 5th signal is
   contained in the lowest byte of Value2. Note that you pass the
   signal numbers returned by 5 different AllocSignal() calls and
   not the shifted versions (1<<Sig).

   The first 4 signals are for notification that a note was played
   on the audiochannel (if you receive one of those signals, you can
   lookup the sample data in the AlgoMusicMsgPort structure), the
   5th is for notification that AlgoMusic has been quitted. If
   AlgoMusic has been quitted, neither COMMAND_UNREGISTER nor any
   other command may be issued!

   Any number of tasks may be registered to AlgoMusic's signalling
   mechanism. Each of the tasks will be signalled upon an event.

   You may not register the same task twice simultaneously!          */

#define COMMAND_UNREGISTER 0x1001

/* COMMAND_UNREGISTER

   Input: None

   Lets the sending task be removed from AlgoMusic's signalling
   mechanism (e.g. when an analyzer wants to quit). This call
   MUST be performed by a registered task when the task quits,
   or AlgoMusic will go on signalling to a non-existing task.

   It is safe to unregister a task that hasn't registered at all.    */
