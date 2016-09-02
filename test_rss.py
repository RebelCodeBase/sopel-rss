# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from sopel.db import SopelDB
from sopel.formatting import bold
from sopel.modules import rss
from sopel.test_tools import MockSopel, MockConfig
import feedparser
import hashlib
import os
import pytest
import tempfile
import types


FEED_VALID = '''<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0" xml:base="http://www.site1.com/feed" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Site 1 Articles</title>
<link>http://www.site1.com/feed</link>
<description></description>
<language>en</language>

<item>
<title>Title 3</title>
<link>http://www.site1.com/article3</link>
<description>&lt;p&gt;Description of article 3&lt;/p&gt;</description>
<summary>&lt;p&gt;Summary of article 3&lt;/p&gt;</summary>
<author>Author 3</author>
<pubDate>Sat, 23 Aug 2016 03:30:33 +0000</pubDate>
<guid isPermaLink="false">3 at http://www.site1.com/</guid>
</item>

<item>
<title>Title 2</title>
<link>http://www.site1.com/article2</link>
<description>&lt;p&gt;Description of article 2&lt;/p&gt;</description>
<summary>&lt;p&gt;Summary of article 2&lt;/p&gt;</summary>
<author>Author 2</author>
<pubDate>Sat, 22 Aug 2016 02:20:22 +0000</pubDate>
<guid isPermaLink="false">2 at http://www.site1.com/</guid>
</item>

<item>
<title>Title 1</title>
<link>http://www.site1.com/article1</link>
<description>&lt;p&gt;Description of article 1&lt;/p&gt;</description>
<summary>&lt;p&gt;Summary of article 1&lt;/p&gt;</summary>
<author>Author 1</author>
<pubDate>Sat, 21 Aug 2016 01:10:11 +0000</pubDate>
<guid isPermaLink="false">1 at http://www.site1.com/</guid>
</item>

</channel>
</rss>'''


FEED_INVALID = '''<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0" xml:base="http://www.site1.com/feed" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Site 1 Articles</title>
<link>http://www.site1.com/feed</link>
<description></description>
<language>en</language>
</channel>
</rss>'''


FEED_ITEM_NEITHER_TITLE_NOR_DESCRIPTION = '''<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0" xml:base="http://www.site1.com/feed" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Site</title>
<link>http://www.site.com/feed</link>
<description></description>

<item>
<link>http://www.site.com/article</link>
</item>

</channel>
</rss>'''


def __fixtureBotSetup(request):
    bot = MockSopel('Sopel')
    bot = rss.__configDefine(bot)
    bot.config.core.db_filename = tempfile.mkstemp()[1]
    bot.db = SopelDB(bot.config)
    bot.output = ''

    # monkey patch bot
    def join(self, channel):
        if channel not in bot.channels:
            bot.channels.append(channel)
    bot.join = types.MethodType(join, bot)
    def say(self, message, channel = ''):
        bot.output += message + "\n"
    bot.say = types.MethodType(say, bot)

    # tear down bot
    def fin():
        os.remove(bot.config.filename)
        os.remove(bot.config.core.db_filename)
    request.addfinalizer(fin)

    return bot


def __fixtureBotAddData(bot, id, url):
    bot.memory['rss']['feeds']['feed'+id] = {'channel': '#channel' + id, 'name': 'feed' + id, 'url': url}
    bot.memory['rss']['hashes']['feed'+id] = rss.RingBuffer(100)
    feedreader = MockFeedReader(FEED_VALID)
    bot.memory['rss']['formats']['feeds']['feed'+id] = rss.FeedFormater(feedreader)
    sql_create_table = 'CREATE TABLE ' + rss.__digestTablename('feed'+id) + ' (id INTEGER PRIMARY KEY, hash VARCHAR(32) UNIQUE)'
    bot.db.execute(sql_create_table)
    bot.channels = ['#channel'+id]
    return bot


@pytest.fixture(scope="function")
def bot(request):
    bot = __fixtureBotSetup(request)
    bot = __fixtureBotAddData(bot, '1', 'http://www.site1.com/feed')
    return bot


@pytest.fixture(scope="function")
def bot_void(request):
    bot = __fixtureBotSetup(request)
    return bot


