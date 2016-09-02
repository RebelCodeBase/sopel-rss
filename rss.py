# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from sopel.formatting import bold
from sopel.config.types import StaticSection, ListAttribute, ValidatedAttribute
from sopel.logger import get_logger
from sopel.module import commands, interval, require_admin
from sopel.tools import SopelMemory
import feedparser
import hashlib
import shlex
import time
import urllib.parse
import urllib.request

LOGGER = get_logger(__name__)

MAX_HASHES_PER_FEED = 300

UPDATE_INTERVAL = 60 # seconds

FORMAT_DEFAULT = 'fl+ftl'

FORMAT_SEPARATOR = '+'

TEMPLATES_DEFAULT = {
    'f': bold('[{}]'),
    'a': '<{}>',
    'd': '{}',
    'g': '{}',
    'l': bold('→') + ' {}',
    'p': '({})',
    's': '{}',
    't': '{}',
    'y': bold('→') + ' {}',
}

COMMANDS = {
    'add': {
        'synopsis': 'synopsis: {}rss add <channel> <name> <url> [<format>]',
        'helptext': ['add a feed identified by <name> with feed address <url> to irc channel <channel>. optional: add a format string.'],
        'examples' : ['{}rss add #sopel-test guardian https://www.theguardian.com/world/rss',
                      '{}rss add #sopel-test guardian https://www.theguardian.com/world/rss ' + FORMAT_DEFAULT],
        'required': 3,
        'optional': 1,
        'function': '__rssAdd'
    },
    'del': {
        'synopsis': 'synopsis: {}rss del <name>',
        'helptext': ['delete a feed identified by <name>.'],
        'examples': ['{}rss del guardian'],
        'required': 1,
        'optional': 0,
        'function': '__rssDel'
    },
    'fields': {
        'synopsis': 'synopsis: {}rss fields <name>',
        'helptext': ['list all feed item fields available for the feed identified by <name>.',
                     'f: feedname, a: author, d: description, g: guid, l: link, p: published, s: summary, t: title, y: tinyurl'],
        'examples': ['{}rss fields guardian'],
        'required': 1,
        'optional': 0,
        'function': '__rssFields'
    },
    'format': {
        'synopsis': 'synopsis: {}rss format <name> <format>',
        'helptext': ['set the format string for the feed identified by <name>.',
                     'if <format> is omitted the default format "' + FORMAT_DEFAULT + '" will be used. if the default format is not valid for this feed a minimal format will be used.',
                     'a format string is separated by the separator "' + FORMAT_SEPARATOR + '"',
                     'the left part of the format string indicates the fields that will be hashed for an item. if you change this part all feed items will be reposted.',
                     'the fields determine when a feed item will be reposted. if you see duplicates then first look at this part of the format string.',
                     'the right part of the format string determines which feed item fields will be posted.'],
        'examples': ['{}rss format fl+ftl'],
        'required': 2,
        'optional': 0,
        'function': '__rssFormat'
    },
    'get': {
        'synopsis': 'synopsis: {}rss get <name>',
        'helptext': ['post all feed items of the feed identified by <name> to its channel.'],
        'examples': ['{}rss get guardian'],
        'required': 1,
        'optional': 0,
        'function': '__rssGet'
    },
    'help': {
        'synopsis': 'synopsis: {}rss help [<command>]',
        'helptext': ['get help for <command>.'],
        'examples': ['{}rss help format'],
        'required': 0,
        'optional': 1,
        'function': '__rssHelp'
    },
    'join': {
        'synopsis': 'synopsis: {}rss join',
        'helptext': ['join all channels which are associated to a feed'],
        'examples': ['{}rss join'],
        'required': 0,
        'optional': 0,
        'function': '__rssJoin'
    },
    'list': {
        'synopsis': 'synopsis: {}rss list [<feed>|<channel>]',
        'helptext': ['list the properties of a feed identified by <feed> or list all feeds in a channel identified by <channel>.'],
        'examples': ['{}rss list', '{}rss list guardian',
                     '{}rss list', '{}rss list #sopel-test'],
        'required': 0,
        'optional': 1,
        'function': '__rssList'
    },
    'update': {
        'synopsis': 'synopsis: {}rss update',
        'helptext': ['post the latest feed items of all feeds'],
        'examples': ['{}rss update'],
        'required': 0,
        'optional': 0,
        'function': '__rssUpdate'
    }
}

