import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
import requests
from bs4 import BeautifulSoup
from messages import (SHOW_QUERY, LIST_QUERY, INFO_CONTENT, HELP_DESCRIPTION1, HELP_DESCRIPTION2, HELP_DESCRIPTION3, HELP_DESCRIPTION4, HELP_DESCRIPTION5)
import os
import re
import asyncio
import traceback


HEADERS = {'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'}
groups = ['tbr', 'reading', 'read', 'rereading']

class tracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_help_embed(self, content, cur_page):
        embed = discord.Embed(title="Commands", colour=discord.Colour(0x4a90e2), description=content)
        embed.set_author(name=f"Page {cur_page}/5")
        return embed
  
    @app_commands.command(description='Understand the commands')
    async def help(self, ctx:discord.Interaction):
        pages = 5
        cur_page = 1
        contents = [HELP_DESCRIPTION1, HELP_DESCRIPTION2, HELP_DESCRIPTION3, HELP_DESCRIPTION4, HELP_DESCRIPTION5]
        
        embed = await self.get_help_embed(contents[cur_page-1], cur_page)
        await ctx.response.send_message(embed=embed)
        message = await ctx.original_response()
        # getting the message object for editing and reacting

        await message.add_reaction("◀️")
        await message.add_reaction("▶️")
        
        def check(reaction, user):
            return user == ctx.user and str(reaction.emoji) in ["◀️", "▶️"]

        while True:

            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=1200, check=check)

                if str(reaction.emoji) == "▶️" and cur_page != pages:
                    cur_page += 1
                    embed = await self.get_help_embed(contents[cur_page-1], cur_page)
                    await message.edit(embed=embed)
                    await message.remove_reaction(reaction, user)

                elif str(reaction.emoji) == "◀️" and cur_page > 1:
                    cur_page -= 1
                    embed = await self.get_help_embed(contents[cur_page-1], cur_page)
                    await message.edit(embed=embed)
                    await message.remove_reaction(reaction, user)

                else:
                    await message.remove_reaction(reaction, user)
            except asyncio.TimeoutError:
                await message.remove_reaction(reaction, user)
                break

    @app_commands.command(description='Understand the bot')
    async def info(self, ctx:discord.Interaction):
        await ctx.response.send_message(INFO_CONTENT)

    @app_commands.command(description="Suggest something that you'd like to see here.")
    async def suggest(self, ctx:discord.Interaction, message:str):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(int(os.getenv('SUGGESTION_CHANNEL')))
        if message == None:
            await ctx.response.send_message('Please write your suggestion after the /suggest!')
        else:
            await channel.send("SUGGESTION\n"+message)
            await ctx.response.send_message('Suggestion sent! Thank you for your contribution :)')

    async def send_error(self, message):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(int(os.getenv('ERROR_CHANNEL')))
        await channel.send(message)

    @app_commands.command(description="Explain an error you've found.")
    async def error(self, ctx:discord.Interaction, message:str):
        if message == None:
            await ctx.response.send_message('Please describe the error after the /error!')
        else:
            await self.send_error("BUG\n"+message)
            await ctx.response.send_message('Error sent! Thank you for your contribution :)')

    async def get_update_fic_metadata(self, soup):
        pb_chapters, total_chapters = soup.find('dd', attrs={'class' : 'chapters'}).string.split('/')
        pb_chapters = int(pb_chapters)
        total_chapters = (int(total_chapters) if '?' not in total_chapters else -1)
        completed = (pb_chapters==total_chapters)
        return pb_chapters, total_chapters, completed

    async def get_fic_metadata(self, soup):
        title = soup.find(attrs={'class' : 'title heading'}).string.strip()
        pb_chapters, total_chapters, completed = await self.get_update_fic_metadata(soup)
        authors=[]
        for author in soup.css.select('h3[class="byline heading"] > a[rel="author"]'):
            authors.append(author.text.strip())
        return title, authors, pb_chapters, total_chapters, completed
    
    async def get_next_chapter(self, soup):
        next_chapter = soup.find('a',string="Next Chapter →", href=True)
        if next_chapter:
            next_chapter = next_chapter['href']
            if next_chapter.startswith("/works/"):
                next_chapter = "https://archiveofourown.org/"+next_chapter
            return next_chapter
        else:
            return '-' 

    async def get_full_url(self, url):
        soup = await self.get_soup(url)
        full_url = soup.find('h3', attrs={'class':'title'}).find('a', href=True)
        full_url = full_url['href']
        if full_url.startswith("/works/"):
            full_url = "https://archiveofourown.org/"+full_url
        return full_url

    async def get_fic_id(self, url:str):
        if url.startswith('https://archiveofourown.org/chapters/'):
            url = await self.get_full_url(url)
        return int(re.findall(r"(?<=/works/)[\d]+", url)[0])

    async def update_fic_db(self, fic_id, pb_chapters, total_chapters, completed):
        await self.bot.db.execute('UPDATE "Fic" SET published_chapters=$1, total_chapters=$2, completed=$3 WHERE id=$4', pb_chapters, total_chapters, completed, fic_id)

    async def add_fic(self, fic_id, url, title, authors, pb_chapters, total_chapters, completed, main_pairing):
        await self.bot.db.execute('INSERT INTO "Fic" (id, name, authors, link, published_chapters, total_chapters, completed, main_pairing) VALUES ($1, $2, $3, $4, $5, $6, $7, $8);', fic_id, title, authors, url, pb_chapters, total_chapters, completed, main_pairing)
    
    async def add_tracker(self, guild_id, fic_id, status, url, next_chapter, tmp, ctx):
        status = status.lower()
        if status == 'tbr':
            last_ch = '-'
            next_ch = next_chapter
        elif 'reading' in status:
            last_ch = url
            next_ch = next_chapter
        else:
            last_ch = url
            next_ch = '-'

        last_name = await self.get_chapter(last_ch, ctx)
        next_name = await self.get_chapter(next_ch, ctx)
        await self.bot.db.execute('INSERT INTO "Tracker" (guild_id, fic_id, status, last_chapter, next_chapter, updated_at, last_ch_name, next_ch_name) VALUES ($1, $2, $3, $4, $5, $6, $7, $8);',guild_id, fic_id, status, last_ch, next_ch, tmp, last_name, next_name)

    async def get_soup(self, url, ctx=None):
        #Get the html from the url to scrape the fic metadata
        try:
            response = requests.get(url, headers=HEADERS)
            soup = BeautifulSoup(response.text, "html.parser")
            return soup
        except Exception as e:
            if ctx:
                await ctx.response.send_message(f"An error occurred")
            
            await self.send_error(f"BUG\nGetting Soup\n getting soup:\n {type(e)(traceback.format_exc())}")

            return None
    
    async def get_first_chapter(self, url, soup):
        ch_index = soup.find('select', attrs={'name':'selected_id'})
        first_ch = ch_index.find('option')['value']
        root = re.findall(r"[\w:./]+/works/\d+", url)[0]
        return root+'/chapters/'+first_ch
            
    async def get_main_pairing(self, soup):
        pairing = soup.find('dd', attrs={'class' : 'relationship tags'}).find('ul', attrs={'class':'commas'})
        pairing = [pairing for pairing in pairing.find_all('li')]
        main_pairing = [mp.text for mp in pairing[0].find('a')][0]
        return main_pairing
    
    async def manage_fic(self, fic_id, url, soup):
        title, authors, pb_chapters, total_chapters, completed = await self.get_fic_metadata(soup)
        check_fic = await self.bot.db.fetch('SELECT * FROM "Fic" WHERE id = $1', fic_id)
        if len(check_fic)<1:
            if total_chapters==1:
                root_url = url
            else:
                root_url = await self.get_first_chapter(url, soup)
            main_pairing = await self.get_main_pairing(soup)
            await self.add_fic(fic_id, root_url, title, authors, pb_chapters, total_chapters, completed, main_pairing)
        else:
            await self.update_fic_db(fic_id, pb_chapters, total_chapters, completed)
        return title, total_chapters

    async def update_fic(self, ctx, fic_id, url):
        soup = await self.get_soup(url, ctx)
        if soup:
            try:
                pb_chapters, total_chapters, completed = await self.get_update_fic_metadata(soup)
                await self.update_fic_db(fic_id, pb_chapters, total_chapters, completed)
            except:
                try:
                    first_ch = await self.get_first_chapter(url, soup)
                    await self.db.execute('UPDATE FROM "Fic" SET link=$1 WHERE id=$2', first_ch, fic_id)

                    #Retrying to update
                    new_soup = await self.get_soup(first_ch, ctx)
                    pb_chapters, total_chapters, completed = await self.get_update_fic_metadata(new_soup)
                    await self.update_fic_db(fic_id, pb_chapters, total_chapters, completed)
                except:
                    await self.send_error(f"BUG\nUPDATE FIC\n Fanfic id={fic_id} couldn't be updated!")
                  
    @app_commands.command(description='Add a fic to one of your lists.')
    @app_commands.choices(status=[
        Choice(name='TBR', value='tbr'),
        Choice(name='Reading', value='reading'),
        Choice(name='Read', value='read'),
        Choice(name='Rereading', value='rereading'),
    ])
    async def add(self, ctx:discord.Interaction, status:str, url:str):
        if '/series/' in url:
            await ctx.response.send_message(f"I still don't support tracking of series, please use the url of a single work instead.")
            return
        guild = ctx.guild.id
        fic_id = await self.get_fic_id(url)
        await ctx.response.defer()
        check = await self.bot.db.fetch('SELECT * FROM "Tracker" WHERE guild_id=$1 AND fic_id=$2 AND status=$3', guild, fic_id, status)
        if len(check)>0:
            await ctx.followup.send(f"You're already tracking this fic!")
            return
        soup = await self.get_soup(url, ctx)
        if soup:
            try:
                title, total_ch = await self.manage_fic(fic_id, url, soup)
                if status=='tbr':
                    if total_ch==1:
                        next_ch = url
                    else:
                        next_ch = await self.get_first_chapter(url, soup)
                else:
                    next_ch = await self.get_next_chapter(soup)
                await self.add_tracker(guild, fic_id, status, url, next_ch, ctx.created_at, ctx)
            except Exception as e:
                await self.send_error(f'BUG\nManaging and Adding Fic\n{type(e)(traceback.format_exc())}')
            else:
                await ctx.followup.send(f"You're tracking {title} now!")
                if status=='read':
                    await self.bot.db.execute('INSERT INTO "ReadFics"(guild_id, fic_id, value) VALUES ($1, $2, 1);', guild, fic_id)
            
    @app_commands.command(description="Set a TBR fic to Reading. (The URL sent must be of the last chapter you'd read)")
    async def start(self, ctx:discord.Interaction, url:str):
        guild = ctx.guild.id
        fic_id = await self.get_fic_id(url)
        await ctx.response.defer()
        soup = await self.get_soup(url, ctx)
        if soup:
            title = await self.manage_fic(fic_id, url, soup)
            next_ch = await self.get_next_chapter(soup)
            tracker = await self.bot.db.fetch('SELECT * FROM "Tracker" WHERE guild_id=$1 AND fic_id=$2 AND status=$3', guild, fic_id, 'tbr')
            if len(tracker)<1:
                await self.add_tracker(guild, fic_id, "reading", url, next_ch, ctx.created_at, ctx)
            else:
                last_ch_name = await self.get_chapter(url, ctx)
                next_ch_name = await self.get_chapter(next_ch, ctx)
                await self.bot.db.execute('UPDATE "Tracker" SET status=$1, last_chapter=$2, next_chapter=$3, updated_at=$4, last_ch_name=$5, next_ch_name=$6 WHERE id=$7', 'reading', url, next_ch, ctx.created_at, last_ch_name, next_ch_name, tracker[0]['id'])
            await ctx.followup.send(f'You just started reading {title}!')

    async def purge_fics(self):
        fics_to_purge = await self.bot.db.fetch('SELECT f.id FROM "Fic" AS f LEFT JOIN "Tracker" t ON f.id=t.fic_id WHERE t.id IS NULL')
        fics_to_purge = tuple([val['id'] for val in fics_to_purge])
        await self.bot.db.execute('DELETE FROM "Fic" WHERE id=any($1)', fics_to_purge)

    @app_commands.command(description="Delete all your tracks, all tracks from a fic, a specific tracker, or all fics into a specific list.")
    @app_commands.choices(kind=[
        Choice(name='All', value='all'),
        Choice(name='Fic', value='fic'),
        Choice(name='Tracker', value='tracker'),
        Choice(name='TBR', value='tbr'),
        Choice(name='Reading', value='reading'),
        Choice(name='Read', value='read'),
        Choice(name='Rereading', value='rereading'),
    ])
    @app_commands.choices(status=[
        Choice(name='TBR', value='tbr'),
        Choice(name='Reading', value='reading'),
        Choice(name='Read', value='read'),
        Choice(name='Rereading', value='rereading'),
    ])
    async def delete(self, ctx:discord.Interaction, kind:str, url:str=None, status:str=None):
        guild = ctx.guild.id
        await ctx.response.defer()
        if kind=='all':
            await self.bot.db.execute('DELETE FROM "Tracker" WHERE guild_id=$1', guild)
            await ctx.followup.send('All your trackers were deleted!')
        elif kind=='fic':
            fic_id = await self.get_fic_id(url)
            await self.bot.db.execute('DELETE FROM "Tracker" WHERE guild_id=$1 AND fic_id=$2', guild, fic_id)
            await ctx.followup.send('All the trackers from the fic were deleted!')
        elif kind=='tracker':
            fic_id = await self.get_fic_id(url)
            await self.bot.db.execute('DELETE FROM "Tracker" WHERE guild_id=$1 AND fic_id=$2 AND status=$3', guild, fic_id, status)
            await ctx.followup.send('Your track was deleted!')
        elif kind in groups:
            await self.bot.db.execute('DELETE FROM "Tracker" WHERE guild_id=$1 AND status=$2', guild, kind)
            await ctx.followup.send(f'All the {kind} trackers were deleted!')
        await self.purge_fics()

    @app_commands.command(description='Update the last chapter read from one of the fics on your Reading list.')
    async def update(self, ctx:discord.Interaction, url:str):
        await ctx.response.defer()
        soup = await self.get_soup(url, ctx)
        if soup:
            #update fic metadata
            fic_id = await self.get_fic_id(url)
            title = await self.bot.db.fetch('SELECT name FROM "Fic" WHERE id=$1', fic_id)
            if len(title)<1:
                await ctx.followup.send(f'Please add your fic first by using the /add command!\nExample: /add reading {url}')
                return
            else:
                await self.update_fic(ctx, fic_id, url)
                #Check tracker
                guild = ctx.guild.id
                tracker = await self.bot.db.fetch('SELECT id FROM "Tracker" WHERE guild_id=$1 AND fic_id=$2 AND (status LIKE $3)', guild, fic_id, f"%{'reading'}%")
                if len(tracker)<1:
                    await ctx.followup.send(f'It does not seem you started this fic yet. If the fic is in your TBR list now, you can update it by using the url on the /start command.\nExample: /start {url}')
                else:
                    next_ch = await self.get_next_chapter(soup)
                    last_ch_name = await self.get_chapter(url, ctx)
                    next_ch_name = await self.get_chapter(next_ch, ctx)
                    await self.bot.db.execute('UPDATE "Tracker" SET last_chapter=$1, next_chapter=$2, updated_at=$3, last_ch_name=$4, next_ch_name=$5 WHERE id=$6', url, next_ch, ctx.created_at, last_ch_name, next_ch_name, tracker[0]["id"])
                    await ctx.followup.send(f'Your tracking of {title[0]["name"]} was updated!')

    async def change_status(self, ctx:discord.Interaction, url:str, status:str):
        guild = ctx.guild.id
        fic_id = await self.get_fic_id(url)
        title = await self.bot.db.fetch('SELECT name FROM "Fic" WHERE id=$1', fic_id)
        if len(title)<1:
            await ctx.response.send_message('Please add your fic first by using the /add command!')
            await ctx.response.send_message(f'Example: /add reading {url}')
            return
        else: 
            tracker = await self.bot.db.fetch('SELECT MAX(id) FROM (SELECT id FROM "Tracker" WHERE guild_id=$1 AND fic_id=$2)', guild, fic_id)
            if len(tracker)<1:
                await ctx.response.send_message("It seems you still don't have a track for this fic. Please add one by using the /add command.")
                await ctx.response.send_message(f'Example: /add reading {url}')
            else:
                await self.bot.db.execute('UPDATE "Tracker" SET status=$1, updated_at=$2 WHERE id=$3', status, ctx.created_at, tracker[0]["max"])
                await ctx.response.send_message(f'The status of {title[0]["name"]} now is {status}!')

    async def update_read_table(self, guild, fic):
        tracking = await self.bot.db.fetch('SELECT id, value FROM "ReadFics" WHERE guild_id=$1 AND fic_id=$2', guild, fic)
        if len(tracking)>0:
            await self.bot.db.execute('UPDATE "ReadFics" SET value=$1 WHERE id=$2', tracking[0]['value']+1, tracking[0]['id'])
        else:
            await self.bot.db.execute('INSERT INTO "ReadFics"(guild_id, fic_id, value) VALUES ($1, $2, 1);', guild, fic)

    @app_commands.command(description='Move one of your Reading fics to the Read list.')
    async def finish(self, ctx:discord.Interaction, url:str):
        guild = ctx.guild.id
        fic_id = await self.get_fic_id(url)
        await ctx.response.defer()
        title = await self.bot.db.fetch('SELECT name FROM "Fic" WHERE id=$1', fic_id)
        if len(title)<1:
            await ctx.followup.send(f'Please add your fic first by using the /add command!\nExample: /add read {url}')
            return
        else:
            await self.update_fic(ctx, fic_id, url) 
            tracker = await self.bot.db.fetch('SELECT * FROM "Tracker" WHERE guild_id=$1 AND fic_id=$2 AND status!=$3', guild, fic_id, 'read')
            if len(tracker)<1:
                await ctx.followup.send(f"It seems you still don't have an open track for this fic. Please add one by using the /add command. Remember you can add a non-tracked fic directly in your read list by using: /add read {url}.")
            else:
                await self.update_read_table(guild, fic_id)
                await self.bot.db.execute('UPDATE "Tracker" SET status=$1, last_chapter=$2, next_chapter=$3, updated_at=$4 WHERE id=$5', 'read', url, '-', ctx.created_at, tracker[0]['id'])
                await ctx.followup.send(f'You just finished {title[0]["name"]}! Please remember to use the /reread command whenever you want to reread it.\nExample: /reread {url}')

    @app_commands.command(description='Restart the chapters tracking from a fic on the Reading list.')
    async def restart(self, ctx:discord.Interaction, url:str):
        guild = ctx.guild.id
        fic_id = await self.get_fic_id(url)
        await ctx.response.defer()
        await self.update_fic(ctx, fic_id, url)
        title = await self.bot.db.fetch('SELECT name FROM "Fic" WHERE id=$1', fic_id)
        if len(title)<1:
            await ctx.followup.send(f'Please add your fic first by using the /add command!\nExample: /add reading {url}')
            return
        else:
            await self.update_fic(ctx, fic_id, url)
            tracker = await self.bot.db.fetch('SELECT * FROM "Tracker" WHERE guild_id=$1 AND fic_id=$2 AND (status LIKE $3)', guild, fic_id, f"%{'reading'}")
            if len(tracker)<1:
                await ctx.followup.send(f"It seems you still don't have an open track for this fic. Please add one by using the /add command.\nExample: /add reading {url}")
            else:
                soup = await self.get_soup(url, ctx)
                root_url = await self.get_first_chapter(url, soup)
                await self.bot.db.execute('UPDATE "Tracker" SET last_chapter=$1, next_chapter=$2, updated_at=$3, last_ch_name=0, next_ch_name=1 WHERE id=$4', '-', root_url, ctx.created_at, tracker[0]['id'])
                await ctx.followup.send(f'You just restarted {title[0]["name"]}!')

    @app_commands.command(description="Move a Read fic into the Rereading list. This means the next chapter will be the first one again.")
    async def reread(self, ctx:discord.Interaction, url:str):
        guild = ctx.guild.id
        fic_id = await self.get_fic_id(url)
        await ctx.response.defer()
        title = await self.bot.db.fetch('SELECT name FROM "Fic" WHERE id=$1', fic_id)
        if len(title)<1:
            await ctx.followup.send(f'Please add your fic first by using the /add command!\nExample: /add rereading {url}')
            return
        else:
            tracker = await self.bot.db.fetch('SELECT * FROM "Tracker" WHERE guild_id=$1 AND fic_id=$2 AND status=$3', guild, fic_id, 'read')
            if len(tracker)<1:
                await ctx.followup.send(f"It seems you still don't have a closed track for this fic. Please add one by using the /finish command.\nExample: /finish {url}")
            else:
                soup = await self.get_soup(url)
                root_url = await self.get_first_chapter(url, soup)
                await self.bot.db.execute('UPDATE "Tracker" SET last_chapter=$1, next_chapter=$2, status=$3, updated_at=$4 WHERE id=$5', '-', root_url, 'rereading', ctx.created_at, tracker[0]['id'])
                await ctx.followup.send(f'You just started rereading {title[0]["name"]}!')

    async def get_chapter(self, url, ctx):
        if url=='-':
            return 0
        if '/chapters/' not in url:
            return 1
        soup = await self.get_soup(url, ctx)
        chapter = soup.find('h3', attrs={'class':'title'}).find('a').text
        return int(chapter[8:])

    async def get_embed_title(self, fic_title, authors):
        authors_str = ', '.join(authors)
        title = fic_title+', by '+authors_str
        return title
    
    async def get_embed_chapter(self, number, url):
        if number==0:
            return '-'
        return f'[Chapter {number}]({url})'
    
    async def get_embed(self, description, title, publishing_info, last_ch_info, next_ch_info, status):
        embed = discord.Embed(colour=discord.Colour(0x4a90e2), description=description)
        embed.set_author(name=title, icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
        embed.add_field(name="🏁 Publishing", value=publishing_info, inline=True)
        embed.add_field(name="⬅️ Last Chapter", value=last_ch_info, inline=True)
        embed.add_field(name="➡️ Next Chapter", value=next_ch_info, inline=True)
        return embed

    async def get_fics(self, status, guild_id):
        if status=='all':
            return await self.bot.db.fetch(SHOW_QUERY, guild_id)
        return await self.bot.db.fetch(LIST_QUERY, guild_id, status)

    async def get_embeds_list(self, ctx, fics):
        embeds = []
        for fic in fics:
            try:
                await self.update_fic(ctx, fic['fic_id'], fic['link'])
                title = await self.get_embed_title(fic['name'], fic['authors'])
                total_chapters = str(fic['total_chapters']) if fic['total_chapters']>0 else '?'
                publishing_info = fic['classification']+'  |  '+str(fic['published_chapters'])+'/'+total_chapters
                last_ch_info = await self.get_embed_chapter(fic['last_ch_name'], fic['last_chapter'])
                next_ch_info = await self.get_embed_chapter(fic['next_ch_name'], fic['next_chapter'])
                status_embed = ('TBR' if fic['status']=='tbr' else fic['status'].capitalize())
                description = f'{status_embed}   |   {fic["main_pairing"]}'
                embed = await self.get_embed(description, title, publishing_info, last_ch_info, next_ch_info, status_embed)
                embeds.append(embed)
            except Exception as e:
                err = str(type(e)(traceback.format_exc() + f'Happened in Fic: {fic["name"]}\nObject: {fic}'))
                await self.send_error("BUG\nCommand Show - Getting Embeds\n"+err)
                pass
        return embeds

    def chunker(self, seq, size):
        return [seq[pos:pos + size] for pos in range(0, len(seq), size)]

    @app_commands.command(description="Show a list of all the fics you're tracking, or all the ones into a specific list.")
    @app_commands.choices(status=[
        Choice(name='All', value='all'),
        Choice(name='TBR', value='tbr'),
        Choice(name='Reading', value='reading'),
        Choice(name='Read', value='read'),
        Choice(name='Rereading', value='rereading'),
    ])
    async def show(self, ctx:discord.Interaction, status:str):
        guild = ctx.guild.id
        fics = await self.get_fics(status, guild)
        fics_total = len(fics)
        if fics_total>0:
            await ctx.response.defer()

            try:
                cur_page=1
                items = 3
                pages = -(-len(fics) // items)
                embeds_paged = await self.get_embeds_list(ctx, fics)
                embeds_paged = self.chunker(embeds_paged, items)
            except Exception as e:
                await ctx.followup.send('An error occurred while requesting your fanfics. The problem was already sent to our team.')
                await self.send_error("BUG\nCommand Show - Getting Embeds\n"+traceback.format_exc())
            else:
                await ctx.followup.send(content=f'{fics_total} fics found! Page {cur_page}/{pages}', embeds=embeds_paged[cur_page-1])
                message = await ctx.original_response()
                await message.add_reaction("◀️")
                await message.add_reaction("▶️")
                
                def check(reaction, user):
                    return user == ctx.user and str(reaction.emoji) in ["◀️", "▶️"]

                while True:
                    reaction, user = await self.bot.wait_for("reaction_add", timeout=600, check=check)
                    try:
                        if str(reaction.emoji) == "▶️" and cur_page != pages:
                            cur_page += 1
                            await message.edit(content=f'{fics_total} fics found! Page {cur_page}/{pages}', embeds=embeds_paged[cur_page-1])
                            await message.remove_reaction(reaction, user)
                        elif str(reaction.emoji) == "◀️" and cur_page > 1:
                            cur_page -= 1
                            await message.edit(content=f'Page {cur_page}/{pages}', embeds=embeds_paged[cur_page-1])
                            await message.remove_reaction(reaction, user)
                        else:
                            await message.remove_reaction(reaction, user)
                    except asyncio.TimeoutError:
                        await message.remove_reaction(reaction, user)
                        break
        else:
            await ctx.response.send_message('It were not found any fics!')
#quantidade de palavras
#sumario

async def setup(bot):
    await bot.add_cog(tracker(bot))