@pytest.fixture(scope="function")
def bot_rssList(request):
    bot = __fixtureBotSetup(request)
    bot = __fixtureBotAddData(bot, '1', 'http://www.site1.com/feed')
    bot = __fixtureBotAddData(bot, '2', 'http://www.site2.com/feed')
    return bot


@pytest.fixture(scope="function")
def bot_rssUpdate(request):
    bot = __fixtureBotSetup(request)
    bot = __fixtureBotAddData(bot, '1', FEED_VALID)
    return bot


@pytest.fixture(scope="module")
def feedreader_feed_valid():
    return MockFeedReader(FEED_VALID)


@pytest.fixture(scope="module")
def feedreader_feed_invalid():
    return MockFeedReader(FEED_INVALID)


@pytest.fixture(scope="module")
def feedreader_feed_item_neither_title_nor_description():
    return MockFeedReader(FEED_ITEM_NEITHER_TITLE_NOR_DESCRIPTION)


# Implementing a mock rss feed get_feeder
class MockFeedReader:
    def __init__(self, url):
        self.url = url

    def get_feed(self):
        feed = feedparser.parse(self.url)
        return feed

    def get_tinyurl(self, url):
        return 'https://tinyurl.com/govvpmm'


def test_rss_too_many_parameters(bot):
    rss.__rss(bot, ['add', '#channel', 'feedname', FEED_VALID, 'fl+ftl', 'fifth_argument'])
    expected = rss.COMMANDS['add']['synopsis'].format(bot.config.core.prefix) + '\n'
    assert expected == bot.output


def test_rss_too_few_parameters(bot):
    rss.__rss(bot, ['add', '#channel', 'feedname'])
    expected = rss.COMMANDS['add']['synopsis'].format(bot.config.core.prefix) + '\n'
    assert expected == bot.output


def test_rss_feed_add(bot):
    rss.__rss(bot, ['add', '#channel', 'feedname', FEED_VALID])
    assert rss.__feedExists(bot, 'feedname') == True


def test_rss_feed_delete(bot):
    rss.__rss(bot, ['add', '#channel', 'feedname', FEED_VALID])
    rss.__rss(bot, ['del', 'feedname'])
    assert rss.__feedExists(bot, 'feedname') == False


def test_rss_fields_get(bot):
    rss.__rss(bot, ['fields', 'feed1'])
    expected = rss.MESSAGES['fields_of_feed_are'].format('feed1', 'fadglpsty') + '\n'
    assert expected == bot.output


def test_rss_format_set(bot):
    rss.__rss(bot, ['format', 'feed1', 'asl+als'])
    format_new = bot.memory['rss']['formats']['feeds']['feed1'].get_format()
    assert 'asl+als' == format_new


def test_rssGet_post_feed_items(bot):
    rss.__rss(bot, ['add', '#channel', 'feedname', FEED_VALID])
    rss.__rss(bot, ['get', 'feedname'])
    expected = bold('[feedname]') + ' Title 1 ' + bold('→') + " http://www.site1.com/article1\n" + bold('[feedname]') + ' Title 2 ' + bold('→') + " http://www.site1.com/article2\n" + bold('[feedname]') + ' Title 3 ' + bold('→') + " http://www.site1.com/article3\n"
    assert expected == bot.output


def test_rss_help_synopsis_help(bot):
    rss.__rss(bot, ['help'])
    expected = rss.COMMANDS['help']['synopsis'].format(bot.config.core.prefix) + '\n'
    expected += rss.MESSAGES['command_is_one_of'].format('|'.join(sorted(rss.COMMANDS.keys()))) + '\n'
    assert expected == bot.output


def test_rss_join(bot):
    rss.__rss(bot, ['join'])
    channels = []
    for feed in bot.memory['rss']['feeds']:
        feedchannel = bot.memory['rss']['feeds'][feed]['channel']
        if feedchannel not in channels:
            channels.append(feedchannel)
    assert channels == bot.channels


def test_rss_list_feed(bot):
    rss.__rss(bot, ['list', 'feed1'])
    expected = '#channel1 feed1 http://www.site1.com/feed fl+ftl\n'
    assert expected == bot.output