MESSAGES = {
    'added_feed_formater_for_feed':
        'added feed formater for feed "{}"',
    'added_ring_buffer_for_feed':
        'added ring buffer for feed "{}"',
    'added_rss_feed_to_channel_with_url':
        'added rss feed "{}" to channel "{}" with url "{}"',
    'added_rss_feed_to_channel_with_url_and_format':
        'added rss feed "{}" to channel "{}" with url "{}" and format "{}"',
    'channel_must_start_with_a_hash_sign':
        'channel "{}" must start with a "#"',
    'command_is_one_of':
        'where <command> is one of {}',
    'consider_rss_fields':
        'consider {}rss fields {} to create a valid format',
    'deleted_ring_buffer_for_feed':
        'deleted ring buffer for feed "{}"',
    'deleted_rss_feed_in_channel_with_url':
        'deleted rss feed "{}" in channel "{}" with url "{}"',
    'examples':
        'examples:',
    'feed_items_have_neither_title_nor_description':
        'feed items have neither title nor description',
    'feed_name_already_in_use':
        'feed name "{}" is already in use, please choose a different name',
    'feed_does_not_exist':
        'feed "{}" doesn\'t exist!',
    'fields_of_feed_are':
        'fields of feed "{}" are "{}"',
    'format_of_feed_has_been_set_to':
        'format of feed "{}" has been set to "{}"',
    'read_hashes_of_feed_from_sqlite_table':
        'read hashes of feed "{}" from sqlite table "{}"',
    'removed_rows_in_table_of_feed':
        'removed {} rows in table "{}" of feed "{}"',
    'saved_config_to_disk':
        'saved config to disk',
    'saved_hash_of_feed_to_sqlite_table':
        'saved hash "{}" of feed "{}" to sqlite table "{}"',
    'synopsis_rss':
        'synopsis: {}rss {}',
    'unable_to_read_feed':
        'unable to read feed',
    'unable_to_read_url_of_feed':
        'unable to read url "{}" of feed "{}"',
    'unable_to_save_config_to_disk':
        'unable to save config to disk!',
    'unable_to_save_hash_of_feed_to_sqlite_table':
        'unable to save hash "{}" of feed "{}" to sqlite table "{}"',
}


class RSSSection(StaticSection):
    feeds = ListAttribute('feeds')
    formats = ListAttribute('formats')
    templates = ListAttribute('templates')


def configure(config):
    config.define_section('rss', RSSSection)
    config.rss.configure_setting('feeds', 'comma separated strings consisting of channel, name, url and an optional format separated by spaces')
    config.rss.configure_setting('formats', 'comma separated strings consisting hash and output fields separated by {}'.format(FORMAT_SEPARATOR))
    config.rss.configure_setting('templates', 'comma separated strings consisting format field and template string separated by spaces'.format(FORMAT_SEPARATOR))


def setup(bot):
    bot = __configDefine(bot)
    __configRead(bot)


def shutdown(bot):
    __configSave(bot)


@require_admin
@commands('rss')
def rss(bot, trigger):
    # trigger(1) == 'rss'
    # trigger(2) are the arguments separated by spaces
    args = shlex.split(trigger.group(2))
    __rss(bot, args)


def __rss(bot, args):
    args_count = len(args)

    # check if we have a valid command or output general synopsis
    if  args_count == 0 or args[0] not in COMMANDS.keys():
        message = MESSAGES['synopsis_rss'].format(
            bot.config.core.prefix, '|'.join(sorted(COMMANDS.keys())))
        bot.say(message)
        return

    cmd = args[0]

    # check if the number of arguments is valid
    present = args_count-1
    required = COMMANDS[cmd]['required']
    optional = COMMANDS[cmd]['optional']
    if present < required or present > required + optional:
        bot.say(COMMANDS[cmd]['synopsis'].format(bot.config.core.prefix))
        return

    if args_count > 5:
        globals()[COMMANDS['help']['function']](bot, ['help', args[0]])
        return

    # call command function
    globals()[COMMANDS[cmd]['function']](bot, args)


