# -*- coding: utf-8 -*-
"""
rss.py - Sopel rss module
Copyright © 2016, RebelCodeBase, https://github.com/RebelCodeBase/sopel-rss
Licensed under the GNU GENERAL PUBLIC LICENSE, Version 3

This module posts rss feed items to irc channels
"""
from __future__ import unicode_literals
from sopel.config.types import StaticSection, ListAttribute, ValidatedAttribute
from sopel.formatting import color, bold, underline
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
        'function': '_rss_add'
    },
    'config': {
        'synopsis': 'synopsis: {}rss config <key> [<value>]',
        'helptext': ['show the value of a key in the config file or set the value of a key in the config file.'],
        'examples': ['{}rss config formats',
                     '{}rss config templates'],
        'required': 1,
        'optional': 1,
        'function': '_rss_config'
    },
    'del': {
        'synopsis': 'synopsis: {}rss del <name>',
        'helptext': ['delete a feed identified by <name>.'],
        'examples': ['{}rss del guardian'],
        'required': 1,
        'optional': 0,
        'function': '_rss_del'
    },
    'fields': {
        'synopsis': 'synopsis: {}rss fields <name>',
        'helptext': ['list all feed item fields available for the feed identified by <name>.',
                     'f: feedname, a: author, d: description, g: guid, l: link, p: published, s: summary, t: title, y: tinyurl'],
        'examples': ['{}rss fields guardian'],
        'required': 1,
        'optional': 0,
        'function': '_rss_fields'
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
        'function': '_rss_format'
    },
    'get': {
        'synopsis': 'synopsis: {}rss get <name>',
        'helptext': ['post all feed items of the feed identified by <name> to its channel.'],
        'examples': ['{}rss get guardian'],
        'required': 1,
        'optional': 0,
        'function': '_rss_get'
    },
    'help': {
        'synopsis': 'synopsis: {}rss help [<command>]',
        'helptext': ['get help for <command>.'],
        'examples': ['{}rss help format'],
        'required': 0,
        'optional': 2,
        'function': '_rss_help'
    },
    'join': {
        'synopsis': 'synopsis: {}rss join',
        'helptext': ['join all channels which are associated to a feed.'],
        'examples': ['{}rss join'],
        'required': 0,
        'optional': 0,
        'function': '_rss_join'
    },
    'list': {
        'synopsis': 'synopsis: {}rss list [<feed>|<channel>]',
        'helptext': ['list the properties of a feed identified by <feed> or list all feeds in a channel identified by <channel>.'],
        'examples': ['{}rss list', '{}rss list guardian',
                     '{}rss list', '{}rss list #sopel-test'],
        'required': 0,
        'optional': 1,
        'function': '_rss_list'
    },
    'update': {
        'synopsis': 'synopsis: {}rss update',
        'helptext': ['post the latest feed items of all feeds.'],
        'examples': ['{}rss update'],
        'required': 0,
        'optional': 0,
        'function': '_rss_update'
    }
}