def test_rss_update_update(bot_rssUpdate):
    rss.__rss(bot_rssUpdate, ['update'])
    expected = bold('[feed1]') + ' Title 1 ' + bold('→') + " http://www.site1.com/article1\n" + bold('[feed1]') + ' Title 2 ' + bold('→') + " http://www.site1.com/article2\n" + bold('[feed1]') + ' Title 3 ' + bold('→') + " http://www.site1.com/article3\n"
    assert expected == bot_rssUpdate.output


def test_rssAdd_feed_add(bot):
    rss.__rssAdd(bot, ['add', '#channel', 'feedname', FEED_VALID])
    assert rss.__feedExists(bot, 'feedname') == True


def test_rssDel_feed_nonexistent(bot):
    rss.__rssDel(bot, ['del', 'abcd'])
    expected = rss.MESSAGES['feed_does_not_exist'].format('abcd') + '\n'
    assert expected == bot.output


def test_rssDel_feed_delete(bot):
    rss.__rssAdd(bot, ['add', '#channel', 'feedname', FEED_VALID])
    rss.__rssDel(bot, ['del', 'feedname'])
    assert rss.__feedExists(bot, 'feedname') == False


def test_rssFields_feed_nonexistent(bot):
    rss.__rssFields(bot, ['fields', 'abcd'])
    expected = rss.MESSAGES['feed_does_not_exist'].format('abcd') + '\n'
    assert expected == bot.output


def test_rssFields_get(bot):
    rss.__rssFields(bot, ['fields', 'feed1'])
    expected = rss.MESSAGES['fields_of_feed_are'].format('feed1', 'fadglpst') + '\n'
    assert expected == bot.output


def test_rssFields_get(bot):
    rss.__rssAdd(bot, ['add', '#channel', 'feedname', FEED_VALID, 'fltp+atl'])
    bot.output = ''
    rss.__rssFields(bot, ['fields', 'feedname'])
    expected = rss.MESSAGES['fields_of_feed_are'].format('feedname', 'fadglpsty') + '\n'
    assert expected == bot.output


def test_rssFormat_feed_nonexistent(bot):
    rss.__rssFormat(bot, ['format', 'abcd', ''])
    expected = rss.MESSAGES['feed_does_not_exist'].format('abcd') + '\n'
    assert expected == bot.output


def test_rssFormat_format_unchanged(bot):
    format_old = bot.memory['rss']['formats']['feeds']['feed1'].get_format()
    rss.__rssFormat(bot, ['format', 'feed1', 'abcd+efgh'])
    format_new = bot.memory['rss']['formats']['feeds']['feed1'].get_format()
    assert format_old == format_new
    expected = rss.MESSAGES['consider_rss_fields'].format(bot.config.core.prefix, 'feed1') + '\n'
    assert expected == bot.output


def test_rssFormat_format_changed(bot):
    format_old = bot.memory['rss']['formats']['feeds']['feed1'].get_format()
    rss.__rssFormat(bot, ['format', 'feed1', 'asl+als'])
    format_new = bot.memory['rss']['formats']['feeds']['feed1'].get_format()
    assert format_old != format_new


def test_rssFormat_format_set(bot):
    rss.__rssFormat(bot, ['format', 'feed1', 'asl+als'])
    format_new = bot.memory['rss']['formats']['feeds']['feed1'].get_format()
    assert 'asl+als' == format_new


def test_rssFormat_format_output(bot_rssUpdate):
    rss.__rssFormat(bot_rssUpdate, ['format', 'feed1', 'fadglpst+fadglpst'])
    rss.__rssUpdate(bot_rssUpdate, ['update'])
    expected = rss.MESSAGES['format_of_feed_has_been_set_to'].format('feed1', 'fadglpst+fadglpst') + '''
\x02[feed1]\x02 <Author 1> |<p>Description of article 1</p>| {1 at http://www.site1.com/} \x02→\x02 http://www.site1.com/article1 (2016-08-21 01:10) «<p>Description of article 1</p>» Title 1
\x02[feed1]\x02 <Author 2> |<p>Description of article 2</p>| {2 at http://www.site1.com/} \x02→\x02 http://www.site1.com/article2 (2016-08-22 02:20) «<p>Description of article 2</p>» Title 2
\x02[feed1]\x02 <Author 3> |<p>Description of article 3</p>| {3 at http://www.site1.com/} \x02→\x02 http://www.site1.com/article3 (2016-08-23 03:30) «<p>Description of article 3</p>» Title 3
'''
    assert expected == bot_rssUpdate.output