def __rssAdd(bot, args):
    channel = args[1]
    feedname = args[2]
    url = args[3]
    format = ''
    if len(args) == 5:
        format = args[4]
    feedreader = FeedReader(url)
    checkresults = __feedCheck(bot, feedreader, channel, feedname)
    if checkresults:
        for message in checkresults:
            LOGGER.debug(message)
            bot.say(message)
        return
    message = __feedAdd(bot, channel, feedname, url, format)
    bot.say(message)
    bot.join(channel)
    __configSave(bot)


def __rssDel(bot, args):
    feedname = args[1]
    if not __feedExists(bot, feedname):
        message = MESSAGES['feed_does_not_exist'].format(feedname)
        bot.say(message)
        return

    message = __feedDelete(bot, feedname)
    bot.say(message)
    __configSave(bot)


def __rssFields(bot, args):
    feedname = args[1]
    if not __feedExists(bot, feedname):
        message = MESSAGES['feed_does_not_exist'].format(feedname)
        bot.say(message)
        return

    fields = bot.memory['rss']['formats']['feeds'][feedname].get_fields()
    message = MESSAGES['fields_of_feed_are'].format(feedname, fields)
    bot.say(message)


def __rssFormat(bot, args):
    feedname = args[1]
    format = args[2]
    if not __feedExists(bot, feedname):
        message = MESSAGES['feed_does_not_exist'].format(feedname)
        bot.say(message)
        return

    format_new = bot.memory['rss']['formats']['feeds'][feedname].set_format(format)

    if format == format_new:
        message = MESSAGES['format_of_feed_has_been_set_to'].format(feedname, format_new)
        LOGGER.debug(message)
        bot.say(message)
        return

    message = MESSAGES['consider_rss_fields'].format(bot.config.core.prefix, feedname)
    bot.say(message)


def __rssGet(bot, args):
    feedname = args[1]

    if not __feedExists(bot, feedname):
        message = 'feed "{}" doesn\'t exist!'.format(feedname)
        LOGGER.debug(message)
        bot.say(message)
        return

    url = bot.memory['rss']['feeds'][feedname]['url']
    feedreader = FeedReader(url)
    __feedUpdate(bot, feedreader, feedname, True)


def __rssHelp(bot, args):
    args_count = len(args)

    # check if we have a valid command or output general synopsis
    if  args_count == 1 or args[0] not in COMMANDS.keys():
        message = COMMANDS[args[0]]['synopsis'].format(bot.config.core.prefix)
        bot.say(message)
        if args_count == 1:
            message = MESSAGES['command_is_one_of'].format('|'.join(sorted(COMMANDS.keys())))
            bot.say(message)
        return

    # output help messages
    cmd = args[1]
    message = COMMANDS[cmd]['synopsis'].format(bot.config.core.prefix)
    bot.say(message)
    for message in COMMANDS[cmd]['helptext']:
        bot.say(message)
    message = MESSAGES['examples']
    bot.say(message)
    for message in COMMANDS[cmd]['examples']:
        bot.say(message.format(bot.config.core.prefix))


def __rssJoin(bot, args):
    for feedname, feed in bot.memory['rss']['feeds'].items():
        bot.join(feed['channel'])
    if bot.config.core.logging_channel:
        bot.join(bot.config.core.logging_channel)


def __rssList(bot, args):

    arg = ''
    if len(args) == 2:
        arg = args[1]

    # list feed
    if arg and __feedExists(bot, arg):
        __feedList(bot, arg)
        return

    # list feeds in channel
    for feedname, feed in bot.memory['rss']['feeds'].items():
        if arg and arg != feed['channel']:
            continue
        __feedList(bot, feedname)


