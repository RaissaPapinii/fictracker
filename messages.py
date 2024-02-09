CREATE_TABLES = '''
CREATE TABLE IF NOT EXISTS public."Fic"
(
    id integer NOT NULL,
    name text COLLATE pg_catalog."C" NOT NULL,
    authors text[] COLLATE pg_catalog."C" NOT NULL,
    link text COLLATE pg_catalog."C",
    published_chapters integer NOT NULL,
    total_chapters integer NOT NULL,
    completed boolean NOT NULL DEFAULT false,
    main_pairing text COLLATE pg_catalog."default",
    CONSTRAINT "Fic_pkey" PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS public."Tracker"
(
    id integer NOT NULL GENERATED ALWAYS AS IDENTITY ( INCREMENT 1 START 1 MINVALUE 1 MAXVALUE 2147483647 CACHE 1 ),
    guild_id bigint NOT NULL,
    fic_id integer NOT NULL,
    status character varying(20) COLLATE pg_catalog."default" NOT NULL,
    last_chapter text COLLATE pg_catalog."C",
    next_chapter text COLLATE pg_catalog."C",
    updated_at timestamp with time zone NOT NULL,
    last_ch_name integer,
    next_ch_name integer,
    CONSTRAINT "Tracker_pkey" PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS public."ReadFics"
(
    id integer NOT NULL GENERATED ALWAYS AS IDENTITY ( INCREMENT 1 START 1 MINVALUE 1 MAXVALUE 2147483647 CACHE 1 ),
    guild_id bigint NOT NULL,
    fic_id integer NOT NULL,
    value integer NOT NULL,
    CONSTRAINT "ReadFics_pkey" PRIMARY KEY (id)
)
'''
SHOW_QUERY = '''
    SELECT
        t.id,
        t.status,
        t.fic_id,
        f.link,
        f.name,
        f.authors,
        f.main_pairing,
        CASE
            WHEN f.completed=False THEN 'WIP'
            WHEN f.total_chapters=1 THEN 'One-Shot'
            ELSE 'Completed'
        END classification,
        f.published_chapters,
        f.total_chapters,
        t.last_ch_name,
        t.last_chapter,
        t.next_ch_name,
        t.next_chapter
    FROM "Tracker" AS t
        INNER JOIN "Fic" AS f ON t.fic_id=f.id
    WHERE t.guild_id=$1
    ORDER BY t.updated_at DESC
'''

LIST_QUERY = '''
    SELECT
        t.id,
        t.status,
        t.fic_id,
        f.link,
        f.name,
        f.authors,
        f.main_pairing,
        CASE
            WHEN f.completed=False THEN 'WIP'
            WHEN f.total_chapters=1 THEN 'One-Shot'
            ELSE 'Completed'
        END classification,
        f.published_chapters,
        f.total_chapters,
        t.last_ch_name,
        t.last_chapter,
        t.next_ch_name,
        t.next_chapter
    FROM "Tracker" AS t
        INNER JOIN "Fic" AS f ON t.fic_id=f.id
    WHERE t.guild_id=$1 AND t.status=$2
    ORDER BY t.updated_at DESC
'''

LIST_TRACKER = '''
    SELECT
        t.id,
        t.status,
        t.fic_id,
        f.link,
        f.name,
        f.authors,
        f.main_pairing,
        CASE
            WHEN f.completed=False THEN 'WIP'
            WHEN f.total_chapters=1 THEN 'One-Shot'
            ELSE 'Completed'
        END classification,
        f.published_chapters,
        f.total_chapters,
        t.last_ch_name,
        t.last_chapter,
        t.next_ch_name,
        t.next_chapter
    FROM "Tracker" AS t
        INNER JOIN "Fic" AS f ON t.fic_id=f.id
    WHERE t.id=$1
'''

INFO_CONTENT = '''This bot uses the concept of _lists_ to keep tracking of your fanfics, being the lists: **TBR**, **Reading**, **Read**, and **Rereading**.
So, in order to manage all your fics correctly, while using a command it is often asked what is the **status** of your reading. Also, you will need to provide an url of the fic every time you use a command, since the bot will use it to find the correct fic you're refering to.

__**Plataforms**__
For now, this bot can only track fics from AO3 but, in the future, other plataforms may be included. Please, use the `/suggest` command if you want to recommend one.

__**Data**__
The bot only uses your user id to respond to your command and, otherwise, the only data collected from the server is its unique identification.
In this way, the bot can manage trackers from different servers without messing up with the chapters tracking. The bot stores the all the fics and servers information into a database, for better performance.
**Important:** All the data stored is used only for the purpose of this bot, and none of it will be sold, exchanged, or divulgued by any means!
'''