def test_rssGetfeed_nonexistent(bot):
    rss.__rssGet(bot, ['get', 'abcd'])
    expected = rss.MESSAGES['feed_does_not_exist'].format('abcd') + '\n'
    assert expected == bot.output


def test_rssGet_post_feed_items(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', FEED_VALID)
    rss.__rssGet(bot, ['get', 'feedname'])
    expected = bold('[feedname]') + ' Title 1 ' + bold('→') + " http://www.site1.com/article1\n" + bold('[feedname]') + ' Title 2 ' + bold('→') + " http://www.site1.com/article2\n" + bold('[feedname]') + ' Title 3 ' + bold('→') + " http://www.site1.com/article3\n"
    assert expected == bot.output


def test_rssHelp_synopsis_help(bot):
    rss.__rssHelp(bot, ['help'])
    expected = rss.COMMANDS['help']['synopsis'].format(bot.config.core.prefix) + '\n'
    expected += rss.MESSAGES['command_is_one_of'].format('|'.join(sorted(rss.COMMANDS.keys()))) + '\n'
    assert expected == bot.output


def test_rssHelp_command(bot):
    rss.__rssHelp(bot, ['help', 'add'])
    expected = rss.COMMANDS['add']['synopsis'].format(bot.config.core.prefix) + '\n'
    for message in rss.COMMANDS['add']['helptext']:
        expected += message + '\n'
    expected += rss.MESSAGES['examples'] + '\n'
    for message in rss.COMMANDS['add']['examples']:
        expected += message.format(bot.config.core.prefix) + '\n'
    assert expected == bot.output


def test_rssJoin(bot):
    rss.__rssJoin(bot, ['join'])
    channels = []
    for feed in bot.memory['rss']['feeds']:
        feedchannel = bot.memory['rss']['feeds'][feed]['channel']
        if feedchannel not in channels:
            channels.append(feedchannel)
    assert channels == bot.channels


def test_rssList_all(bot_rssList):
    rss.__rssList(bot_rssList, ['list'])
    expected1 = '#channel1 feed1 http://www.site1.com/feed'
    expected2 = '#channel2 feed2 http://www.site2.com/feed'
    assert expected1 in bot_rssList.output
    assert expected2 in bot_rssList.output


def test_rssList_feed(bot):
    rss.__rssList(bot, ['list', 'feed1'])
    expected = '#channel1 feed1 http://www.site1.com/feed fl+ftl\n'
    assert expected == bot.output


def test_rssList_channel(bot):
    rss.__rssList(bot, ['list', '#channel1'])
    expected = '#channel1 feed1 http://www.site1.com/feed fl+ftl\n'
    assert expected == bot.output


def test_rssList_no_feed_found(bot):
    rss.__rssList(bot, ['lsit', 'invalid'])
    assert '' == bot.output


def test_rssUpdate_update(bot_rssUpdate):
    rss.__rssUpdate(bot_rssUpdate, ['update'])
    expected = bold('[feed1]') + ' Title 1 ' + bold('→') + " http://www.site1.com/article1\n" + bold('[feed1]') + ' Title 2 ' + bold('→') + " http://www.site1.com/article2\n" + bold('[feed1]') + ' Title 3 ' + bold('→') + " http://www.site1.com/article3\n"
    assert expected == bot_rssUpdate.output


def test_rssUpdate_no_update(bot_rssUpdate):
    rss.__rssUpdate(bot_rssUpdate, ['update'])
    bot.output = ''
    rss.__rssUpdate(bot_rssUpdate, ['update'])
    assert '' == bot.output


def test_configDefine_SopelMemory():
    bot = MockSopel('Sopel')
    bot = rss.__configDefine(bot)
    assert type(bot.memory['rss']) == rss.SopelMemory


def test_configDefine_feeds():
    bot = MockSopel('Sopel')
    bot = rss.__configDefine(bot)
    assert type(bot.memory['rss']['feeds']) == dict


def test_configDefine_hashes():
    bot = MockSopel('Sopel')
    bot = rss.__configDefine(bot)
    assert type(bot.memory['rss']['hashes']) == dict


def test_configDefine_formats():
    bot = MockSopel('Sopel')
    bot = rss.__configDefine(bot)
    assert type(bot.memory['rss']['formats']['feeds']) == dict


def test_configRead_feed_default(bot_void):
    rss.__configRead(bot_void)
    feeds = bot_void.memory['rss']['feeds']
    expected = {}
    assert expected == feeds


def test_configRead_format_default(bot_void):
    rss.__configRead(bot_void)
    formats = bot_void.memory['rss']['formats']['default']
    expected = rss.FORMAT_DEFAULT
    assert expected == formats


def test_configRead_format_custom_valid(bot_void):
    formats_custom = ['al+fpatl','y+fty']
    bot_void.config.rss.formats = formats_custom
    rss.__configRead(bot_void)
    formats = bot_void.memory['rss']['formats']['default']
    assert formats_custom == formats


def test_configRead_format_custom_invalid(bot_void):
    formats_custom = ['al+fpatl','yy+fty']
    bot_void.config.rss.formats = formats_custom
    rss.__configRead(bot_void)
    formats = bot_void.memory['rss']['formats']['default']
    expected = ['al+fpatl']
    assert expected == formats


def test_configRead_template_default(bot_void):
    rss.__configRead(bot_void)
    templates = bot_void.memory['rss']['templates']['default']
    expected = rss.TEMPLATES_DEFAULT
    assert expected == templates


def test_configRead_template_custom(bot_void):
    templates_custom = ['t >>{}<<']
    bot_void.config.rss.templates = templates_custom
    rss.__configRead(bot_void)
    templates = bot_void.memory['rss']['templates']['default']
    expected = dict()
    for t in rss.TEMPLATES_DEFAULT:
        expected[t] = rss.TEMPLATES_DEFAULT[t]
    expected['t'] = '>>{}<<'
    assert expected == templates


def test_configSave_writes(bot):
    bot.memory['rss']['formats']['default'] = ['ft+ftpal']
    for t in rss.TEMPLATES_DEFAULT:
        bot.memory['rss']['templates']['default'][t] = rss.TEMPLATES_DEFAULT[t]
    bot.memory['rss']['templates']['default']['a'] = '<{}>'
    bot.memory['rss']['templates']['default']['t'] = '<<{}>>'
    rss.__configSave(bot)
    expected = '''[core]
owner = '''+'''
admins = '''+'''
homedir = ''' + bot.config.homedir + '''
db_filename = ''' + bot.db.filename + '''

[rss]
feeds = #channel1 feed1 http://www.site1.com/feed
formats = ft+ftpal
templates = t <<{}>>

'''
    f = open(bot.config.filename, 'r')
    config = f.read()
    assert expected == config


def test_dbCreateTable_and_dbCheckIfTableExists(bot):
    rss.__dbCreateTable(bot, 'feedname')
    result = rss.__dbCheckIfTableExists(bot, 'feedname')
    assert [(rss.__digestTablename('feedname'),)] == result


def test_dbDropTable(bot):
    rss.__dbCreateTable(bot, 'feedname')
    rss.__dbDropTable(bot, 'feedname')
    result = rss.__dbCheckIfTableExists(bot, 'feedname')
    assert [] == result


def test_dbGetNumerOfRows(bot):
    ROWS = 10
    for i in range(ROWS):
        hash = rss.hashlib.md5(str(i).encode('utf-8')).hexdigest()
        bot.memory['rss']['hashes']['feed1'].append(hash)
        rss.__dbSaveHashToDatabase(bot, 'feed1', hash)
    rows_feed = rss.__dbGetNumberOfRows(bot, 'feed1')
    assert ROWS == rows_feed


def test_dbRemoveOldHashesFromDatabase(bot):
    SURPLUS_ROWS = 10
    bot.memory['rss']['hashes']['feed1'] = rss.RingBuffer(rss.MAX_HASHES_PER_FEED + SURPLUS_ROWS)
    for i in range(rss.MAX_HASHES_PER_FEED + SURPLUS_ROWS):
        hash = hashlib.md5(str(i).encode('utf-8')).hexdigest()
        bot.memory['rss']['hashes']['feed1'].append(hash)
        rss.__dbSaveHashToDatabase(bot, 'feed1', hash)
    rss.__dbRemoveOldHashesFromDatabase(bot, 'feed1')
    rows_feed = rss.__dbGetNumberOfRows(bot, 'feed1')
    assert rss.MAX_HASHES_PER_FEED == rows_feed


def test_dbSaveHashToDatabase(bot):
    rss.__dbSaveHashToDatabase(bot, 'feed1', '463f9357db6c20a94a68f9c9ef3bb0fb')
    hashes = rss.__dbReadHashesFromDatabase(bot, 'feed1')
    expected = [(1, '463f9357db6c20a94a68f9c9ef3bb0fb')]
    assert expected == hashes


def test_digestTablename_works():
    digest = rss.__digestTablename('thisisatest')
    assert 'rss_f830f69d23b8224b512a0dc2f5aec974' == digest


def test_feedAdd_create_db_table(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', FEED_VALID)
    result = rss.__dbCheckIfTableExists(bot, 'feedname')
    assert [(rss.__digestTablename('feedname'),)] == result


def test_feedAdd_create_ring_buffer(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', FEED_VALID)
    assert type(bot.memory['rss']['hashes']['feedname']) == rss.RingBuffer


def test_feedAdd_create_feed(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', FEED_VALID)
    feed = bot.memory['rss']['feeds']['feedname']
    assert {'name': 'feedname', 'url': FEED_VALID, 'channel': '#channel'} == feed


def test_feedCheck_feed_valid(bot, feedreader_feed_valid):
    checkresults = rss.__feedCheck(bot, feedreader_feed_valid, '#newchannel', 'newname')
    assert not checkresults


def test_feedCheck_feedname_must_be_unique(bot, feedreader_feed_valid):
    checkresults = rss.__feedCheck(bot, feedreader_feed_valid, '#newchannel', 'feed1')
    expected = [rss.MESSAGES['feed_name_already_in_use'].format('feed1')]
    assert expected == checkresults


def test_feedCheck_channel_must_start_with_hash(bot, feedreader_feed_valid):
    checkresults = rss.__feedCheck(bot, feedreader_feed_valid, 'nohashsign', 'newname')
    expected = [rss.MESSAGES['channel_must_start_with_a_hash_sign'].format('nohashsign')]
    assert expected == checkresults


def test_feedCheck_feed_invalid(bot, feedreader_feed_invalid):
    checkresults = rss.__feedCheck(bot, feedreader_feed_invalid, '#channel', 'newname')
    expected = [rss.MESSAGES['unable_to_read_feed'].format('nohashsign')]
    assert expected == checkresults


def test_feedCheck_feeditem_must_have_title_or_description(bot, feedreader_feed_item_neither_title_nor_description):
    checkresults = rss.__feedCheck(bot, feedreader_feed_item_neither_title_nor_description, '#newchannel', 'newname')
    expected = [rss.MESSAGES['feed_items_have_neither_title_nor_description']]
    assert expected == checkresults


def test_feedDelete_delete_db_table(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', FEED_VALID)
    rss.__feedDelete(bot, 'feedname')
    result = rss.__dbCheckIfTableExists(bot, 'feedname')
    assert [] == result


def test_feedDelete_delete_ring_buffer(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', FEED_VALID)
    rss.__feedDelete(bot, 'feedname')
    assert 'feedname' not in bot.memory['rss']['hashes']


def test_feedDelete_delete_feed(bot):
    rss.__feedAdd(bot, 'channel', 'feed', FEED_VALID)
    rss.__feedDelete(bot, 'feed')
    assert 'feed' not in bot.memory['rss']['feeds']


def test_feedExists_passes(bot):
    assert rss.__feedExists(bot, 'feed1') == True


def test_feedExists_fails(bot):
    assert rss.__feedExists(bot, 'nofeed') == False


def test_feedList_format(bot):
    rss.__feedAdd(bot, 'channel', 'feed', FEED_VALID, 'ft+ftldsapg')
    rss.__feedList(bot, 'feed')
    expected = 'channel feed ' + FEED_VALID + ' ft+ftldsapg\n'
    output = bot.output
    assert expected == bot.output


def test_feedUpdate_print_messages(bot, feedreader_feed_valid):
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', True)
    expected = bold('[feed1]') + ' Title 1 ' + bold('→') + " http://www.site1.com/article1\n" + bold('[feed1]') + ' Title 2 ' + bold('→') + " http://www.site1.com/article2\n" + bold('[feed1]') + ' Title 3 ' + bold('→') + " http://www.site1.com/article3\n"
    assert expected == bot.output


def test_feedUpdate_store_hashes(bot, feedreader_feed_valid):
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', True)
    expected = ['4a8c89da09811991825b2263a4f9a7e0', '1f1c02250ee0f37ee99542a58fe266de', '53d66294d8b4313baf22d3ef62cb4cec']
    hashes = bot.memory['rss']['hashes']['feed1'].get()
    assert expected == hashes


def test_feedUpdate_no_update(bot, feedreader_feed_valid):
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', True)
    bot.output = ''
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', False)
    assert '' == bot.output


def test_hashesRead(bot, feedreader_feed_valid):
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', True)
    expected = ['4a8c89da09811991825b2263a4f9a7e0', '1f1c02250ee0f37ee99542a58fe266de', '53d66294d8b4313baf22d3ef62cb4cec']
    bot.memory['rss']['hashes']['feed1'] = rss.RingBuffer(100)
    rss.__hashesRead(bot, 'feed1')
    hashes = bot.memory['rss']['hashes']['feed1'].get()
    assert expected == hashes


def test_FeedFormater_get_format_custom(feedreader_feed_valid):
    ff = rss.FeedFormater(feedreader_feed_valid, 'ta+ta')
    assert 'ta+ta' == ff.get_format()


def test_FeedFormater_get_format_default(feedreader_feed_valid):
    ff = rss.FeedFormater(feedreader_feed_valid)
    assert ff.get_default() == ff.get_format()


def test_FeedFormater_get_fields_feed_valid(feedreader_feed_valid):
    ff = rss.FeedFormater(feedreader_feed_valid)
    fields = ff.get_fields()
    assert 'fadglpsty' == fields


def test_FeedFormater_get_fields_feed_item_neither_title_nor_description(feedreader_feed_item_neither_title_nor_description):
    ff = rss.FeedFormater(feedreader_feed_item_neither_title_nor_description)
    fields = ff.get_fields()
    assert 'd' not in fields and 't' not in fields


def test_FeedFormater_check_format_default(feedreader_feed_valid):
    ff = rss.FeedFormater(feedreader_feed_valid)
    assert ff.get_default() == ff.get_format()


def test_FeedFormater_check_format_hashed_empty(feedreader_feed_valid):
    format = '+t'
    ff = rss.FeedFormater(feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_FeedFormater_check_format_output_empty(feedreader_feed_valid):
    format = 't'
    ff = rss.FeedFormater(feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_FeedFormater_check_format_hashed_only_feedname(feedreader_feed_valid):
    format = 'f+t'
    ff = rss.FeedFormater(feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_FeedFormater_check_format_output_only_feedname(feedreader_feed_valid):
    format = 't+f'
    ff = rss.FeedFormater(feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_FeedFormater_check_format_duplicate_separator(feedreader_feed_valid):
    format = 't+t+t'
    ff = rss.FeedFormater(feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_FeedFormater_check_format_duplicate_field_hashed(feedreader_feed_valid):
    format = 'll+t'
    ff = rss.FeedFormater(feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_FeedFormater_check_format_duplicate_field_output(feedreader_feed_valid):
    format = 'l+tll'
    ff = rss.FeedFormater(feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_FeedFormater_check_format_tinyurl(feedreader_feed_valid):
    format = 'fy+ty'
    ff = rss.FeedFormater(feedreader_feed_valid, format)
    assert format == ff.get_format()


def test_FeedFormater_check_tinyurl_output(feedreader_feed_valid):
    format = 'fy+ty'
    ff = rss.FeedFormater(feedreader_feed_valid, format)
    item = feedreader_feed_valid.get_feed().entries[0]
    post = ff.get_post('feed1', item)
    expected = 'Title 3 \x02→\x02 https://tinyurl.com/govvpmm'
    assert expected == post


def test_RingBuffer_append():
    rb = rss.RingBuffer(3)
    assert rb.get() == []
    rb.append('1')
    assert ['1'] == rb.get()


def test_RingBuffer_overflow():
    rb = rss.RingBuffer(3)
    rb.append('hash1')
    rb.append('hash2')
    rb.append('hash3')
    assert ['hash1', 'hash2', 'hash3'] == rb.get()
    rb.append('hash4')
    assert ['hash2', 'hash3', 'hash4'] == rb.get()