@interval(UPDATE_INTERVAL)
def __rssUpdate(bot, args=[]):
    for feedname in bot.memory['rss']['feeds']:

        # the conditional check is necessary to avoid
        # "RuntimeError: dictionary changed size during iteration"
        # which occurs if a feed has been deleted in the meantime
        if __feedExists(bot, feedname):
            url = bot.memory['rss']['feeds'][feedname]['url']
            feedreader = FeedReader(url)
            __feedUpdate(bot, feedreader, feedname, False)


def __configDefine(bot):
    bot.config.define_section('rss', RSSSection)
    bot.memory['rss'] = SopelMemory()
    bot.memory['rss']['feeds'] = dict()
    bot.memory['rss']['hashes'] = dict()
    bot.memory['rss']['formats'] = dict()
    bot.memory['rss']['formats']['feeds'] = dict()
    bot.memory['rss']['formats']['default'] = list()
    bot.memory['rss']['templates'] = dict()
    bot.memory['rss']['templates']['default'] = dict()
    return bot


# read config from disk to memory
def __configRead(bot):

    # read feeds from config file
    if bot.config.rss.feeds and bot.config.rss.feeds[0]:
        for feed in bot.config.rss.feeds:

            # split feed by spaces
            atoms = feed.split(' ')

            channel = atoms[0]
            feedname = atoms[1]
            url = atoms[2]

            try:
                format = atoms[3]
            except IndexError:
                format = ''

            __feedAdd(bot, channel, feedname, url, format)
            __hashesRead(bot, feedname)

    fields = ''
    for f in TEMPLATES_DEFAULT:
        fields += f
        bot.memory['rss']['templates']['default'][f] = TEMPLATES_DEFAULT[f]

    # read default formats from config file
    if bot.config.rss.formats and bot.config.rss.formats[0]:
        for format in bot.config.rss.formats:
            # check if format contains only valid fields
            if not set(format) <= set(fields + FORMAT_SEPARATOR):
                continue
            if not FeedFormater(FeedReader('')).is_format_valid(format, FORMAT_SEPARATOR, fields):
                continue
            bot.memory['rss']['formats']['default'].append(format)

    if not bot.memory['rss']['formats']['default']:
        bot.memory['rss']['formats']['default'] = FORMAT_DEFAULT

    # read default templates from config file
    if bot.config.rss.templates and bot.config.rss.templates[0]:
        for template in bot.config.rss.templates:
            atoms = template.split(' ')
            bot.memory['rss']['templates']['default'][atoms[0]] = atoms[1]

    message = 'read config from disk'
    LOGGER.debug(message)


# save config from memory to disk
def __configSave(bot):
    if not bot.memory['rss']['feeds'] or not bot.memory['rss']['formats'] or not bot.memory['rss']['templates']:
        return

    # we want no more than MAX_HASHES in our database
    for feedname in bot.memory['rss']['feeds']:
        __dbRemoveOldHashesFromDatabase(bot, feedname)

    # flatten feeds for config file
    feeds = []
    for feedname, feed in bot.memory['rss']['feeds'].items():
        newfeed = feed['channel'] + ' ' + feed['name'] + ' ' + feed['url']
        format = bot.memory['rss']['formats']['feeds'][feedname].get_format()
        format_default = bot.memory['rss']['formats']['feeds'][feedname].get_default()
        if format != format_default:
            newfeed += ' ' + format
        feeds.append(newfeed)
    bot.config.rss.feeds = [','.join(feeds)]

    # save channels to config file
    channels = bot.config.core.channels
    for feedname, feed in bot.memory['rss']['feeds'].items():
        if not feed['channel'] in channels:
            bot.config.core.channels += [feed['channel']]

    # flatten formats for config file
    formats = list()
    for format in bot.memory['rss']['formats']['default']:

        # only save formats that differ from the default
        if not format == FORMAT_DEFAULT:
            formats.append(format)

    bot.config.rss.formats = [','.join(formats)]

    # flatten templates for config file
    templates = list()
    for field in bot.memory['rss']['templates']['default']:
        template = bot.memory['rss']['templates']['default'][field]

        #only save template that differ from the default
        if not TEMPLATES_DEFAULT[field] == template:
            templates.append(field + ' ' + template)

    bot.config.rss.templates = [','.join(templates)]

    try:
        bot.config.save()
        message = MESSAGES['saved_config_to_disk']
        LOGGER.debug(message)
    except:
        message = MESSAGES['unable_to_save_config_to_disk']
        LOGGER.error(message)