CONFIG = {
    'feeds': {
        'synopsis': 'feeds = <channel1>|<feed1>|<url1>[|<format1>],<channel2>|<feed2>|<url2>[|<format2>],...',
        'helptext': ['the bot is watching these feeds. it reads the feed located at the url and posts new feed items to the channel in the specified format.'],
        'examples': ['feeds = #sopel-test|guardian|https://www.theguardian.com/world/rss|fl+ftl'],
        'func_get': '_config_get_feeds',
        'func_set': '_config_set_feeds'
    },
    'formats': {
        'synopsis': 'formats = <format1>,<format2>,...',
        'helptext': ['if no format is defined for a feed the bot will try these formats and the global default format (' + FORMAT_DEFAULT + ') one by one until it finds a valid format.',
                     'a format is valid if the fields used in the format do exist in the feed items.'],
        'examples': ['formats = pl+fpatl, plfpl'],
        'func_get': '_config_get_formats',
        'func_set': '_config_set_formats'
    },
    'templates': {
        'synopsis': 'templates = <field1>|<template1>,<field2>|<template2>,...',
        'helptext': ['for each rss feed item field a template can be defined which will be used to create the output string.',
                     'each template must contain exactly one pair of curly braces which will be replaced by the field value.',
                     'the bot will use the global default template for those fields which no custom template is defined.'],
        'examples': [''],
        'func_get': '_config_get_templates',
        'func_set': '_config_set_templates'
    },
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
    'added_sqlite_table_for_feed':
        'added sqlite table "{}" for feed "{}"',
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
    'dropped_sqlite_table_of_feed':
        'dropped sqlite table "{}" of feed "{}"',
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
    'get_help_on_config_keys_with':
        'get help on config keys with: {}rss help config {}',
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
    config.rss.configure_setting('feeds', 'comma separated strings consisting of channel, name, url and an optional format separated by pipes')
    config.rss.configure_setting('formats', 'comma separated strings consisting hash and output fields separated by {}'.format(FORMAT_SEPARATOR))
    config.rss.configure_setting('templates', 'comma separated strings consisting format field and template string separated by pipes'.format(FORMAT_SEPARATOR))


def setup(bot):
    bot = _config_define(bot)
    _config_read(bot)


def shutdown(bot):
    _config_save(bot)


@require_admin
@commands('rss')
def rss(bot, trigger):
    # trigger(1) == 'rss'
    # trigger(2) are the arguments separated by spaces
    args = shlex.split(trigger.group(2))
    _rss(bot, args)


def _rss(bot, args):
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


def _rss_add(bot, args):
    channel = args[1]
    feedname = args[2]
    url = args[3]
    format = ''
    if len(args) == 5:
        format = args[4]
    feedreader = FeedReader(url)
    checkresults = _feed_check(bot, feedreader, channel, feedname)
    if checkresults:
        for message in checkresults:
            LOGGER.debug(message)
            bot.say(message)
        return
    message = _feed_add(bot, channel, feedname, url, format)
    bot.say(message)
    bot.join(channel)
    _config_save(bot)


def _rss_config(bot, args):
    print(args)
    key = args[1]
    if key not in CONFIG:
        return


    value = ''
    if len(args) == 3:
        value = args[2]

    if not value:
        # call get function
        message = globals()[CONFIG[key]['func_get']](bot)
        bot.say(message)
        return

    # call set function
    globals()[CONFIG[key]['func_set']](bot, value)


def _rss_del(bot, args):
    feedname = args[1]
    if not _feed_exists(bot, feedname):
        message = MESSAGES['feed_does_not_exist'].format(feedname)
        bot.say(message)
        return

    message = _feed_delete(bot, feedname)
    bot.say(message)
    _config_save(bot)


def _rss_fields(bot, args):
    feedname = args[1]
    if not _feed_exists(bot, feedname):
        message = MESSAGES['feed_does_not_exist'].format(feedname)
        bot.say(message)
        return

    fields = bot.memory['rss']['formats']['feeds'][feedname].get_fields()
    message = MESSAGES['fields_of_feed_are'].format(feedname, fields)
    bot.say(message)


def _rss_format(bot, args):
    feedname = args[1]
    format = args[2]
    if not _feed_exists(bot, feedname):
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


def _rss_get(bot, args):
    feedname = args[1]

    if not _feed_exists(bot, feedname):
        message = 'feed "{}" doesn\'t exist!'.format(feedname)
        LOGGER.debug(message)
        bot.say(message)
        return

    url = bot.memory['rss']['feeds'][feedname]['url']
    feedreader = FeedReader(url)
    _feed_update(bot, feedreader, feedname, True)


def _rss_help(bot, args):
    args_count = len(args)

    # check if we have a valid command or output general synopsis
    if  args_count == 1 or args[0] not in COMMANDS.keys():
        message = COMMANDS[args[0]]['synopsis'].format(bot.config.core.prefix)
        bot.say(message)
        if args_count == 1:
            message = MESSAGES['command_is_one_of'].format('|'.join(sorted(COMMANDS.keys())))
            bot.say(message)
        return

    # get the command
    cmd = args[1]

    # in case of 'config' we may have to output detailed help on config keys
    if cmd == 'config':
        _help_config(bot, args)
        return

    # output help texts on commands
    _help_text(bot, COMMANDS, cmd)


def _rss_join(bot, args):
    for feedname, feed in bot.memory['rss']['feeds'].items():
        bot.join(feed['channel'])
    if bot.config.core.logging_channel:
        bot.join(bot.config.core.logging_channel)


def _rss_list(bot, args):

    arg = ''
    if len(args) == 2:
        arg = args[1]

    # list feed
    if arg and _feed_exists(bot, arg):
        _feed_list(bot, arg)
        return

    # list feeds in channel
    for feedname, feed in bot.memory['rss']['feeds'].items():
        if arg and arg != feed['channel']:
            continue
        _feed_list(bot, feedname)


@interval(UPDATE_INTERVAL)
def _rss_update(bot, args=[]):
    for feedname in bot.memory['rss']['feeds']:

        # the conditional check is necessary to avoid
        # "RuntimeError: dictionary changed size during iteration"
        # which occurs if a feed has been deleted in the meantime
        if _feed_exists(bot, feedname):
            url = bot.memory['rss']['feeds'][feedname]['url']
            feedreader = FeedReader(url)
            _feed_update(bot, feedreader, feedname, False)


def _config_define(bot):
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


def _config_concatenate_channels(bot):
    channels = bot.config.core.channels
    for feedname, feed in bot.memory['rss']['feeds'].items():
        if not feed['channel'] in channels:
            channels += [feed['channel']]
    return channels


def _config_concatenate_feeds(bot):
    feeds = []
    for feedname, feed in bot.memory['rss']['feeds'].items():
        newfeed = feed['channel'] + '|' + feed['name'] + '|' + feed['url']
        format = bot.memory['rss']['formats']['feeds'][feedname].get_format()
        format_default = bot.memory['rss']['formats']['feeds'][feedname].get_default()
        if format != format_default:
            newfeed += '|' + format
        feeds.append(newfeed)
        feeds.sort()
    return [','.join(feeds)]


def _config_concatenate_formats(bot):
    formats = list()
    for format in bot.memory['rss']['formats']['default']:

        # only save formats that differ from the default
        if not format == FORMAT_DEFAULT:
            formats.append(format)
    return [','.join(formats)]


def _config_concatenate_templates(bot):
    templates = list()
    for field in bot.memory['rss']['templates']['default']:
        template = bot.memory['rss']['templates']['default'][field]

        #only save template that differ from the default
        if not TEMPLATES_DEFAULT[field] == template:
            templates.append(field + '|' + template)
    templates.sort()
    return [','.join(templates)]


def _config_get_feeds(bot):
    return _config_concatenate_feeds(bot)[0]


def _config_get_formats(bot):
    return _config_concatenate_formats(bot)[0] + ',' + FORMAT_DEFAULT


def _config_get_templates(bot):
    templates = list()
    for field in TEMPLATES_DEFAULT:
        try:
            template = bot.memory['rss']['templates']['default'][field]
        except KeyError:
            template = TEMPLATES_DEFAULT[field]
        templates.append(field + '|' + template)
    templates.sort()
    return ','.join(templates)


# read config from disk to memory
def _config_read(bot):

    # read feeds from config file
    if bot.config.rss.feeds and bot.config.rss.feeds[0]:
        _config_split_feeds(bot, bot.config.rss.feeds)

    # read default formats from config file
    if bot.config.rss.formats and bot.config.rss.formats[0]:
        bot.memory['rss']['formats']['default'] = _config_split_formats(bot, bot.config.rss.formats)

    # read default templates from config file
    if bot.config.rss.templates and bot.config.rss.templates[0]:
        bot.memory['rss']['templates']['default'] = _config_split_templates(bot, bot.config.rss.templates)

    message = 'read config from disk'
    LOGGER.debug(message)


# save config from memory to disk
def _config_save(bot):
    if not bot.memory['rss']['feeds'] or not bot.memory['rss']['formats'] or not bot.memory['rss']['templates']:
        return

    # we want no more than MAX_HASHES in our database
    for feedname in bot.memory['rss']['feeds']:
        _db_remove_old_hashes_from_database(bot, feedname)

    bot.config.core.channels = _config_concatenate_channels(bot)
    bot.config.rss.feeds = _config_concatenate_feeds(bot)
    bot.config.rss.formats = _config_concatenate_formats(bot)
    bot.config.rss.templates = _config_concatenate_templates(bot)

    try:
        bot.config.save()
        message = MESSAGES['saved_config_to_disk']
        LOGGER.debug(message)
    except:
        message = MESSAGES['unable_to_save_config_to_disk']
        LOGGER.error(message)


def _config_set_feeds(bot, value):
    feeds = value.split(',')
    _config_split_feeds(bot, feeds)


def _config_set_formats(bot, value):
    formats = value.split(',')
    bot.memory['rss']['formats']['default'] = _config_split_formats(bot, formats)


def _config_set_templates(bot, value):
    templates = value.split(',')
    bot.memory['rss']['templates']['default'] = _config_split_templates(bot, templates)


def _config_split_feeds(bot, feeds):
    for feed in feeds:

        # split feed by pipes
        atoms = feed.split('|')

        try:
            channel = atoms[0]
            feedname = atoms[1]
            url = atoms[2]
        except IndexError:
            continue

        try:
            format = atoms[3]
        except IndexError:
            format = ''

        feedreader = FeedReader(url)
        if _feed_check(bot, feedreader, channel, feedname) == []:
            _feed_add(bot, channel, feedname, url, format)
            _hashes_read(bot, feedname)


def _config_split_formats(bot, formats):
    result = list()

    fields = ''
    for f in TEMPLATES_DEFAULT:
        fields += f

    for format in formats:

        # check if format contains only valid fields
        if not set(format) <= set(fields + FORMAT_SEPARATOR):
            continue
        if not FeedFormater(bot, FeedReader('')).is_format_valid(format, FORMAT_SEPARATOR, fields):
            continue
        result.append(format)

    if result:
        return result
    return FORMAT_DEFAULT


def _config_split_templates(bot, templates):
    result = dict()

    for f in TEMPLATES_DEFAULT:
        result[f] = TEMPLATES_DEFAULT[f]

    for template in templates:
        atoms = template.split('|')
        if FeedFormater(bot, FeedReader('')).is_template_valid(atoms[1]):
            result[atoms[0]] = atoms[1]
    return result


def _db_check_if_table_exists(bot, feedname):
    tablename = _digest_tablename(feedname)
    sql_check_table = "SELECT name FROM sqlite_master WHERE type='table' AND name=(?)"
    return bot.db.execute(sql_check_table, (tablename,)).fetchall()


def _db_create_table(bot, feedname):
    tablename = _digest_tablename(feedname)

    # use UNIQUE for column hash to minimize database writes by using
    # INSERT OR IGNORE (which is an abbreviation for INSERT ON CONFLICT IGNORE)
    sql_create_table = "CREATE TABLE '{}' (id INTEGER PRIMARY KEY, hash VARCHAR(32) UNIQUE)".format(tablename)
    bot.db.execute(sql_create_table)
    message = MESSAGES['added_sqlite_table_for_feed'].format(tablename, feedname)
    LOGGER.debug(message)


def _db_drop_table(bot, feedname):
    tablename = _digest_tablename(feedname)
    sql_drop_table = "DROP TABLE '{}'".format(tablename)
    bot.db.execute(sql_drop_table)
    message = MESSAGES['dropped_sqlite_table_of_feed'].format(tablename, feedname)
    LOGGER.debug(message)


def _db_get_number_of_rows(bot, feedname):
    tablename = _digest_tablename(feedname)
    sql_count_hashes = "SELECT count(*) FROM '{}'".format(tablename)
    return bot.db.execute(sql_count_hashes).fetchall()[0][0]


def _db_read_hashes_from_database(bot, feedname):
    tablename = _digest_tablename(feedname)
    sql_hashes = "SELECT * FROM '{}'".format(tablename)
    message = MESSAGES['read_hashes_of_feed_from_sqlite_table'].format(feedname, tablename)
    LOGGER.debug(message)
    return bot.db.execute(sql_hashes).fetchall()


def _db_remove_old_hashes_from_database(bot, feedname):
    tablename = _digest_tablename(feedname)
    rows = _db_get_number_of_rows(bot, feedname)

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


def _db_save_hash_to_database(bot, feedname, hash):
    tablename = _digest_tablename(feedname)

    # INSERT OR IGNORE is the short form of INSERT ON CONFLICT IGNORE
    sql_save_hashes = "INSERT OR IGNORE INTO '{}' VALUES (NULL,?)".format(tablename)

    try:
        bot.db.execute(sql_save_hashes, (hash,))
        message = MESSAGES['saved_hash_of_feed_to_sqlite_table'].format(hash, feedname, tablename)
        LOGGER.debug(message)
    except:
        message = MESSAGES['unable_to_save_hash_of_feed_to_sqlite_table'].format(hash, feedname, tablename)
        LOGGER.error(message)


def _digest_tablename(feedname):
    # we need to hash the name of the table as sqlite3 does not permit to parametrize table names
    return 'rss_' + hashlib.md5(feedname.encode('utf-8')).hexdigest()


def _feed_add(bot, channel, feedname, url, format=''):
    # create hash table for this feed in sqlite3 database provided by the sopel framework
    result = _db_check_if_table_exists(bot, feedname)
    if not result:
        _db_create_table(bot, feedname)

    # create new RingBuffer for hashes of feed items
    bot.memory['rss']['hashes'][feedname] = RingBuffer(MAX_HASHES_PER_FEED)
    message = MESSAGES['added_ring_buffer_for_feed'].format(feedname)
    LOGGER.debug(message)

    # create new FeedFormatter to handle feed hashing and output
    feedreader = FeedReader(url)
    bot.memory['rss']['formats']['feeds'][feedname] = FeedFormater(bot, feedreader, format)
    message = MESSAGES['added_feed_formater_for_feed'].format(feedname)
    LOGGER.debug(message)

    # create new dict for feed properties
    bot.memory['rss']['feeds'][feedname] = { 'channel': channel, 'name': feedname, 'url': url }

    message_info = MESSAGES['added_rss_feed_to_channel_with_url'].format(feedname, channel, url)
    if format:
        message_info = MESSAGES['added_rss_feed_to_channel_with_url_and_format'].format(feedname, channel, url, format)
    LOGGER.info(message_info)

    return message_info


def _feed_check(bot, feedreader, channel, feedname):
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
    if _feed_exists(bot, feedname):
        message = MESSAGES['feed_name_already_in_use'].format(feedname)
        result.append(message)

    # check that channel starts with #
    if not channel.startswith('#'):
        message = MESSAGES['channel_must_start_with_a_hash_sign'].format(channel)
        result.append(message)

    return result


def _feed_delete(bot, feedname):
    channel = bot.memory['rss']['feeds'][feedname]['channel']
    url = bot.memory['rss']['feeds'][feedname]['url']

    del(bot.memory['rss']['feeds'][feedname])
    message_info = MESSAGES['deleted_rss_feed_in_channel_with_url'].format(feedname, channel, url)
    LOGGER.info(message_info)

    del(bot.memory['rss']['hashes'][feedname])
    message = MESSAGES['deleted_ring_buffer_for_feed'].format(feedname)
    LOGGER.debug(message)

    _db_drop_table(bot, feedname)
    return message_info


def _feed_exists(bot, feedname):
    if feedname in bot.memory['rss']['feeds']:
        return True
    return False


def _feed_list(bot, feedname):
    feed = bot.memory['rss']['feeds'][feedname]
    format_feed = bot.memory['rss']['formats']['feeds'][feedname].get_format()
    bot.say('{} {} {} {}'.format(feed['channel'], feed['name'], feed['url'], format_feed))


def _feed_update(bot, feedreader, feedname, chatty):
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
                _db_save_hash_to_database(bot, feedname, hash)
            message = bot.memory['rss']['formats']['feeds'][feedname].get_post(feedname, item)
            LOGGER.debug(message)
            bot.say(message, channel)


def _hashes_read(bot, feedname):

    # read hashes from database to memory
    hashes = _db_read_hashes_from_database(bot, feedname)

    # each hash in hashes consists of
    # hash[0]: id
    # hash[1]: md5 hash
    for hash in hashes:
        bot.memory['rss']['hashes'][feedname].append(hash[1])


def _help_config(bot, args):
    args_count = len(args)
    if args_count == 3:
        cmd = args[2]
        _help_text(bot, CONFIG, cmd)
        return

    _help_text(bot, COMMANDS, 'config')
    message = MESSAGES['get_help_on_config_keys_with'].format(bot.config.core.prefix, '|'.join(sorted(CONFIG.keys())))
    bot.say(message)


def _help_text(bot, type, cmd):
    message = type[cmd]['synopsis'].format(bot.config.core.prefix)
    bot.say(message)
    for message in type[cmd]['helptext']:
        bot.say(message)
    message = MESSAGES['examples']
    bot.say(message)
    for message in type[cmd]['examples']:
        bot.say(message.format(bot.config.core.prefix))


# Implementing an rss format handler
class FeedFormater:

    LOGGER = get_logger(__name__)

    def __init__(self, bot, feedreader, format=''):
        self.bot = bot
        self.feedreader = feedreader
        self.separator = FORMAT_SEPARATOR
        self.set_minimal()
        self.set_format(format)

    def get_default(self):
        for format in self.bot.memory['rss']['formats']['default']:
            return format
        return FORMAT_DEFAULT

    def get_format(self):
        return self.format

    def get_fields(self):
        return self._format_get_fields(self.feedreader)

    def get_hash(self, feedname, item):
        saneitem = dict()
        saneitem['author'] = self._value_sanitize('author', item)
        saneitem['description'] = self._value_sanitize('description', item)
        saneitem['guid'] = self._value_sanitize('guid', item)
        saneitem['link'] = self._value_sanitize('link', item)
        saneitem['published'] = self._value_sanitize('published', item)
        saneitem['summary'] = self._value_sanitize('summary', item)
        saneitem['title'] = self._value_sanitize('title', item)

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
        fields = self._format_get_fields(self.feedreader)
        if 't' in fields:
            return 'ft+ft'
        return 'fd+fd'

    def get_post(self, feedname, item):
        saneitem = dict()
        saneitem['author'] = self._value_sanitize('author', item)
        saneitem['description'] = self._value_sanitize('description', item)
        saneitem['guid'] = self._value_sanitize('guid', item)
        saneitem['link'] = self._value_sanitize('link', item)
        saneitem['summary'] = self._value_sanitize('summary', item)
        saneitem['title'] = self._value_sanitize('title', item)

        pubtime = ''
        if 'p' in self.output:
            pubtime = time.strftime('%Y-%m-%d %H:%M', item['published_parsed'])
        shorturl = ''
        if 'y' in self.output:
            shorturl = self.feedreader.get_tinyurl(saneitem['link'])

        legend = {
            'f': feedname,
            'a': saneitem['author'],
            'd': saneitem['description'],
            'g': saneitem['guid'],
            'l': saneitem['link'],
            'p': pubtime,
            's': saneitem['summary'],
            't': saneitem['title'],
            'y': shorturl,
        }

        templates = dict()
        for t in TEMPLATES_DEFAULT:
            templates[t] = TEMPLATES_DEFAULT[t]

        for t in self.bot.memory['rss']['templates']['default']:
            if self.is_template_valid(self.bot.memory['rss']['templates']['default'][t]):
                templates[t] = self.bot.memory['rss']['templates']['default'][t]

        post = ''
        for f in self.output:
            post += templates[f].format(legend.get(f, '')) + ' '

        return post[:-1]

    def is_format_valid(self, format, separator, fields = ''):
        hashed, output, remainder = self._format_split(format, separator)
        return(self._format_valid(hashed, output, remainder, fields))

    def is_template_valid(self, template):

        # check if template contains exactly one pair of curly braces
        if template.count('{}') != 1:
            return False

        return True

    def set_format(self, format_new=''):
        format_sanitized = self._format_sanitize(format_new)
        if format_new and format_new != format_sanitized:
            return self.format
        self.format = format_sanitized
        self.hashed, self.output, self.remainder = self._format_split(self.format, self.separator)
        return self.format

    def set_minimal(self):
        self.format = self.get_minimal()
        self.hashed, self.output, self.remainder = self._format_split(self.format, self.separator)
        return self.format

    def _format_get_fields(self, feedreader):
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

    def _format_sanitize(self, format):

        # check if format is valid
        if format:
            hashed, output, remainder = self._format_split(format, self.separator)
            if self._format_valid(hashed, output, remainder):
                return hashed + self.separator + output

        # check in turn if each default format is valid
        for format in self.bot.memory['rss']['formats']['default']:
            hashed, output, remainder = self._format_split(format, self.separator)
            if self._format_valid(hashed, output, remainder):
                return hashed + self.separator + output

        # check if global default format is valid
        hashed, output, remainder = self._format_split(FORMAT_DEFAULT, self.separator)
        if self._format_valid(hashed, output, remainder):
            return hashed + self.separator + output

        # else return the minimal valid format
        return self.get_minimal()


    def _format_split(self, format, separator):
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

    def _format_valid(self, hashed, output, remainder, fields =''):

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
            fields = self._format_get_fields(self.feedreader)

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

    def _value_sanitize(self, key, item):
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