HELP_DESCRIPTION1 = '''\n
__**Understanding how the bot works**__\n
To get more information about the premisses of this bot, please use the command `/info`.

__**Suggesting something**__\n
If you've had an idea for this bot, please use the `/suggest` command to share with us :)

__**Finding an error**__\n
If something is not working as it should, please use the `/error` command to explain the problem to us.
'''

HELP_DESCRIPTION2 = '''\n
__**Adding a Fanfic**__\n
Use the `/add` command, followed by the list in which you want to add the tracker, and the url of the last chapter you've read from the fic.
In case you're adding the fic to your TBR list, the URL can also be of the first one.
    * Example: `/add TBR https://archiveofourown.org/works/48936820/chapters/123457870` -> I added 'To Save an Empire' to my TBR list

__**Starting a Fanfic on your TBR list**__\n
Use the `/start` command followed by the url of the last chapter you've read. The fic will be moved automatically to your Reading list.
    * Example: `/start https://archiveofourown.org/works/48936820/chapters/125064640` -> Say I'd just started reading 'To Save an Empire', an the last chapter I've read is the 3rd one.
'''

HELP_DESCRIPTION3 = '''\n
__**Deleting**__\n
By using the `/delete` command you can erase all your trackers, all the trackers from one list or fic, or even a specific tracker.
For this you will need to choose one of the options:\n
    **1. All:** Delete all your trackers.
    _Possible Scenario:_ I don't want to use the bot anymore, so I'd like to clean all my data.\n
        * Usage: `/delete All`\n
    **2. Fic:** Delete all the trackers from the fanfic of the url, no matter the list.
    _Possible Scenario:_ I don't like to continue reading this fic, so I'd like to remove it from my trackings.\n
        * Example: `/delete Fic https://archiveofourown.org/works/48936820/chapters/123457870` -> Remove all the trackers from 'To Save An Empire'\n
    **3. Tracker:** Delete the tracker from the fanfic and list(status) indicated.
    _Possible Scenario:_ I accidentaly added a fic to the wrong list, so I'd like to remove it.\n
        * Example: `/delete Tracker Read https://archiveofourown.org/works/48936820/chapters/123457870` -> Remove 'To Save An Empire' from my Read list because it is a WIP. \n
    **4. \{list\}:** Delete all the fics from the list.
    _Possible Scenario:_ I want to restart my TBR list, so I'd like to clean it all.\n
        * Example: `/delete TBR` -> My TBR list don't have any fics anymore.\n
'''

HELP_DESCRIPTION4 = '''\n
__**Updating a tracker**__\n
Use the command `/update` to indicate the last chapter you've read from a fic in your Reading or Rereading list.
    * Example: `/update https://archiveofourown.org/works/48936820/chapters/126781108` -> Tell the bot the last chapter I've read from 'To Save an Empire' is the 6th one.

__**Restarting a Fanfic**__\n
Whenevevr you want to restart a fanfic on your reading or rereading list, use the `/restart` command to set the next chapter to the first one again.
_Possible Scenario:_ The fic was on hiatus and now that it was updated, you don't remember much about it, so you'd like to reread it again.    
    * Example: `/restart https://archiveofourown.org/works/48936820/chapters/126781108` -> The next chapter from 'To Save an Empire' for me to read is the first one.

__**Finishing a Fanfic**__\n
Use the command `/finish` whenever the fic is finished and you've read the last chapter.
The fic will be moved automatically to the Read list.
    * Example: `/finish https://archiveofourown.org/works/48489811/chapters/125801242` -> Means that I've read the last chapter of 'Reluctantly Yours'. 
'''

HELP_DESCRIPTION5 = '''\n
__**Rereading a Fanfic**__\n
Whenever you'd like to reread a fic, use the command `/reread` to move it to the Rereading list and reset the next chapter to read back to the first one.
Note that the url used in this command can be from any chapter of the fic.
    * Example: `/reread https://archiveofourown.org/works/48489811/chapters/125801242` -> Tell the bot I'd like to start rereading 'Reluctantly Yours' now.

__**Showing my Trackers**__\n
By using the `/show` command, you will receive a list of cards containing all the fics you track, accordingly to the options:\n
    **1. All:** Return all the fics you're tracking, no matter the list.
        * Usage: `/show All`\n
    **2. \{list\}:** Return all the fics on that list.
    _Possible Scenario:_ I'd like to see all the fics I'm reading now.\n
        * Example: `/show Reading `        
'''