def __dbCheckIfTableExists(bot, feedname):
    tablename = __digestTablename(feedname)
    sql_check_table = "SELECT name FROM sqlite_master WHERE type='table' AND name=(?)"
    return bot.db.execute(sql_check_table, (tablename,)).fetchall()


def __dbCreateTable(bot, feedname):
    tablename = __digestTablename(feedname)

    # use UNIQUE for column hash to minimize database writes by using
    # INSERT OR IGNORE (which is an abbreviation for INSERT ON CONFLICT IGNORE)
    sql_create_table = "CREATE TABLE '{}' (id INTEGER PRIMARY KEY, hash VARCHAR(32) UNIQUE)".format(tablename)
    bot.db.execute(sql_create_table)
    message = 'added sqlite table "{}" for feed "{}"'.format(tablename, feedname)
    LOGGER.debug(message)


def __dbDropTable(bot, feedname):
    tablename = __digestTablename(feedname)
    sql_drop_table = "DROP TABLE '{}'".format(tablename)
    bot.db.execute(sql_drop_table)
    message = 'dropped sqlite table "{}" of feed "{}"'.format(tablename, feedname)
    LOGGER.debug(message)


def __dbGetNumberOfRows(bot, feedname):
    tablename = __digestTablename(feedname)
    sql_count_hashes = "SELECT count(*) FROM '{}'".format(tablename)
    return bot.db.execute(sql_count_hashes).fetchall()[0][0]


def __dbReadHashesFromDatabase(bot, feedname):
    tablename = __digestTablename(feedname)
    sql_hashes = "SELECT * FROM '{}'".format(tablename)
    message = MESSAGES['read_hashes_of_feed_from_sqlite_table'].format(feedname, tablename)
    LOGGER.debug(message)
    return bot.db.execute(sql_hashes).fetchall()


def __dbRemoveOldHashesFromDatabase(bot, feedname):
    tablename = __digestTablename(feedname)
    rows = __dbGetNumberOfRows(bot, feedname)

    if rows > MAX_HASHES_PER_FEED:

        # calculate number of rows to delete in table hashes
        delete_rows = rows - MAX_HASHES_PER_FEED

        # prepare sqlite statement to figure out
        # the ids of those hashes which should be deleted
        sql_first_hashes = "SELECT id FROM '{}' ORDER BY '{}'.id LIMIT (?)".format(tablename, tablename)

        # loop over the hashes which should be deleted
        for row in bot.db.execute(sql_first_hashes, (str(delete_rows),)).fetchall():

            # delete old hashes from database
            sql_delete_hashes = "DELETE FROM '{}' WHERE id = (?)".format(tablename)
            bot.db.execute(sql_delete_hashes, (str(row[0]),))

        message = MESSAGES['removed_rows_in_table_of_feed'].format(str(delete_rows), tablename, feedname)
        LOGGER.debug(message)


def __dbSaveHashToDatabase(bot, feedname, hash):
    tablename = __digestTablename(feedname)

    # INSERT OR IGNORE is the short form of INSERT ON CONFLICT IGNORE
    sql_save_hashes = "INSERT OR IGNORE INTO '{}' VALUES (NULL,?)".format(tablename)

    try:
        bot.db.execute(sql_save_hashes, (hash,))
        message = MESSAGES['saved_hash_of_feed_to_sqlite_table'].format(hash, feedname, tablename)
        LOGGER.debug(message)
    except:
        message = MESSAGES['unable_to_save_hash_of_feed_to_sqlite_table'].format(hash, feedname, tablename)
        LOGGER.error(message)


def __digestTablename(feedname):
    # we need to hash the name of the table as sqlite3 does not permit to parametrize table names
    return 'rss_' + hashlib.md5(feedname.encode('utf-8')).hexdigest()


def __feedAdd(bot, channel, feedname, url, format=''):
    # create hash table for this feed in sqlite3 database provided by the sopel framework
    result = __dbCheckIfTableExists(bot, feedname)
    if not result:
        __dbCreateTable(bot, feedname)

    # create new RingBuffer for hashes of feed items
    bot.memory['rss']['hashes'][feedname] = RingBuffer(MAX_HASHES_PER_FEED)
    message = MESSAGES['added_ring_buffer_for_feed'].format(feedname)
    LOGGER.debug(message)

    # create new FeedFormatter to handle feed hashing and output
    feedreader = FeedReader(url)
    bot.memory['rss']['formats']['feeds'][feedname] = FeedFormater(feedreader, format)
    message = MESSAGES['added_feed_formater_for_feed'].format(feedname)
    LOGGER.debug(message)

    # create new dict for feed properties
    bot.memory['rss']['feeds'][feedname] = { 'channel': channel, 'name': feedname, 'url': url }

    message_info = MESSAGES['added_rss_feed_to_channel_with_url'].format(feedname, channel, url)
    if format:
        message_info = MESSAGES['added_rss_feed_to_channel_with_url_and_format'].format(feedname, channel, url, format)
    LOGGER.info(message_info)

    return message_info


def __feedCheck(bot, feedreader, channel, feedname):
    result = []

    # read feed
    feed = feedreader.get_feed()
    if not feed:
        message = MESSAGES['unabele_to_read_feed']
        return [message]

    try:
        item = feed['entries'][0]
    except IndexError:
        message = MESSAGES['unable_to_read_feed']
        return [message]

    # check that feed items have either title or description
    if not hasattr(item, 'title') and not hasattr(item, 'description'):
        message = MESSAGES['feed_items_have_neither_title_nor_description']
        result.append(message)

    # check that feed name is unique
    if __feedExists(bot, feedname):
        message = MESSAGES['feed_name_already_in_use'].format(feedname)
        result.append(message)

    # check that channel starts with #
    if not channel.startswith('#'):
        message = MESSAGES['channel_must_start_with_a_hash_sign'].format(channel)
        result.append(message)

    return result


def __feedDelete(bot, feedname):
    channel = bot.memory['rss']['feeds'][feedname]['channel']
    url = bot.memory['rss']['feeds'][feedname]['url']

    del(bot.memory['rss']['feeds'][feedname])
    message_info = MESSAGES['deleted_rss_feed_in_channel_with_url'].format(feedname, channel, url)
    LOGGER.info(message_info)

    del(bot.memory['rss']['hashes'][feedname])
    message = MESSAGES['deleted_ring_buffer_for_feed'].format(feedname)
    LOGGER.debug(message)

    __dbDropTable(bot, feedname)
    return message_info


def __feedExists(bot, feedname):
    if feedname in bot.memory['rss']['feeds']:
        return True
    return False


def __feedList(bot, feedname):
    feed = bot.memory['rss']['feeds'][feedname]
    format_feed = bot.memory['rss']['formats']['feeds'][feedname].get_format()
    bot.say('{} {} {} {}'.format(feed['channel'], feed['name'], feed['url'], format_feed))


def __feedUpdate(bot, feedreader, feedname, chatty):
    feed = feedreader.get_feed()

    if not feed:
        url = bot.memory['rss']['feeds'][feedname]['url']
        message = MESSAGES['unable_to_read_url_of_feed'].format(url, feedname)
        LOGGER.error(message)
        return

    channel = bot.memory['rss']['feeds'][feedname]['channel']

    # bot.say new or all items
    for item in reversed(feed['entries']):
        hash = bot.memory['rss']['formats']['feeds'][feedname].get_hash(feedname, item)
        new_item = not hash in bot.memory['rss']['hashes'][feedname].get()
        if chatty or new_item:
            if new_item:
                bot.memory['rss']['hashes'][feedname].append(hash)
                __dbSaveHashToDatabase(bot, feedname, hash)
            message = bot.memory['rss']['formats']['feeds'][feedname].get_post(feedname, item)
            LOGGER.debug(message)
            bot.say(message, channel)


def __hashesRead(bot, feedname):

    # read hashes from database to memory
    hashes = __dbReadHashesFromDatabase(bot, feedname)

    # each hash in hashes consists of
    # hash[0]: id
    # hash[1]: md5 hash
    for hash in hashes:
        bot.memory['rss']['hashes'][feedname].append(hash[1])


# Implementing an rss format handler
class FeedFormater:

    LOGGER = get_logger(__name__)

    def __init__(self, feedreader, format=''):
        self.feedreader = feedreader
        self.separator = FORMAT_SEPARATOR
        self.FORMAT_DEFAULT = FORMAT_DEFAULT
        self.set_minimal()
        self.set_format(format)

    def get_default(self):
        return self.FORMAT_DEFAULT

    def get_format(self):
        return self.format

    def get_fields(self):
        return self.__formatGetFields(self.feedreader)

    def get_hash(self, feedname, item):
        saneitem = dict()
        saneitem['author'] = self.__valueSanitize('author', item)
        saneitem['description'] = self.__valueSanitize('description', item)
        saneitem['guid'] = self.__valueSanitize('guid', item)
        saneitem['link'] = self.__valueSanitize('link', item)
        saneitem['published'] = self.__valueSanitize('published', item)
        saneitem['summary'] = self.__valueSanitize('summary', item)
        saneitem['title'] = self.__valueSanitize('title', item)

        legend = {
            'f': feedname,
            'a': saneitem['author'],
            'd': saneitem['description'],
            'g': saneitem['guid'],
            'l': saneitem['link'],
            'p': saneitem['published'],
            's': saneitem['summary'],
            't': saneitem['title'],
            'y': saneitem['link'],
        }

        signature = ''
        for f in self.hashed:
            signature += legend.get(f, '')

        return hashlib.md5(signature.encode('utf-8')).hexdigest()

    def get_minimal(self):
        fields = self.__formatGetFields(self.feedreader)
        if 't' in fields:
            return 'ft+ft'
        return 'fd+fd'

    def get_post(self, feedname, item):
        saneitem = dict()
        saneitem['author'] = self.__valueSanitize('author', item)
        saneitem['description'] = self.__valueSanitize('description', item)
        saneitem['guid'] = self.__valueSanitize('guid', item)
        saneitem['link'] = self.__valueSanitize('link', item)
        saneitem['summary'] = self.__valueSanitize('summary', item)
        saneitem['title'] = self.__valueSanitize('title', item)

        pubtime = ''
        if 'p' in self.output:
            pubtime = time.strftime('%Y-%m-%d %H:%M', item['published_parsed'])
        shorturl = ''
        if 'y' in self.output:
            shorturl = self.feedreader.get_tinyurl(saneitem['link'])

        legend = {
            'f': bold('[' + feedname + ']'),
            'a': '<' + saneitem['author'] + '>',
            'd': '|' + saneitem['description'] + '|',
            'g': '{' + saneitem['guid'] + '}',
            'l': bold('→') + ' ' + saneitem['link'],
            'p': '(' + pubtime + ')',
            's': '«' + saneitem['summary']+ '»',
            't': saneitem['title'],
            'y': bold('→') + ' ' + shorturl,
        }

        post = ''
        for f in self.output:
            post += legend.get(f, '') + ' '

        return post[:-1]

    def is_format_valid(self, format, separator, fields = ''):
        hashed, output, remainder = self.__formatSplit(format, separator)
        return(self.__formatValid(hashed, output, remainder, fields))

    def set_format(self, format_new=''):
        format_sanitized = self.__formatSanitize(format_new)
        if format_new and format_new != format_sanitized:
            return self.format
        self.format = format_sanitized
        self.hashed, self.output, self.remainder = self.__formatSplit(self.format, self.separator)
        return self.format

    def set_minimal(self):
        self.format = self.get_minimal()
        self.hashed, self.output, self.remainder = self.__formatSplit(self.format, self.separator)
        return self.format

    def __formatGetFields(self, feedreader):
        feed = feedreader.get_feed()

        try:
            item = feed.entries[0]
        except IndexError:
            item = dict()

        fields = 'f'

        if hasattr(item, 'author'):
            fields += 'a'
        if hasattr(item, 'description'):
            fields += 'd'
        if hasattr(item, 'guid'):
            fields += 'g'
        if hasattr(item, 'link'):
            fields += 'l'
        if hasattr(item, 'published') and hasattr(item, 'published_parsed'):
            fields += 'p'
        if hasattr(item, 'summary'):
            fields += 's'
        if hasattr(item, 'title'):
            fields += 't'
        if hasattr(item, 'link'):
            fields += 'y'

        return fields

    def __formatSanitize(self, format):
        if not format:
            format = self.get_default()

        hashed, output, remainder = self.__formatSplit(format, self.separator)

        if not self.__formatValid(hashed, output, remainder):
            return self.get_minimal()

        return hashed + self.separator + output

    def __formatSplit(self, format, separator):
        format_split = str(format).split(separator)
        hashed = format_split[0]
        try:
            output = format_split[1]
        except IndexError:
            output = ''

        try:
            remainder = format_split[2]
        except IndexError:
            remainder = ''

        return hashed, output, remainder

    def __formatValid(self, hashed, output, remainder, fields = ''):

        # check format for duplicate separators
        if remainder:
            return False

        # check if hashed is empty
        if not len(hashed):
            return False

        # check if output is empty
        if not len(output):
            return False

        # check if hashed contains only the feedname
        if hashed == 'f':
            return False

        # check if hashed contains only the feedname
        if output == 'f':
            return False

        if not fields:
            fields = self.__formatGetFields(self.feedreader)

        # check hashed has only valid fields
        for f in hashed:
            if f not in fields:
                return False

        # check output has only valid fields
        for f in output:
            if f not in fields:
                return False

        # check hashed for duplicates
        if len(hashed) > len(set(hashed)):
            return False

        # check output for duplicates
        if len(output) > len(set(output)):
            return False

        return True

    def __valueSanitize(self, key, item):
        if hasattr(item, key):
            return item[key]
        return ''


# Implementing an rss feed reader for dependency injection
class FeedReader:
    def __init__(self, url):
        self.url = url

    def get_feed(self):
        try:
            feed = feedparser.parse(self.url)
            return feed
        except:
            return False

    def get_tinyurl(self, url):
        tinyurlapi = 'https://tinyurl.com/api-create.php'
        data = urllib.parse.urlencode({'url': url}).encode("utf-8")
        req = urllib.request.Request(tinyurlapi, data)
        response = urllib.request.urlopen(req)
        tinyurl = response.read().decode('utf-8')
        return tinyurl


    # Implementing a ring buffer
# https://www.safaribooksonline.com/library/view/python-cookbook/0596001673/ch05s19.html
class RingBuffer:
    """ class that implements a not-yet-full buffer """
    def __init__(self,size_max):
        self.max = size_max
        self.index = 0
        self.data = []

    class __Full:
        """ class that implements a full buffer """
        def append(self, x):
            """ Append an element overwriting the oldest one. """
            self.data[self.cur] = x
            self.cur = (self.cur+1) % self.max
        def get(self):
            """ return list of elements in correct order """
            return self.data[self.cur:]+self.data[:self.cur]

    def append(self,x):
        """ append an element at the end of the buffer """
        self.data.append(x)
        if len(self.data) == self.max:
            self.cur = 0
            # Permanently change self's class from non-full to full
            self.__class__ = self.__Full

    def get(self):
        """ return a list of elements from the oldest to the newest. """
        return self.data
